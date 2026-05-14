from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI

from .config import DeepSeekConfig
from .models import PreparedSubmission

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GradingOptions:
    max_retries: int = 3
    retry_delay: float = 5.0
    thinking: bool = False


class DeepSeekGrader:
    def __init__(self, config: DeepSeekConfig, options: Optional[GradingOptions] = None, client: Optional[OpenAI] = None):
        self.config = config
        self.options = options or GradingOptions()
        self.client = client or OpenAI(api_key=config.api_key, base_url=config.base_url, timeout=config.timeout)
        self.cache: dict[str, dict[str, Any]] = {}

    def grade(self, prepared: PreparedSubmission, answer_content: str) -> dict[str, Any]:
        content_hash = hashlib.sha256(prepared.content.encode("utf-8", errors="ignore")).hexdigest()
        if content_hash in self.cache:
            result = dict(self.cache[content_hash])
            result["from_cache"] = True
            return result

        last_error = ""
        for attempt in range(1, self.options.max_retries + 1):
            try:
                kwargs: dict[str, Any] = {
                    "model": self.config.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是严格、公正的 Python 课程助教。你必须只输出合法 JSON，不要输出 Markdown。",
                        },
                        {"role": "user", "content": build_prompt(prepared, answer_content)},
                    ],
                    "max_tokens": 700,
                    "response_format": {"type": "json_object"},
                    "extra_body": {"thinking": {"type": "enabled" if self.options.thinking else "disabled"}},
                }
                if self.options.thinking:
                    kwargs["reasoning_effort"] = "high"
                else:
                    kwargs["temperature"] = 0.0
                response = self.client.chat.completions.create(**kwargs)
                text = response.choices[0].message.content or ""
                result = parse_grading_json(text)
                self.cache[content_hash] = dict(result)
                return result
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                logger.warning("评分请求失败: student_id=%s attempt=%s error=%s", prepared.submission.student_id, attempt, last_error)
                if attempt < self.options.max_retries:
                    time.sleep(self.options.retry_delay)

        return {
            "score": 0,
            "comment": f"API请求失败: {last_error}",
            "issues": [last_error],
            "strengths": [],
            "confidence": "low",
            "success": False,
        }


def build_prompt(prepared: PreparedSubmission, answer_content: str) -> str:
    submission = prepared.submission
    return f"""
请对学生 Python 作业评分，并以 json object 返回。

评分约束：
- 分数必须是整数，建议只使用 100, 98, 97, 96, 95, 92, 90。
- 基础功能正确应为 92 分以上。
- 低于 95 分必须在 comment 中指出主要问题，20 字以内。
- 95 分及以上给简短鼓励性评语。
- issues 和 strengths 必须是字符串数组。
- confidence 必须是 high、medium 或 low。

期望 JSON 格式：
{{
  "score": 96,
  "comment": "功能正确，结构清晰",
  "issues": [],
  "strengths": ["实现完整"],
  "confidence": "high"
}}

学生信息：
- student_id: {submission.student_id}
- name: {submission.name_from_filename or "未知"}
- source_file: {submission.source_file.name}

参考答案：
```python
{answer_content}
```

学生提交：
```python
{prepared.content}
```
""".strip()


def parse_grading_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    data = json.loads(cleaned)
    score = max(0, min(100, int(data.get("score", 0))))
    issues = data.get("issues") or []
    strengths = data.get("strengths") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    if not isinstance(strengths, list):
        strengths = [str(strengths)]
    confidence = str(data.get("confidence", "medium")).lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"
    return {
        "score": score,
        "comment": str(data.get("comment", "")).strip(),
        "issues": [str(item) for item in issues],
        "strengths": [str(item) for item in strengths],
        "confidence": confidence,
        "success": True,
    }
