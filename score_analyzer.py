"""统计分析模块"""
import os
import json
import statistics
from typing import List, Dict, Tuple
from collections import Counter
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm


class StatisticsAnalyzer:
    """统计分析器"""

    def __init__(self, config_file: str = 'config.json'):
        """初始化统计分析器"""
        # 设置中文字体
        try:
            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
        except:
            pass

        # 设置reports目录
        self.reports_path = self._get_reports_path(config_file)

    def analyze_scores(self, results: List[Dict]) -> Dict:
        """
        分析评分结果

        Args:
            results: 评分结果列表

        Returns:
            统计分析结果
        """
        scores = [r['score'] for r in results if r.get('success', False)]

        if not scores:
            return {
                'count': 0,
                'message': '没有有效的评分数据'
            }

        return {
            'count': len(scores),
            'mean': round(statistics.mean(scores), 2),
            'median': statistics.median(scores),
            'mode': statistics.mode(scores) if len(scores) > 1 else scores[0],
            'stdev': round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
            'min': min(scores),
            'max': max(scores),
            'range': max(scores) - min(scores),
            'percentiles': self._calculate_percentiles(scores),
            'distribution': self._calculate_distribution(scores),
            'grade_distribution': self._calculate_grade_distribution(scores)
        }

    def _calculate_percentiles(self, scores: List[int]) -> Dict:
        """计算百分位数"""
        if not scores:
            return {}

        sorted_scores = sorted(scores)
        n = len(sorted_scores)

        return {
            '25th': sorted_scores[n // 4] if n >= 4 else sorted_scores[0],
            '50th': sorted_scores[n // 2],
            '75th': sorted_scores[3 * n // 4] if n >= 4 else sorted_scores[-1]
        }

    def _calculate_distribution(self, scores: List[int]) -> Dict:
        """计算分数分布"""
        distribution = Counter()

        for score in scores:
            if score >= 95:
                distribution['95-100'] += 1
            elif score >= 90:
                distribution['90-94'] += 1
            elif score >= 85:
                distribution['85-89'] += 1
            elif score >= 80:
                distribution['80-84'] += 1
            elif score >= 70:
                distribution['70-79'] += 1
            elif score >= 60:
                distribution['60-69'] += 1
            else:
                distribution['<60'] += 1

        return dict(distribution)

    def _calculate_grade_distribution(self, scores: List[int]) -> Dict:
        """计算等级分布"""
        grades = Counter()

        for score in scores:
            if score >= 95:
                grades['优秀'] += 1
            elif score >= 90:
                grades['良好'] += 1
            elif score >= 80:
                grades['中等'] += 1
            elif score >= 60:
                grades['及格'] += 1
            else:
                grades['不及格'] += 1

        total = len(scores)
        return {
            grade: {
                'count': count,
                'percentage': round(100 * count / total, 1)
            }
            for grade, count in grades.items()
        }

    def generate_report(self, results: List[Dict], output_file: str = None):
        """
        生成统计报告

        Args:
            results: 评分结果列表
            output_file: 输出文件路径
        """
        stats = self.analyze_scores(results)

        if stats.get('count', 0) == 0:
            report = "没有有效的评分数据\n"
        else:
            report = f"""
=====================================
        评分统计报告
=====================================

基本统计信息：
-----------------
总人数：{stats['count']}
平均分：{stats['mean']}
中位数：{stats['median']}
众数：{stats['mode']}
标准差：{stats['stdev']}
最高分：{stats['max']}
最低分：{stats['min']}
分数范围：{stats['range']}

百分位数：
-----------------
25%分位：{stats['percentiles'].get('25th', 'N/A')}
50%分位：{stats['percentiles'].get('50th', 'N/A')}
75%分位：{stats['percentiles'].get('75th', 'N/A')}

分数分布：
-----------------"""

            for range_str, count in sorted(stats['distribution'].items(), reverse=True):
                percentage = round(100 * count / stats['count'], 1)
                bar = '█' * int(percentage / 2)
                report += f"\n{range_str:8} : {count:3}人 ({percentage:5.1f}%) {bar}"

            report += "\n\n等级分布：\n-----------------"
            for grade, info in stats['grade_distribution'].items():
                report += f"\n{grade:6} : {info['count']:3}人 ({info['percentage']:5.1f}%)"

            # 添加异常检测
            report += "\n\n异常检测：\n-----------------"
            low_scores = [r for r in results if r.get('score', 0) < 60 and r.get('success', False)]
            if low_scores:
                report += f"\n低于60分的学生：{len(low_scores)}人"
                for r in low_scores[:5]:  # 只显示前5个
                    report += f"\n  - {r['student_id']}: {r['score']}分 ({r.get('comment', 'N/A')})"

        if output_file is None:
            output_file = 'statistics_report.txt'

        # 确保使用reports目录
        output_file = os.path.join(self.reports_path, os.path.basename(output_file))
        # 转换为绝对路径以便显示
        abs_output_file = os.path.abspath(output_file)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"统计报告已生成：{abs_output_file}")
        return stats

    def plot_distribution(self, results: List[Dict], output_file: str = None):
        """
        绘制分数分布图

        Args:
            results: 评分结果列表
            output_file: 输出图片文件路径
        """
        scores = [r['score'] for r in results if r.get('success', False)]

        if not scores:
            print("没有有效的评分数据，无法生成图表")
            return

        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # 1. 直方图
        axes[0, 0].hist(scores, bins=20, edgecolor='black', alpha=0.7)
        axes[0, 0].set_xlabel('分数')
        axes[0, 0].set_ylabel('人数')
        axes[0, 0].set_title('分数分布直方图')
        axes[0, 0].grid(True, alpha=0.3)

        # 2. 箱线图
        axes[0, 1].boxplot(scores, vert=True)
        axes[0, 1].set_ylabel('分数')
        axes[0, 1].set_title('分数箱线图')
        axes[0, 1].grid(True, alpha=0.3)

        # 3. 等级分布饼图
        stats = self.analyze_scores(results)
        grade_dist = stats['grade_distribution']
        if grade_dist:
            labels = list(grade_dist.keys())
            sizes = [info['count'] for info in grade_dist.values()]
            colors = ['#2ecc71', '#3498db', '#f39c12', '#e67e22', '#e74c3c'][:len(labels)]

            axes[1, 0].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                          shadow=True, startangle=90)
            axes[1, 0].set_title('等级分布')

        # 4. 累积分布
        sorted_scores = sorted(scores)
        cumulative = list(range(1, len(sorted_scores) + 1))
        cumulative_pct = [100 * i / len(sorted_scores) for i in cumulative]

        axes[1, 1].plot(sorted_scores, cumulative_pct, marker='o', markersize=3)
        axes[1, 1].set_xlabel('分数')
        axes[1, 1].set_ylabel('累积百分比 (%)')
        axes[1, 1].set_title('累积分布曲线')
        axes[1, 1].grid(True, alpha=0.3)

        plt.suptitle(f'评分统计分析 (n={len(scores)})', fontsize=16, fontweight='bold')
        plt.tight_layout()

        if output_file is None:
            output_file = 'score_distribution.png'

        # 确保使用reports目录
        output_file = os.path.join(self.reports_path, os.path.basename(output_file))
        # 转换为绝对路径以便显示
        abs_output_file = os.path.abspath(output_file)

        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"分布图已保存：{abs_output_file}")

    def find_outliers(self, results: List[Dict], threshold: float = 1.5) -> List[Dict]:
        """
        查找异常分数

        Args:
            results: 评分结果列表
            threshold: IQR倍数阈值

        Returns:
            异常分数列表
        """
        scores = [r['score'] for r in results if r.get('success', False)]

        if len(scores) < 4:
            return []

        sorted_scores = sorted(scores)
        n = len(sorted_scores)

        q1 = sorted_scores[n // 4]
        q3 = sorted_scores[3 * n // 4]
        iqr = q3 - q1

        lower_bound = q1 - threshold * iqr
        upper_bound = q3 + threshold * iqr

        outliers = []
        for r in results:
            if r.get('success', False):
                score = r['score']
                if score < lower_bound or score > upper_bound:
                    outliers.append({
                        'student_id': r['student_id'],
                        'score': score,
                        'comment': r.get('comment', ''),
                        'type': 'low' if score < lower_bound else 'high'
                    })

        return outliers

    def _get_reports_path(self, config_file: str) -> str:
        """获取reports目录路径"""
        import json
        import os
        
        try:
            # 确保使用绝对路径读取配置文件
            if not os.path.isabs(config_file):
                config_file = os.path.abspath(config_file)
                
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                base_path = config.get('base_path', '.')
                
            # 确保 base_path 是绝对路径
            if not os.path.isabs(base_path):
                base_path = os.path.abspath(base_path)
                
            reports_path = os.path.join(base_path, 'reports')
            
        except Exception as e:
            print(f"警告: 无法读取配置文件 {config_file}: {e}")
            reports_path = os.path.abspath('./reports')

        # 确保目录存在
        os.makedirs(reports_path, exist_ok=True)
        return reports_path