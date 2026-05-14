from __future__ import annotations

import ast
import difflib
import re


class SimilarityChecker:
    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def check_similarity(self, code1: str, code2: str) -> dict:
        text_similarity = difflib.SequenceMatcher(None, code1, code2).ratio()
        structure_similarity = self._structure_similarity(code1, code2)
        token_similarity = self._token_similarity(code1, code2)
        overall = text_similarity * 0.3 + structure_similarity * 0.4 + token_similarity * 0.3
        return {
            "text_similarity": round(text_similarity, 3),
            "structure_similarity": round(structure_similarity, 3),
            "token_similarity": round(token_similarity, 3),
            "overall_similarity": round(overall, 3),
            "is_suspicious": overall >= self.threshold,
        }

    def find_similar_submissions(self, submissions: list[tuple[str, str]]) -> list[dict]:
        pairs = []
        for i in range(len(submissions)):
            for j in range(i + 1, len(submissions)):
                student1, code1 = submissions[i]
                student2, code2 = submissions[j]
                similarity = self.check_similarity(code1, code2)
                if similarity["is_suspicious"]:
                    pairs.append({"student1": student1, "student2": student2, "similarity": similarity["overall_similarity"], "details": similarity})
        return sorted(pairs, key=lambda item: item["similarity"], reverse=True)

    def _structure_similarity(self, code1: str, code2: str) -> float:
        try:
            struct1 = [type(node).__name__ for node in ast.walk(ast.parse(code1))]
            struct2 = [type(node).__name__ for node in ast.walk(ast.parse(code2))]
            return difflib.SequenceMatcher(None, struct1, struct2).ratio()
        except SyntaxError:
            return difflib.SequenceMatcher(None, code1, code2).ratio()

    def _token_similarity(self, code1: str, code2: str) -> float:
        tokens1 = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", code1))
        tokens2 = set(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", code2))
        union = tokens1 | tokens2
        return len(tokens1 & tokens2) / len(union) if union else 0.0

