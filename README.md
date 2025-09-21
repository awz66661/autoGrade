# AutoGrade Python 助教项目

## 项目简介

AutoGrade 是一个基于大语言模型的 Python 作业自动评分工具，适用于高校编程课程助教自动批改学生作业。

## 主要功能
- 自动读取学生提交的 Python 文件
- 支持自定义评分标准
- 通过大模型 API 自动评分
- 评分进度条显示
- 结果自动保存到 `results.txt`
- 兼容中文编码

## 项目结构
```
├── autograde.py         # 主程序
├── config.json          # 配置文件（API密钥、模型等）
```

## 使用方法

### 1. 环境准备
- Python 3.8 及以上
- 推荐使用虚拟环境（venv）
- 安装依赖：
  ```bash
  pip install openai tqdm
  ```

### 2. 配置文件
编辑 `config.json`，示例：
```json
{
    "base_path": "C:/Path/to/your/project",
    "api_key": "你的API密钥",
    "base_url": "https://api.deepseek.com/v1", // 请根据实际使用的模型服务填写
    "model": "deepseek-chat" // 请根据实际使用的模型服务填写
}
```
- `base_path`：工作文件夹路径，需包含 `submissions` 子文件夹（存放学生作业）和 `template.py` 标准答案文件。
- `api_key`、`base_url`、`model`：请根据实际使用的模型服务填写。

### 3. 文件组织
- `submissions/` 文件夹下每个学生的作业文件命名格式建议为 `学号_其他信息.py`，如 `20231234_hw1.py`。
- `template.py` 为标准答案。

### 4. 运行
在项目目录下执行：
```bash
python autograde.py
```
运行后会自动显示进度条，评分结果保存至 `results.txt`。


## 常见问题
- 若 `submissions` 文件夹或 `template.py` 不存在，程序会提示并跳过。
- 若 API 调用失败，结果会显示错误信息。
- 支持 Windows 路径和中文文件名。

