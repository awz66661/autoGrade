"""代码相似度检测模块"""
import difflib
import ast
import re
from typing import List, Tuple, Dict
from collections import defaultdict


class SimilarityChecker:
    """代码相似度检测器"""

    def __init__(self, threshold: float = 0.85):
        """
        初始化相似度检测器

        Args:
            threshold: 相似度阈值，超过此值视为可疑
        """
        self.threshold = threshold

    def check_similarity(self, code1: str, code2: str) -> Dict:
        """
        检测两段代码的相似度

        Args:
            code1: 第一段代码
            code2: 第二段代码

        Returns:
            相似度检测结果
        """
        # 多种相似度度量
        text_similarity = self._text_similarity(code1, code2)
        structure_similarity = self._structure_similarity(code1, code2)
        token_similarity = self._token_similarity(code1, code2)

        # 综合相似度（加权平均）
        overall_similarity = (
            text_similarity * 0.3 +
            structure_similarity * 0.4 +
            token_similarity * 0.3
        )

        return {
            'text_similarity': round(text_similarity, 3),
            'structure_similarity': round(structure_similarity, 3),
            'token_similarity': round(token_similarity, 3),
            'overall_similarity': round(overall_similarity, 3),
            'is_suspicious': overall_similarity >= self.threshold
        }

    def _text_similarity(self, code1: str, code2: str) -> float:
        """计算文本相似度（基于difflib）"""
        return difflib.SequenceMatcher(None, code1, code2).ratio()

    def _normalize_code(self, code: str) -> str:
        """标准化代码（去除空格、注释等）"""
        # 去除注释
        code = re.sub(r'#.*', '', code)
        code = re.sub(r'""".*?"""', '', code, flags=re.DOTALL)
        code = re.sub(r"'''.*?'''", '', code, flags=re.DOTALL)

        # 去除空行和多余空格
        lines = [line.strip() for line in code.split('\n') if line.strip()]
        return '\n'.join(lines)

    def _structure_similarity(self, code1: str, code2: str) -> float:
        """计算结构相似度（基于AST）"""
        try:
            tree1 = ast.parse(code1)
            tree2 = ast.parse(code2)

            structure1 = self._extract_structure(tree1)
            structure2 = self._extract_structure(tree2)

            return self._compare_structures(structure1, structure2)
        except:
            # 如果解析失败，返回文本相似度
            return self._text_similarity(code1, code2)

    def _extract_structure(self, tree: ast.AST) -> List[str]:
        """提取代码结构"""
        structure = []
        for node in ast.walk(tree):
            structure.append(type(node).__name__)
        return structure

    def _compare_structures(self, struct1: List[str], struct2: List[str]) -> float:
        """比较两个结构列表"""
        if not struct1 or not struct2:
            return 0.0

        matcher = difflib.SequenceMatcher(None, struct1, struct2)
        return matcher.ratio()

    def _token_similarity(self, code1: str, code2: str) -> float:
        """计算标记相似度（基于标识符和关键词）"""
        tokens1 = self._extract_tokens(code1)
        tokens2 = self._extract_tokens(code2)

        if not tokens1 or not tokens2:
            return 0.0

        # 计算Jaccard相似度
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)

        return len(intersection) / len(union) if union else 0.0

    def _extract_tokens(self, code: str) -> set:
        """提取代码中的标识符和关键词"""
        tokens = set()

        # 提取标识符（变量名、函数名等）
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
        tokens.update(identifiers)

        # 提取字符串字面量
        strings = re.findall(r'["\'].*?["\']', code)
        tokens.update(strings)

        return tokens

    def find_similar_submissions(self, submissions: List[Tuple[str, str]]) -> List[Dict]:
        """
        在多份作业中查找相似的提交

        Args:
            submissions: [(student_id, code), ...]

        Returns:
            相似作业对列表
        """
        similar_pairs = []

        for i in range(len(submissions)):
            for j in range(i + 1, len(submissions)):
                student1, code1 = submissions[i]
                student2, code2 = submissions[j]

                similarity = self.check_similarity(code1, code2)

                if similarity['is_suspicious']:
                    similar_pairs.append({
                        'student1': student1,
                        'student2': student2,
                        'similarity': similarity['overall_similarity'],
                        'details': similarity
                    })

        # 按相似度降序排序
        similar_pairs.sort(key=lambda x: x['similarity'], reverse=True)

        return similar_pairs

    def group_similar_submissions(self, submissions: List[Tuple[str, str]]) -> List[List[str]]:
        """
        将相似的作业分组

        Args:
            submissions: [(student_id, code), ...]

        Returns:
            相似作业组列表
        """
        groups = defaultdict(set)
        processed = set()

        for i in range(len(submissions)):
            if i in processed:
                continue

            student1, code1 = submissions[i]
            group_id = i
            groups[group_id].add(student1)
            processed.add(i)

            for j in range(i + 1, len(submissions)):
                if j in processed:
                    continue

                student2, code2 = submissions[j]
                similarity = self.check_similarity(code1, code2)

                if similarity['is_suspicious']:
                    groups[group_id].add(student2)
                    processed.add(j)

        # 转换为列表格式
        return [list(group) for group in groups.values() if len(group) > 1]