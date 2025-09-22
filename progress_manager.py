"""进度管理和断点续批模块"""
import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Set
from datetime import datetime


class ProgressManager:
    """进度管理器，支持断点续批"""

    def __init__(self, progress_file: str = "grading_progress.json"):
        """
        初始化进度管理器

        Args:
            progress_file: 进度文件路径
        """
        self.progress_file = Path(progress_file)
        self.progress_data = self._load_progress()

    def _load_progress(self) -> Dict:
        """加载进度文件"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return self._init_progress()
        return self._init_progress()

    def _init_progress(self) -> Dict:
        """初始化进度数据"""
        return {
            'completed': [],
            'failed': [],
            'in_progress': None,
            'timestamp': None,
            'session_id': None,
            'statistics': {}
        }

    def save_progress(self):
        """保存进度到文件"""
        self.progress_data['timestamp'] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress_data, f, ensure_ascii=False, indent=2)

    def mark_completed(self, student_id: str, result: Dict):
        """标记学生作业为已完成"""
        self.progress_data['completed'].append({
            'student_id': student_id,
            'score': result.get('score', 0),
            'comment': result.get('comment', ''),
            'timestamp': datetime.now().isoformat()
        })
        self.save_progress()

    def mark_failed(self, student_id: str, error: str):
        """标记学生作业为失败"""
        self.progress_data['failed'].append({
            'student_id': student_id,
            'error': error,
            'timestamp': datetime.now().isoformat()
        })
        self.save_progress()

    def mark_in_progress(self, student_id: str):
        """标记正在处理的学生作业"""
        self.progress_data['in_progress'] = student_id
        self.save_progress()

    def clear_in_progress(self):
        """清除正在处理标记"""
        self.progress_data['in_progress'] = None
        self.save_progress()

    def get_completed_ids(self) -> Set[str]:
        """获取已完成的学生ID集合"""
        return {item['student_id'] for item in self.progress_data['completed']}

    def get_failed_ids(self) -> Set[str]:
        """获取失败的学生ID集合"""
        return {item['student_id'] for item in self.progress_data['failed']}

    def should_skip(self, student_id: str) -> bool:
        """判断是否应该跳过该学生（已完成）"""
        return student_id in self.get_completed_ids()

    def should_retry(self, student_id: str) -> bool:
        """判断是否应该重试该学生（失败的）"""
        return student_id in self.get_failed_ids()

    def reset_failed(self):
        """重置失败列表，准备重试"""
        self.progress_data['failed'] = []
        self.save_progress()

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            'total_completed': len(self.progress_data['completed']),
            'total_failed': len(self.progress_data['failed']),
            'last_updated': self.progress_data.get('timestamp', 'N/A'),
            'in_progress': self.progress_data.get('in_progress', None)
        }

    def reset(self):
        """重置进度"""
        self.progress_data = self._init_progress()
        self.save_progress()


class CacheManager:
    """缓存管理器"""

    def __init__(self, cache_file: str = "grading_cache.pkl"):
        """
        初始化缓存管理器

        Args:
            cache_file: 缓存文件路径
        """
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict:
        """加载缓存文件"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
            except:
                return {}
        return {}

    def save_cache(self):
        """保存缓存到文件"""
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.cache, f)

    def get(self, key: str) -> Optional[Dict]:
        """获取缓存项"""
        return self.cache.get(key)

    def set(self, key: str, value: Dict):
        """设置缓存项"""
        self.cache[key] = value
        self.save_cache()

    def clear(self):
        """清空缓存"""
        self.cache = {}
        self.save_cache()

    def remove(self, key: str):
        """删除特定缓存项"""
        if key in self.cache:
            del self.cache[key]
            self.save_cache()