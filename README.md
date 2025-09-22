# AutoGrade - Python 作业自动评分系统

> 基于大语言模型的智能评分工具，为高校编程课程设计

## ✨ 核心特性

- 🚀 **智能评分** - 基于AI大语言模型，准确评估代码质量
- ⚡ **并发处理** - 多线程并发评分，显著提升效率
- 🔄 **断点续批** - 支持中断恢复，避免重复工作
- 🔍 **相似度检测** - 自动识别抄袭和代码相似性
- 📊 **统计分析** - 生成分数分布和详细统计报告
- 📁 **多格式导出** - 支持CSV、Excel、JSON、Markdown
- 🗂️ **文件管理** - 智能清理功能，保持工作目录整洁

## 🛠 快速开始

### 1. 环境准备
```bash
# Python 3.8+ 环境
pip install -r requirements.txt
```

### 2. 配置设置
编辑 `config.json`：
```json
{
    "base_path": "C:\\path\\to\\homework\\folder",
    "api_key": "your-api-key",
    "base_url": "https://api.deepseek.com/v1",
    "model": "deepseek-chat",
    "max_workers": 5,
    "similarity_threshold": 0.85
}
```

### 3. 目录结构设置

在 `base_path` 指定的目录下，需要按以下结构组织文件：

```
base_path/
├── template.py              # 🔑 必需：参考答案文件
├── submissions/             # 🔑 必需：学生作业文件夹
│   ├── 20230001_homework.py # 格式：学号_其他信息.py
│   ├── 20230002_hw1.py      # 程序会自动从文件名提取学号
│   └── 20230003_作业1.py    # 支持中文文件名
├── reports/                 # 📁 自动创建：评分结果输出目录
│   ├── grading_results_*.csv
│   ├── grading_report_*.xlsx
│   ├── statistics_report.txt
│   └── score_distribution.png
└── grading_progress.json    # 📁 自动创建：进度记录文件
```

#### 📝 文件要求说明

1. **`template.py`** (必需)
   - 包含标准答案的Python代码
   - 作为AI评分的参考标准
   - 确保代码格式规范、逻辑清晰

2. **`submissions/`** 文件夹 (必需)
   - 存放所有学生提交的作业文件
   - 文件名格式：`学号_其他信息.py`
   - 支持下划线分隔，程序会自动提取学号部分
   - 示例：`2023001_作业1.py` → 学号：`2023001`

3. **`reports/`** 文件夹 (自动创建)
   - 程序运行时自动创建
   - 存放所有评分结果和统计报告
   - 包含多种格式的导出文件

#### 💡 快速设置示例

假设您的作业目录为 `C:\homework\python_hw1`：

1. **创建目录结构**：
   ```bash
   mkdir C:\homework\python_hw1\submissions
   ```

2. **放置参考答案**：
   将标准答案保存为 `C:\homework\python_hw1\template.py`

3. **放置学生作业**：
   将学生文件放入 `C:\homework\python_hw1\submissions\` 目录

4. **修改配置**：
   ```json
   {
     "base_path": "C:\\homework\\python_hw1",
     "api_key": "your-api-key-here",
     ...
   }
   ```

5. **运行评分**：
   ```bash
   python autograde.py --parallel 5 --export all
   ```

### 4. 开始评分
```bash
# 基础使用
python autograde.py

# 查看所有选项
python autograde.py --help
```

## ⚠️ 重要提醒

1. **首次使用前**，请确保 `base_path` 目录下已创建：
   - ✅ `template.py` - 参考答案文件  
   - ✅ `submissions/` - 学生作业文件夹
   
2. **学生文件命名**：建议使用 `学号_作业名.py` 格式，便于自动识别

3. **API配置**：确保API密钥有效且有足够的调用额度

## 📋 命令行参数

### 🗑️ 清理模式（独立操作）
```bash
python autograde.py --clean base      # 清理base_path目录
python autograde.py --clean local     # 清理当前目录
python autograde.py --clean all       # 清理所有目录
```

### 📊 评分模式
```bash
# 基础选项
python autograde.py                     # 正常评分
python autograde.py --resume           # 从断点继续
python autograde.py --parallel 4       # 并发评分(4线程)

# 导出选项
python autograde.py --export excel     # 导出Excel(默认)
python autograde.py --export all       # 导出所有格式

# 特殊选项
python autograde.py --student 12345    # 只评分特定学生
python autograde.py --no-similarity    # 跳过相似度检测
python autograde.py --retry-failed     # 重试失败作业
```

### 🔧 组合使用
```bash
# 并发 + 断点续批 + 全格式导出
python autograde.py --parallel 5 --resume --export all

# 并发20线程 + 断点续批 + excel导出
python autograde.py --parallel 20 --resume --export excel

# 重试失败 + 自定义标准
python autograde.py --retry-failed --criteria custom.json
```

## 📁 项目结构

```
autograde/
├── autograde.py              # 主程序
├── grader.py                # 评分核心
├── similarity_checker.py    # 相似度检测
├── progress_manager.py      # 进度管理
├── score_analyzer.py        # 统计分析
├── export_utils.py          # 导出工具
├── config.json              # 配置文件
├── grading_criteria_example.json  # 评分标准示例
└── requirements.txt         # 依赖列表
```

## 📊 输出文件说明

### 评分结果（保存在base_path目录）
- `grading_results_*.csv` - CSV格式结果
- `grading_report_*.xlsx` - Excel报告（多工作表）
- `grading_data_*.json` - JSON完整数据
- `grading_report_*.md` - Markdown报告

### 统计分析
- `statistics_report.txt` - 统计摘要
- `score_distribution.png` - 分数分布图

### 进度和日志
- `grading_progress.json` - 进度记录
- `grading_*.log` - 运行日志

## 🎯 自定义评分标准

创建JSON配置文件（参考 `grading_criteria_example.json`）：

```json
{
  "score_ranges": {
    "excellent": {"min": 95, "max": 100, "probability": 0.7},
    "good": {"min": 80, "max": 94, "probability": 0.8}
  },
  "deduction_items": {
    "no_error_handling": -5,
    "poor_code_style": -2
  },
  "bonus_items": {
    "elegant_solution": 3
  }
}
```

## 🔍 相似度检测

自动检测代码相似性：
- **文本相似度** - 基于编辑距离
- **结构相似度** - AST语法树分析
- **标识符相似度** - 变量名对比

超过阈值的作业对将在Excel报告中标出。

## 🚀 性能优化

1. **并发设置**: 根据API限制调整 `--parallel` 参数（建议3-8）
2. **断点续批**: 长任务使用 `--resume` 避免重复工作
3. **智能缓存**: 相同代码自动复用评分结果
4. **清理维护**: 定期使用 `--clean` 清理临时文件

## 🐛 常见问题

| 问题 | 解决方案 |
|------|----------|
| API超时 | 调整config.json中的timeout值 |
| 内存不足 | 减少并发数或分批处理 |
| 编码错误 | 程序已自动处理，检查文件编码 |
| 导入错误 | 确保在项目根目录运行 |

## 📈 工作流程

1. **准备阶段**: 配置文件设置、环境检查
2. **扫描阶段**: 自动发现作业文件、学生ID识别
3. **评分阶段**: 并发评分、进度跟踪、错误处理
4. **检测阶段**: 相似度分析、抄袭识别
5. **分析阶段**: 统计计算、图表生成
6. **导出阶段**: 多格式报告生成
7. **清理阶段**: 临时文件清理（可选）