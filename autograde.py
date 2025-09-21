import os
import json
import time
import logging
from openai import OpenAI
from pathlib import Path
from tqdm import tqdm

# --- 终端颜色美化 ---
# 使用 ANSI 转义序列为终端输出添加颜色
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

# --- 日志记录配置 ---
# 将详细日志记录到文件，只在终端显示警告及以上级别的信息
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 文件处理器，记录所有 INFO 级别及以上的日志
file_handler = logging.FileHandler("grading.log", mode='w', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# 控制台处理器，只显示 WARNING 级别及以上的日志
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.WARNING)
console_formatter = logging.Formatter(f'{Colors.YELLOW}%(levelname)s{Colors.END}: %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


# --- 配置文件处理 ---
def load_config(config_path='config.json'):
    """加载并验证配置文件。"""
    path = Path(config_path)
    if not path.exists():
        logger.critical(f"配置文件未找到: {config_path}")
        default_config = {
            "base_path": "./homework", "api_key": "YOUR_API_KEY",
            "base_url": "YOUR_API_BASE_URL", "model": "gpt-4",
            "request_timeout": 60, "max_retries": 3, "retry_delay": 5
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        print(f"{Colors.YELLOW}提示: 未找到配置文件，已在 {config_path} 创建模板，请填写后重新运行。{Colors.END}")
        raise FileNotFoundError(f"配置文件未找到: {config_path}")

    with open(path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    required_keys = ['base_path', 'api_key', 'base_url', 'model']
    if not all(key in config for key in required_keys):
        logger.critical(f"配置文件缺少关键字段，请确保包含: {required_keys}")
        raise ValueError("配置文件内容不完整。")
    
    config.setdefault('request_timeout', 60)
    config.setdefault('max_retries', 3)
    config.setdefault('retry_delay', 5)
    return config

# --- 文件处理 ---
def get_submissions(base_path):
    """获取所有学生提交的 .py 文件列表。"""
    submissions_dir = Path(base_path) / 'submissions'
    if not submissions_dir.is_dir():
        logger.critical(f"未找到 submissions 文件夹，或该路径不是一个目录: {submissions_dir}")
        raise FileNotFoundError(f"未找到 submissions 文件夹: {submissions_dir}")
    
    submissions = []
    py_files = list(submissions_dir.glob('*.py'))

    if not py_files:
        logger.warning("submissions 文件夹中没有找到任何 .py 文件。")
        return []

    for file_path in py_files:
        if '_' in file_path.name:
            student_id = file_path.name.split('_')[0]
        else:
            student_id = file_path.stem
        
        if file_path.stat().st_size == 0:
            logger.warning(f"文件为空，已跳过: {file_path.name}")
            continue
            
        submissions.append((student_id, file_path))
    return submissions

def get_template_content(base_path):
    """读取参考答案模板文件内容。"""
    template_path = Path(base_path) / 'template.py'
    if not template_path.is_file():
        logger.critical(f"未找到 template.py 文件: {template_path}")
        raise FileNotFoundError(f"未找到 template.py 文件: {template_path}")
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.critical(f"读取模板文件失败: {e}")
        raise

# --- 大模型 API 调用 ---
def grade_submission(student_id, submission_content, template_content, client, model, max_retries, retry_delay):
    """调用大模型 API 对单个学生的提交进行评分，包含重试逻辑。"""
    prompt = f"""
    ### 角色与任务 ###
    你是一位经验丰富的Python课程助教，你的任务是根据提供的参考答案和评分标准，客观、公正地为学生的Python代码作业评分。
    ### 评分标准 ###
    1.  **功能实现 (90-100分)，其中95-100分的概率为80%**
        - **90-91分**: 完成了题目的核心功能要求，但是代码逻辑有一定问题。
        - **92-94分**: 基本完成了题目的核心功能要求。
        - **95-100分**: 代码逻辑正确，能够处理常规输入。
    2.  **代码质量与边界情况 (影响最终分数)**
        - **98分及以上**: 除了功能正确，代码还必须能优雅地处理各种边界情况（例如：空输入、异常输入等），并在必要时提供错误处理或异常捕获。
        - **95-97分**: 功能基本正确，但在边界情况处理上有一定欠缺，或者代码风格不够优雅。
        - **代码风格**: 代码风格和格式问题（如输出格式的小瑕疵）不作为主要扣分项，但可以在评语中提及。
    3.  **评语要求**
        - **低于95分**: 必须提供简明扼要的错误点评或改进建议（20字以内）。
        - **95分及以上**: 提供一句鼓励性的简要评语。
    ### 作业信息 ###
    - **学生学号**: {student_id}
    - **参考答案**:
    ```python
    {template_content}
    ```
    - **学生提交的代码**:
    ```python
    {submission_content}
    ```
    ### 评分步骤 ###
    1.  **理解参考答案**: 首先，请仔细分析参考答案的实现逻辑和关键点。
    2.  **比对学生代码**: 将学生提交的代码与参考答案进行逻辑比对。评估其是否完成了核心功能。
    3.  **检查边界处理**: 评估学生代码是否考虑了必要的边界情况。
    4.  **确定分数和评语**: 根据上述分析和评分标准，给出一个整数分数和相应的评语。
    ### 输出格式 ###
    请严格按照 "学号-分数-评语" 的格式返回结果，不要包含任何其他解释、说明或多余的字符。
    例如: "S001-92-注意列表为空时的处理" 或 "S002-98-代码逻辑清晰，考虑了边界情况"。
    """
    
    for attempt in range(max_retries):
        try:
            # 这条详细日志只会写入文件，不会显示在控制台
            logger.info(f"正在评分 (尝试 {attempt + 1}/{max_retries}): 学号 {student_id}")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位严格且专业的Python课程助教。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150, temperature=0.0
            )
            
            result = response.choices[0].message.content.strip()
            parts = result.split('-')
            if len(parts) >= 3 and parts[1].isdigit(): # 评语中可能包含'-'，所以用>=3
                return result
            else:
                logger.warning(f"学号 {student_id} 的返回格式不规范: '{result}'。将记录为原始返回。")
                return f"{student_id}-0-返回格式错误: {result}"

        except Exception as e:
            logger.error(f"学号 {student_id} 的评分请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            else:
                return f"{student_id}-0-API请求失败: {str(e)}"
    return f"{student_id}-0-评分失败，已达最大重试次数"

# --- 主流程 ---
def main():
    """主执行函数"""
    print(f"{Colors.BOLD}{Colors.BLUE}=== 自动 Python 作业评分脚本 ===")
    print(f"------------------------------------{Colors.END}")

    try:
        # --- 1. 初始化 ---
        print(f"⚙️  {Colors.BOLD}第一步: 初始化与环境检查{Colors.END}")
        config = load_config()
        base_path = config['base_path']
        print(f"  - 配置文件加载成功。")

        client = OpenAI(
            api_key=config['api_key'], base_url=config['base_url'],
            timeout=config['request_timeout']
        )
        print(f"  - 大模型客户端初始化成功。")

        submissions = get_submissions(base_path)
        if not submissions:
            print(f"\n{Colors.YELLOW}在 'submissions' 文件夹中未发现作业文件，程序退出。{Colors.END}")
            return
        print(f"  - {Colors.GREEN}发现 {len(submissions)} 份待批改的作业。{Colors.END}")

        template_content = get_template_content(base_path)
        print(f"  - 参考答案模板加载成功。")

        # --- 2. 开始评分 ---
        print(f"\n🚀 {Colors.BOLD}第二步: 开始执行评分任务{Colors.END}")
        results_file = Path(base_path) / 'results.txt'
        error_file = Path(base_path) / 'results_error.txt'
        
        success_count = 0
        error_count = 0
        
        with open(results_file, 'w', encoding='utf-8') as f_results, \
             open(error_file, 'w', encoding='utf-8') as f_errors, \
             tqdm(total=len(submissions), desc=" ‎ ‎ ‎ overall progress", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}") as pbar:

            for student_id, file_path in submissions:
                pbar.set_postfix_str(f"正在处理: {student_id}", refresh=True)
                
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as submission_file:
                        submission_content = submission_file.read()
                except Exception as e:
                    logger.error(f"读取学生 {student_id} 的文件失败: {e}")
                    f_errors.write(f"{student_id}-0-无法读取提交文件: {e}\n")
                    error_count += 1
                    pbar.update(1)
                    continue

                result = grade_submission(
                    student_id, submission_content, template_content, client, 
                    config['model'], config['max_retries'], config['retry_delay']
                )
                
                if "-0-" in result:
                    f_errors.write(result + '\n')
                    error_count += 1
                else:
                    f_results.write(result + '\n')
                    success_count += 1
                
                pbar.update(1)

        # --- 3. 结果总结 ---
        print(f"\n🏁 {Colors.BOLD}第三步: 评分完成！{Colors.END}")
        print(f"------------------------------------")
        print(f"  - {Colors.GREEN}成功评分: {success_count} 份{Colors.END}")
        print(f"  - {Colors.RED}失败/异常: {error_count} 份{Colors.END}")
        print(f"  - {Colors.GREEN}✔{Colors.END} 成功结果已保存至: {Colors.BOLD}{results_file}{Colors.END}")
        if error_count > 0:
            print(f"  - {Colors.RED}✘{Colors.END} 失败记录已保存至: {Colors.BOLD}{error_file}{Colors.END}")
        print(f"  - 详细运行日志请查看: {Colors.BOLD}grading.log{Colors.END}")

    except (FileNotFoundError, ValueError) as e:
        print(f"\n{Colors.RED}{Colors.BOLD}致命错误: {e}{Colors.END}")
        print(f"请检查配置文件或文件路径后重试。")
    except Exception as e:
        print(f"\n{Colors.RED}{Colors.BOLD}发生未知错误: {e}{Colors.END}")
        logger.critical("发生未知错误", exc_info=True)

if __name__ == "__main__":
    main()