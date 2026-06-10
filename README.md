# 多 agent 办公文档修订助手

这是一个多模型办公文档修订工具。基本流程是：

```text
修改要求 + 可选初稿 + 可选会议纪要
-> writer 生成修改稿
-> reviewer 审查并给下一轮建议
-> 多轮循环
-> 输出 final.docx / final.md / review.md / run_log.json
```

## 1. 输入文件

默认输入目录是：

```text
inputs/
```

### 必填：修改要求

```text
inputs/requirements.md
```

这里写用户希望怎么改、输出什么类型文档、审查重点是什么。

如果该文件不存在或内容为空，程序会停止并提示错误。

### 可选：初稿或原文

程序会按顺序自动查找：

```text
inputs/source.docx
inputs/source.md
inputs/source.txt
```

找到第一个存在的文件就作为初稿。支持：

- `.docx`
- `.md`
- `.txt`

如果没有 source 文件，或 source 文件内容为空，程序会进入“无初稿起草模式”：writer 会根据修改要求和可选会议纪要从零生成初稿。

### 可选：会议纪要

```text
inputs/meeting_notes.md
```

如果存在且内容不为空，writer 和 reviewer 都会参考会议纪要。

如果该文件不存在或内容为空，程序会按“没有会议纪要”处理。

### 示例模板

仓库中保留示例模板：

```text
inputs/source.example.docx
inputs/requirements.example.md
inputs/meeting_notes.example.md
```

真实办公文件不会提交到 git。首次使用时可以复制模板：

```powershell
Copy-Item .\inputs\source.example.docx .\inputs\source.docx
Copy-Item .\inputs\requirements.example.md .\inputs\requirements.md
Copy-Item .\inputs\meeting_notes.example.md .\inputs\meeting_notes.md
```

如果没有初稿，不需要创建 `source.docx`。

如果没有会议纪要，不需要创建 `meeting_notes.md`。

## 2. API 配置

配置文件：

```text
config/settings.env
```

如果该文件不存在，先复制模板：

```powershell
Copy-Item .\config\settings.example.env .\config\settings.env
```

writer 和 reviewer 可以使用不同平台、不同 key、不同模型：

```text
WRITER_API_KEY=writer 的 API key
WRITER_BASE_URL=writer 的接口地址
WRITER_MODEL=writer 使用的模型名
WRITER_ENABLE_SEARCH=true

REVIEWER_API_KEY=reviewer 的 API key
REVIEWER_BASE_URL=reviewer 的接口地址
REVIEWER_MODEL=reviewer 使用的模型名
REVIEWER_ENABLE_SEARCH=true
```

连接测试：

```powershell
.\scripts\check_connections.ps1
```

## 3. 运行

演示/测试流程，不调用真实大模型：

```powershell
.\scripts\run_demo_docx.ps1
```

正式流程，调用真实大模型：

```powershell
.\scripts\run_real_docx.ps1
```

也可以直接运行：

```powershell
.\.venv\Scripts\python.exe .\run_revision.py
```

常用参数：

```powershell
.\.venv\Scripts\python.exe .\run_revision.py `
  --source .\inputs\other.docx `
  --requirements .\inputs\other_requirements.md `
  --meeting-notes .\inputs\meeting_notes.md `
  --cycles 5
```

其中 `--source` 和 `--meeting-notes` 都是可选的。

## 4. 输出目录

dry-run 输出到：

```text
outputs/demo/<timestamp>
outputs/demo/latest
```

真实模型输出到：

```text
outputs/autogen/<timestamp>
outputs/autogen/latest
```

如果 `latest` 里的 Word 文件正被打开，刷新 `latest` 可能会被跳过，但时间戳目录仍会保留本次结果。

主要输出：

```text
final.docx
final.md
review.md
changes_summary.docx
changes_summary.md
run_log.json
```

`changes_summary` 是本次运行的修改说明汇总，包含运行概况、输入材料、每轮修改与审查摘要、最终结论，以及自动识别出的“需补充 / 需核实 / 待确认 / TODO”等人工处理事项。

每轮结果：

```text
drafts/
  round_01_draft.md
  round_01_draft.docx

reviews/
  round_01_review.md
  round_01_review.docx
```

## 5. reviewer 提前停止

reviewer 会输出固定结构，其中包括：

```text
是否继续修改：是/否
总体评分：1-5
```

如果 reviewer 写：

```text
是否继续修改：否
```

程序会提前停止，不再跑满 `--cycles`。

## 6. 当前 Word 支持范围

已支持：

- `.docx` 读取标题、段落、表格文本
- `.docx` 输出最终稿和每轮稿件
- 加粗文本
- 表格内换行
- 跳过 Markdown 表格分隔行

暂不完整支持：

- `.doc` 老格式
- 复杂页眉页脚
- Word 批注
- 修订痕迹
- 文本框和复杂版式

## 7. 判断本地流程是否正常

运行测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

看到 `OK` 表示本地程序逻辑正常。API 是否可用仍以连接测试为准：

```powershell
.\scripts\check_connections.ps1
```
