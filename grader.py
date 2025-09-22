"""评分核心模块"""
import time
import logging
import hashlib
import json
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)


class GradingCriteria:
    """评分标准配置类"""

    def __init__(self, criteria_file: Optional[str] = None):
        """
        初始化评分标准

        Args:
            criteria_file: 评分标准配置文件路径
        """
        self.criteria = self._load_default_criteria()
        if criteria_file and Path(criteria_file).exists():
            self.load_from_file(criteria_file)

    def _load_default_criteria(self) -> Dict:
        """加载默认评分标准"""
        return {
            "score_ranges": {
                "excellent": {"min": 97, "max": 100, "probability": 0.35},
                "very_good": {"min": 95, "max": 96, "probability": 0.40},
                "good": {"min": 92, "max": 94, "probability": 0.20},
                "pass": {"min": 90, "max": 91, "probability": 0.05}
            },
            "deduction_items": {
                "no_error_handling": -3,
                "poor_code_style": -2,
                "missing_edge_cases": -5,
                "inefficient_algorithm": -3
            },
            "bonus_items": {
                "elegant_solution": 2,
                "comprehensive_error_handling": 3,
                "excellent_documentation": 2
            }
        }

    def load_from_file(self, filepath: str):
        """从文件加载评分标准"""
        with open(filepath, 'r', encoding='utf-8') as f:
            custom_criteria = json.load(f)
            self.criteria.update(custom_criteria)

    def get_prompt_template(self) -> str:
        """获取评分提示词模板"""
        return f"""
        ### 角色与任务 ###
        你是一位经验丰富的Python课程助教，你的任务是根据提供的参考答案和评分标准，客观、公正地为学生的Python代码作业评分。

        ### 评分标准 ###
        基于以下配置的评分标准：
        {json.dumps(self.criteria, ensure_ascii=False, indent=2)}

        ### 评分要求 ###
        1. 基础功能实现正确即可获得92分以上
        2. 代码质量、边界情况处理、风格规范可获得额外加分
        3. 根据扣分项和加分项调整最终得分
        4. 优先给予高分，平均分应在96左右
        5. 分数必须为以下固定值之一：100, 98, 97, 96, 95, 92, 90
        6. 低于95分必须提供简明扼要的错误点评（20字以内）
        7. 95分及以上提供鼓励性评语
        """


class Grader:
    """评分器类"""

    def __init__(self, client: OpenAI, model: str, criteria: Optional[GradingCriteria] = None):
        """
        初始化评分器

        Args:
            client: OpenAI客户端
            model: 使用的模型名称
            criteria: 评分标准
        """
        self.client = client
        self.model = model
        self.criteria = criteria or GradingCriteria()
        self.cache = {}  # 缓存已评分的结果

    def _get_content_hash(self, content: str) -> str:
        """计算内容哈希值用于缓存"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def grade(self,
              student_id: str,
              submission_content: str,
              template_content: str,
              max_retries: int = 3,
              retry_delay: int = 5,
              use_cache: bool = True) -> Dict:
        """
        对单个学生作业进行评分

        Args:
            student_id: 学生ID
            submission_content: 学生提交的代码
            template_content: 参考答案
            max_retries: 最大重试次数
            retry_delay: 重试延迟（秒）
            use_cache: 是否使用缓存

        Returns:
            评分结果字典
        """
        # 检查缓存
        content_hash = self._get_content_hash(submission_content)
        if use_cache and content_hash in self.cache:
            logger.info(f"使用缓存结果: 学号 {student_id}")
            cached_result = self.cache[content_hash].copy()
            cached_result['student_id'] = student_id
            cached_result['from_cache'] = True
            return cached_result

        prompt = self._build_prompt(student_id, submission_content, template_content)

        for attempt in range(max_retries):
            try:
                logger.info(f"正在评分 (尝试 {attempt + 1}/{max_retries}): 学号 {student_id}")

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一位严格且专业的Python课程助教。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=150,
                    temperature=0.0
                )

                result = self._parse_response(response.choices[0].message.content.strip(), student_id)

                # 缓存结果
                if use_cache:
                    self.cache[content_hash] = result.copy()

                return result

            except Exception as e:
                logger.error(f"学号 {student_id} 的评分请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    return {
                        'student_id': student_id,
                        'score': 0,
                        'comment': f'API请求失败: {str(e)}',
                        'success': False
                    }

        return {
            'student_id': student_id,
            'score': 0,
            'comment': '评分失败，已达最大重试次数',
            'success': False
        }

    def _build_prompt(self, student_id: str, submission_content: str, template_content: str) -> str:
        """构建评分提示词"""
        base_prompt = self.criteria.get_prompt_template()
        return f"""
        {base_prompt}

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

        ### 输出格式 ###
        请严格按照 "学号-分数-评语" 的格式返回结果。
        例如: "S001-92-注意列表为空时的处理"
        """

    def _parse_response(self, response: str, student_id: str) -> Dict:
        """解析API响应"""
        result = response.strip()
        parts = result.split('-')

        if len(parts) >= 3 and parts[1].isdigit():
            return {
                'student_id': student_id,
                'score': int(parts[1]),
                'comment': '-'.join(parts[2:]),
                'success': True,
                'raw_response': result
            }
        else:
            logger.warning(f"学号 {student_id} 的返回格式不规范: '{result}'")
            return {
                'student_id': student_id,
                'score': 0,
                'comment': f'返回格式错误: {result}',
                'success': False,
                'raw_response': result
            }