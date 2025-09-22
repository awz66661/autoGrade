#!/usr/bin/env python

# 常用指令：
"""
python autograde.py --clean all          # 清理base_path和当前目录的所有文件
python autograde.py --parallel 20 --resume --export all  # 并发20个进程评分，导出所有格式，从上次中断处继续
"""


import os
import sys
import json
import glob
import argparse
import logging
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from tqdm import tqdm
from openai import OpenAI

# 导入自定义模块
from grader import Grader, GradingCriteria
from similarity_checker import SimilarityChecker
from progress_manager import ProgressManager, CacheManager
from score_analyzer import StatisticsAnalyzer
from export_utils import ExportManager


# 终端颜色美化
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    END = '\033[0m'


def setup_logging(log_level: str = 'INFO') -> logging.Logger:
    """设置日志系统"""
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, log_level.upper()))

    # 文件处理器
    file_handler = logging.FileHandler(
        f"grading_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
        mode='w',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter(f'{Colors.YELLOW}%(levelname)s{Colors.END}: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def load_config(config_path: str = 'config.json') -> Dict:
    """加载配置文件"""
    path = Path(config_path)
    if not path.exists():
        print(f"{Colors.YELLOW}配置文件未找到: {config_path}{Colors.END}")
        default_config = {
            "base_path": "./homework",
            "api_key": "YOUR_API_KEY",
            "base_url": "YOUR_API_BASE_URL",
            "model": "gpt-4",
            "request_timeout": 60,
            "max_retries": 3,
            "retry_delay": 5,
            "max_workers": 5,
            "similarity_threshold": 0.85
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        print(f"已创建配置文件模板: {config_path}")
        sys.exit(1)

    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # 设置默认值
    config.setdefault('request_timeout', 60)
    config.setdefault('max_retries', 3)
    config.setdefault('retry_delay', 5)
    config.setdefault('max_workers', 5)
    config.setdefault('similarity_threshold', 0.85)

    return config


def get_submissions(base_path: str) -> List[Tuple[str, Path]]:
    """获取所有学生提交的文件"""
    submissions_dir = Path(base_path) / 'submissions'
    if not submissions_dir.is_dir():
        raise FileNotFoundError(f"未找到 submissions 文件夹: {submissions_dir}")

    submissions = []
    py_files = list(submissions_dir.glob('*.py'))

    for file_path in py_files:
        if '_' in file_path.name:
            student_id = file_path.name.split('_')[0]
        else:
            student_id = file_path.stem

        if file_path.stat().st_size == 0:
            logging.warning(f"文件为空，已跳过: {file_path.name}")
            continue

        submissions.append((student_id, file_path))

    return submissions


def get_template_content(base_path: str) -> str:
    """读取参考答案模板"""
    template_path = Path(base_path) / 'template.py'
    if not template_path.is_file():
        raise FileNotFoundError(f"未找到 template.py 文件: {template_path}")

    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def clean_previous_results(config_file: str = 'config.json') -> bool:
    """清理之前的评分结果文件"""
    try:
        # 读取配置获取base_path
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            base_path = config.get('base_path', '.')

        # 定义要清理的文件模式
        patterns = [
            'grading_results_*.csv',
            'grading_report_*.xlsx',
            'grading_report_*.md',
            'grading_data_*.json',
            'statistics_report.txt',
            'score_distribution.png',
            'grading_progress.json'
        ]

        cleaned_files = []

        # 清理base_path下的文件（兼容旧版本）
        for pattern in patterns:
            file_pattern = os.path.join(base_path, pattern)
            matching_files = glob.glob(file_pattern)

            for file_path in matching_files:
                try:
                    os.remove(file_path)
                    cleaned_files.append(os.path.basename(file_path))
                except PermissionError:
                    file_name = os.path.basename(file_path)
                    print(f"⚠️  跳过正在使用的文件: {file_name}")
                except OSError as e:
                    print(f"⚠️  无法删除文件 {file_path}: {e}")

        # 清理reports目录下的文件
        reports_path = os.path.join(base_path, 'reports')
        if os.path.exists(reports_path):
            for pattern in patterns:
                file_pattern = os.path.join(reports_path, pattern)
                matching_files = glob.glob(file_pattern)

                for file_path in matching_files:
                    try:
                        os.remove(file_path)
                        cleaned_files.append(f"reports/{os.path.basename(file_path)}")
                    except PermissionError:
                        file_name = os.path.basename(file_path)
                        print(f"⚠️  跳过正在使用的文件: reports/{file_name}")
                    except OSError as e:
                        print(f"⚠️  无法删除文件 {file_path}: {e}")

        if cleaned_files:
            print(f"🗑️  已清理 {len(cleaned_files)} 个文件:")
            for file_name in cleaned_files:
                print(f"   - {file_name}")
        else:
            print("✅ 没有找到需要清理的文件")

        return True

    except Exception as e:
        print(f"❌ 清理文件时出错: {e}")
        return False


def clean_local_directory() -> bool:
    """清理当前运行目录中的残留文件"""
    try:
        # 定义要清理的文件模式（在当前目录）
        patterns = [
            'grading_results_*.csv',
            'grading_report_*.xlsx',
            'grading_report_*.md',
            'grading_data_*.json',
            'statistics_report.txt',
            'score_distribution.png',
            'grading_progress.json',
            'grading*.log',
            '*.log'  # 清理所有日志文件
        ]

        cleaned_files = []

        # 清理当前目录下的文件
        for pattern in patterns:
            matching_files = glob.glob(pattern)

            for file_path in matching_files:
                # 跳过重要的配置文件
                if os.path.basename(file_path) in ['config.json', 'grading_criteria_example.json']:
                    continue

                try:
                    os.remove(file_path)
                    cleaned_files.append(os.path.basename(file_path))
                except PermissionError:
                    file_name = os.path.basename(file_path)
                    print(f"⚠️  跳过正在使用的文件: {file_name}")
                except OSError as e:
                    print(f"⚠️  无法删除文件 {file_path}: {e}")

        # 清理当前目录下reports目录
        reports_path = './reports'
        if os.path.exists(reports_path):
            for pattern in patterns[:-2]:  # 不包括日志文件
                file_pattern = os.path.join(reports_path, pattern)
                matching_files = glob.glob(file_pattern)

                for file_path in matching_files:
                    try:
                        os.remove(file_path)
                        cleaned_files.append(f"reports/{os.path.basename(file_path)}")
                    except PermissionError:
                        file_name = os.path.basename(file_path)
                        print(f"⚠️  跳过正在使用的文件: reports/{file_name}")
                    except OSError as e:
                        print(f"⚠️  无法删除文件 {file_path}: {e}")

        if cleaned_files:
            print(f"🗑️  已从当前目录清理 {len(cleaned_files)} 个文件:")
            for file_name in cleaned_files:
                print(f"   - {file_name}")
        else:
            print("✅ 当前目录没有找到需要清理的文件")

        return True

    except Exception as e:
        print(f"❌ 清理本地文件时出错: {e}")
        return False


def grade_single_submission(args: Tuple) -> Dict:
    """评分单个作业（用于并发）"""
    student_id, file_path, grader, template_content, progress_manager = args

    try:
        # 检查是否应该跳过
        if progress_manager and progress_manager.should_skip(student_id):
            return None

        # 标记为正在处理
        if progress_manager:
            progress_manager.mark_in_progress(student_id)

        # 读取学生代码
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            submission_content = f.read()

        # 评分
        result = grader.grade(
            student_id=student_id,
            submission_content=submission_content,
            template_content=template_content
        )

        # 更新进度
        if progress_manager:
            if result['success']:
                progress_manager.mark_completed(student_id, result)
            else:
                progress_manager.mark_failed(student_id, result.get('comment', 'Unknown error'))

        return result

    except Exception as e:
        logging.error(f"评分失败 {student_id}: {e}")
        if progress_manager:
            progress_manager.mark_failed(student_id, str(e))
        return {
            'student_id': student_id,
            'score': 0,
            'comment': f'评分失败: {str(e)}',
            'success': False
        }


def main():
    """主程序入口"""
    # 命令行参数解析
    parser = argparse.ArgumentParser(
        description='自动Python作业评分系统 v2.0',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  %(prog)s                              # 正常评分
  %(prog)s --clean base                 # 仅清理base_path目录
  %(prog)s --clean local                # 仅清理当前目录
  %(prog)s --clean all                  # 清理两个目录
  %(prog)s --resume                     # 从上次中断处继续
  %(prog)s --parallel 4                 # 使用4个并发进程
  %(prog)s --export all                 # 导出所有格式
  %(prog)s --student 12345678           # 只评分特定学生

清理功能：
  清理操作是独立的，只清理文件不执行评分。
  --clean 选项与其他评分选项互斥。
        """
    )
    parser.add_argument('--config', '-c', default='config.json', help='配置文件路径')
    parser.add_argument('--resume', '-r', action='store_true', help='从上次中断处继续')
    parser.add_argument('--retry-failed', action='store_true', help='重试失败的作业')
    parser.add_argument('--no-cache', action='store_true', help='不使用缓存')
    parser.add_argument('--no-similarity', action='store_true', help='跳过相似度检测')
    parser.add_argument('--parallel', '-p', type=int, default=1, help='并发数（默认1）')
    parser.add_argument('--export', '-e', choices=['csv', 'excel', 'json', 'markdown', 'all'],
                       default='excel', help='导出格式')
    parser.add_argument('--criteria', help='自定义评分标准文件')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='日志级别')
    parser.add_argument('--student', '-s', help='只评分特定学生')

    # 清理选项（独立运行，不执行评分）
    clean_group = parser.add_mutually_exclusive_group()
    clean_group.add_argument('--clean', choices=['base', 'local', 'all'],
                           help='清理文件：base=清理base_path目录，local=清理当前目录，all=清理两个目录')
    clean_group.add_argument('--clean-base', action='store_true', help='仅清理base_path目录中的评分结果文件')
    clean_group.add_argument('--clean-local', action='store_true', help='仅清理当前运行目录中的残留文件')
    clean_group.add_argument('--clean-all', action='store_true', help='清理base_path和当前目录的所有文件')

    args = parser.parse_args()

    # 设置日志
    logger = setup_logging(args.log_level)

    print(f"{Colors.BOLD}{Colors.BLUE}=== 自动 Python 作业评分系统 v2.0 ==={Colors.END}")
    print(f"{Colors.CYAN}{'=' * 40}{Colors.END}\n")

    # 检查是否为清理模式
    is_clean_mode = args.clean or args.clean_base or args.clean_local or args.clean_all

    if is_clean_mode:
        # 清理模式：只执行清理操作，不进行评分
        print(f"🗑️  {Colors.BOLD}文件清理模式{Colors.END}")

        try:
            # 加载配置（用于获取base_path）
            config = load_config(args.config)

            # 执行相应的清理操作
            if args.clean == 'base' or args.clean_base:
                print(f"\n🗑️  清理base_path目录...")
                clean_previous_results(args.config)
            elif args.clean == 'local' or args.clean_local:
                print(f"\n🗑️  清理当前运行目录...")
                clean_local_directory()
            elif args.clean == 'all' or args.clean_all:
                print(f"\n🗑️  清理base_path目录...")
                clean_previous_results(args.config)
                print(f"\n🗑️  清理当前运行目录...")
                clean_local_directory()

            print(f"\n✅ {Colors.GREEN}清理完成！{Colors.END}")
            return

        except Exception as e:
            print(f"\n❌ {Colors.RED}清理失败: {e}{Colors.END}")
            return

    try:
        # 评分模式：正常的评分流程
        print(f"📊 {Colors.BOLD}评分模式{Colors.END}")

        # 加载配置
        print(f"\n⚙️  {Colors.BOLD}初始化系统...{Colors.END}")
        config = load_config(args.config)
        print(f"  ✓ 配置文件加载成功")

        # 初始化OpenAI客户端
        client = OpenAI(
            api_key=config['api_key'],
            base_url=config['base_url'],
            timeout=config['request_timeout']
        )
        print(f"  ✓ API客户端初始化成功")

        # 初始化评分标准
        criteria = GradingCriteria(args.criteria) if args.criteria else GradingCriteria()
        print(f"  ✓ 评分标准加载成功")

        # 初始化评分器
        grader = Grader(client, config['model'], criteria)
        if args.no_cache:
            grader.cache = {}  # 清空缓存

        # 初始化进度管理器
        progress_manager = ProgressManager() if args.resume or args.retry_failed else None
        if args.retry_failed and progress_manager:
            progress_manager.reset_failed()
            print(f"  ✓ 准备重试失败的作业")

        # 获取作业列表
        base_path = config['base_path']
        submissions = get_submissions(base_path)

        # 过滤特定学生
        if args.student:
            submissions = [(sid, path) for sid, path in submissions if sid == args.student]
            if not submissions:
                print(f"{Colors.RED}未找到学生 {args.student} 的作业{Colors.END}")
                return

        print(f"  ✓ 发现 {len(submissions)} 份作业\n")

        # 加载模板
        template_content = get_template_content(base_path)

        # 开始评分
        print(f"🚀 {Colors.BOLD}开始评分...{Colors.END}")
        print(f"  并发数: {args.parallel if args.parallel > 1 else '顺序执行'}")

        results = []
        failed_count = 0

        if args.parallel > 1:
            # 并发评分
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallel) as executor:
                futures = []
                for student_id, file_path in submissions:
                    future = executor.submit(
                        grade_single_submission,
                        (student_id, file_path, grader, template_content, progress_manager)
                    )
                    futures.append(future)

                # 使用进度条
                with tqdm(total=len(futures), desc="评分进度") as pbar:
                    for future in concurrent.futures.as_completed(futures):
                        result = future.result()
                        if result:
                            results.append(result)
                            if not result['success']:
                                failed_count += 1
                        pbar.update(1)
        else:
            # 顺序评分
            with tqdm(total=len(submissions), desc="评分进度") as pbar:
                for student_id, file_path in submissions:
                    result = grade_single_submission(
                        (student_id, file_path, grader, template_content, progress_manager)
                    )
                    if result:
                        results.append(result)
                        if not result['success']:
                            failed_count += 1
                    pbar.update(1)

        success_count = len([r for r in results if r['success']])
        print(f"\n✓ 评分完成: 成功 {success_count} 份, 失败 {failed_count} 份\n")

        # 相似度检测
        similarity_results = []
        if not args.no_similarity and len(submissions) > 1:
            print(f"🔍 {Colors.BOLD}执行相似度检测...{Colors.END}")
            checker = SimilarityChecker(threshold=config.get('similarity_threshold', 0.85))

            # 准备代码内容
            code_pairs = []
            for student_id, file_path in submissions:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        code_pairs.append((student_id, f.read()))
                except:
                    continue

            # 检测相似度
            similarity_results = checker.find_similar_submissions(code_pairs)
            if similarity_results:
                print(f"  ⚠️  发现 {len(similarity_results)} 对相似作业")
                for pair in similarity_results[:5]:  # 只显示前5对
                    print(f"    - {pair['student1']} ↔ {pair['student2']}: "
                          f"{pair['similarity']:.1%} 相似度")

        # 统计分析
        print(f"\n📊 {Colors.BOLD}生成统计分析...{Colors.END}")
        analyzer = StatisticsAnalyzer(args.config)
        statistics = analyzer.analyze_scores(results)

        # 打印简要统计
        if statistics.get('count', 0) > 0:
            print(f"  平均分: {statistics['mean']}")
            print(f"  最高分: {statistics['max']}")
            print(f"  最低分: {statistics['min']}")
            print(f"  标准差: {statistics['stdev']}")

        # 导出结果
        print(f"\n💾 {Colors.BOLD}导出结果...{Colors.END}")
        exporter = ExportManager(args.config)

        export_formats = ['csv', 'excel', 'json', 'markdown'] if args.export == 'all' else [args.export]

        for fmt in export_formats:
            if fmt == 'csv':
                exporter.export_to_csv(results)
            elif fmt == 'excel':
                exporter.export_to_excel(results, similarity_results, statistics)
            elif fmt == 'json':
                exporter.export_to_json(results, {'config': config, 'statistics': statistics})
            elif fmt == 'markdown':
                exporter.export_to_markdown(results, statistics)

        # 生成统计报告和图表
        analyzer.generate_report(results)
        try:
            analyzer.plot_distribution(results)
        except:
            logger.warning("无法生成分布图（可能缺少matplotlib）")

        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ 所有任务完成！{Colors.END}")

    except FileNotFoundError as e:
        print(f"\n{Colors.RED}{Colors.BOLD}错误: {e}{Colors.END}")
        logger.critical(f"文件未找到: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}发生错误: {e}{Colors.END}")
        logger.critical("发生未知错误", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()