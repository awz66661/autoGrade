"""导出工具模块"""
import csv
import json
import os
from typing import List, Dict
from pathlib import Path
import pandas as pd
from datetime import datetime


class ExportManager:
    """导出管理器"""

    def __init__(self, config_file: str = 'config.json'):
        """初始化导出管理器"""
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.base_path = self._load_base_path(config_file)

    def _load_base_path(self, config_file: str) -> str:
        """从配置文件中加载base_path并创建reports目录"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                base_path = config.get('base_path', '.')
                # 创建reports目录
                reports_path = os.path.join(base_path, 'reports')
                os.makedirs(reports_path, exist_ok=True)
                return reports_path
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # 如果配置文件不存在或无法解析，使用当前目录下的reports
            reports_path = './reports'
            os.makedirs(reports_path, exist_ok=True)
            return reports_path

    def export_to_csv(self, results: List[Dict], output_file: str = None) -> str:
        """
        导出结果到CSV文件

        Args:
            results: 评分结果列表
            output_file: 输出文件路径

        Returns:
            输出文件路径
        """
        if output_file is None:
            output_file = f'grading_results_{self.timestamp}.csv'

        # 确保使用base_path
        output_file = os.path.join(self.base_path, os.path.basename(output_file))

        with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
            if not results:
                f.write("没有数据\n")
                return output_file

            # 确定所有可能的字段
            all_fields = set()
            for r in results:
                all_fields.update(r.keys())

            fieldnames = ['student_id', 'score', 'comment', 'success']
            # 添加其他字段
            for field in sorted(all_fields):
                if field not in fieldnames:
                    fieldnames.append(field)

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                writer.writerow(result)

        print(f"CSV文件已导出：{output_file}")
        return output_file

    def export_to_excel(self, results: List[Dict],
                       similarity_results: List[Dict] = None,
                       statistics: Dict = None,
                       output_file: str = None) -> str:
        """
        导出结果到Excel文件（多个工作表）

        Args:
            results: 评分结果列表
            similarity_results: 相似度检测结果
            statistics: 统计信息
            output_file: 输出文件路径

        Returns:
            输出文件路径
        """
        if output_file is None:
            output_file = f'grading_report_{self.timestamp}.xlsx'

        # 确保使用base_path
        output_file = os.path.join(self.base_path, os.path.basename(output_file))

        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # 1. 评分结果表
            if results:
                df_results = pd.DataFrame(results)
                # 重新排列列顺序
                priority_cols = ['student_id', 'score', 'comment', 'success']
                other_cols = [col for col in df_results.columns if col not in priority_cols]
                df_results = df_results[priority_cols + other_cols]
                df_results.to_excel(writer, sheet_name='评分结果', index=False)

            # 2. 相似度检测表
            if similarity_results:
                df_similarity = pd.DataFrame(similarity_results)
                df_similarity.to_excel(writer, sheet_name='相似度检测', index=False)

            # 3. 统计信息表
            if statistics:
                # 转换统计信息为适合Excel的格式
                stat_rows = []
                for key, value in statistics.items():
                    if isinstance(value, dict):
                        for sub_key, sub_value in value.items():
                            stat_rows.append({
                                '类别': key,
                                '指标': sub_key,
                                '值': str(sub_value)
                            })
                    else:
                        stat_rows.append({
                            '类别': '基本统计',
                            '指标': key,
                            '值': str(value)
                        })

                df_stats = pd.DataFrame(stat_rows)
                df_stats.to_excel(writer, sheet_name='统计分析', index=False)

            # 4. 等级汇总表
            if results:
                grade_summary = self._create_grade_summary(results)
                df_grade = pd.DataFrame(grade_summary)
                df_grade.to_excel(writer, sheet_name='等级汇总', index=False)

        print(f"Excel文件已导出：{output_file}")
        return output_file

    def _create_grade_summary(self, results: List[Dict]) -> List[Dict]:
        """创建等级汇总"""
        grade_summary = []
        grade_ranges = [
            ('优秀', 90, 100),
            ('良好', 80, 89),
            ('中等', 70, 79),
            ('及格', 60, 69),
            ('不及格', 0, 59)
        ]

        for grade_name, min_score, max_score in grade_ranges:
            students = [
                r['student_id'] for r in results
                if r.get('success', False) and min_score <= r['score'] <= max_score
            ]

            if students:
                grade_summary.append({
                    '等级': grade_name,
                    '分数范围': f'{min_score}-{max_score}',
                    '人数': len(students),
                    '学生列表': ', '.join(students[:10])  # 只显示前10个
                })

        return grade_summary

    def export_to_json(self, results: List[Dict],
                      metadata: Dict = None,
                      output_file: str = None) -> str:
        """
        导出结果到JSON文件

        Args:
            results: 评分结果列表
            metadata: 元数据
            output_file: 输出文件路径

        Returns:
            输出文件路径
        """
        if output_file is None:
            output_file = f'grading_data_{self.timestamp}.json'

        # 确保使用base_path
        output_file = os.path.join(self.base_path, os.path.basename(output_file))

        export_data = {
            'timestamp': self.timestamp,
            'metadata': metadata or {},
            'results': results,
            'summary': {
                'total': len(results),
                'successful': len([r for r in results if r.get('success', False)]),
                'failed': len([r for r in results if not r.get('success', True)])
            }
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"JSON文件已导出：{output_file}")
        return output_file

    def export_to_markdown(self, results: List[Dict],
                          statistics: Dict = None,
                          output_file: str = None) -> str:
        """
        导出结果到Markdown文件

        Args:
            results: 评分结果列表
            statistics: 统计信息
            output_file: 输出文件路径

        Returns:
            输出文件路径
        """
        if output_file is None:
            output_file = f'grading_report_{self.timestamp}.md'

        # 确保使用base_path
        output_file = os.path.join(self.base_path, os.path.basename(output_file))

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 作业评分报告\n\n")
            f.write(f"生成时间：{self.timestamp}\n\n")

            # 统计信息
            if statistics:
                f.write("## 统计概要\n\n")
                f.write("| 指标 | 值 |\n")
                f.write("|------|----|\n")
                for key, value in statistics.items():
                    if not isinstance(value, dict):
                        f.write(f"| {key} | {value} |\n")

            # 评分结果表
            f.write("\n## 评分详情\n\n")
            f.write("| 学号 | 分数 | 评语 | 状态 |\n")
            f.write("|------|------|------|------|\n")

            for r in sorted(results, key=lambda x: x.get('score', 0), reverse=True):
                status = "✓" if r.get('success', False) else "✗"
                f.write(f"| {r['student_id']} | {r.get('score', 0)} | "
                       f"{r.get('comment', 'N/A')} | {status} |\n")

            # 等级分布
            if statistics and 'grade_distribution' in statistics:
                f.write("\n## 等级分布\n\n")
                f.write("| 等级 | 人数 | 百分比 |\n")
                f.write("|------|------|--------|\n")
                for grade, info in statistics['grade_distribution'].items():
                    f.write(f"| {grade} | {info['count']} | {info['percentage']}% |\n")

        print(f"Markdown报告已导出：{output_file}")
        return output_file