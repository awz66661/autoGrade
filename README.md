# AutoGrade - Fudan Python 作业自动评分

基于 DeepSeek OpenAI 兼容接口的 Python 作业批改工具，适配当前课程目录：

```text
assignments/
├── hw_1/
│   ├── answer/project1.py
│   └── submissions/*.py
└── hw_9/
    ├── answer/project9.py
    └── submissions/*.py
```

## 安装

```bash
uv sync
```

复制本地环境变量模板：

```bash
cp .env.example .env
```

在 `.env` 中填写 `DEEPSEEK_API_KEY`。`.env` 已被 `.gitignore` 忽略，不会提交到仓库。

## 常用命令

```bash
# 列出可批改作业
uv run autograde list

# 批改单个作业，默认输出 Excel、CSV、Markdown
uv run autograde hw_9

# 只批改一个学生，跳过相似度检测
uv run autograde hw_1 --student 22301020014 --no-similarity

```

默认作业根目录是 `../assignments`。如需覆盖：

```bash
uv run autograde hw_9 --assignments-dir /path/to/assignments
```

默认并发数为 25，可按需降低：

```bash
uv run autograde hw_9 --parallel 5
```

## DeepSeek 配置

默认配置：

- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-v4-flash`

可临时切换模型：

```bash
uv run autograde hw_9 --model deepseek-v4-pro
```

评分使用 JSON 输出模式，结果字段包括 `score`、`comment`、`issues`、`strengths`、`confidence`。

## 提交解析规则

提交文件名按以下格式解析：

```text
学号_平台用户ID_提交ID_姓名+文件名.py
```

同一学号多次提交时，自动选择提交 ID 最大的文件，其余记录为忽略。`.ipynb` 会提取 code cells 后按 Python 代码评分；其他文件类型跳过并记录原因。

## 名单

课程成员名单已经内置在项目中：

```text
autograde_tool/data/course_108137_roster.json
```

批改输出优先使用内置名单中的姓名；没有匹配时回退到提交文件名解析出的姓名。名单来自课程成员页的本学期快照，不再提供在线同步脚本。

## 输出

报告默认写入每个作业目录下的 `reports/`：

```text
../assignments/hw_9/reports/
├── grading_report_YYYYmmdd_HHMMSS.xlsx
├── grading_results_YYYYmmdd_HHMMSS.csv
└── grading_report_YYYYmmdd_HHMMSS.md
```

报告至少包含：

`student_id`、`name`、`score`、`comment`、`success`、`source_file`、`submission_id`、`platform_user_id`、`from_roster`、`warnings`。
