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

## 8. Continue 继续修改

如果对某次结果不满意，可以在对应项目目录里填写反馈：

```text
projects/<项目名_YYYYMMDD>/inputs/feedback.md
```

然后运行：

```powershell
.\scripts\continue_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>"
```

也可以直接指定某个历史版本目录，适合用 Tab 补全选择基于哪一版继续：

```powershell
.\scripts\continue_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>\outputs\<HHMMSS-pending-v1>"
.\scripts\continue_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>\dry_run_outputs\<HHMMSS-pending-v1>"
```

如果只传项目目录，默认基于 `latest` 继续修改；如果传具体版本目录，则基于该版本继续修改。

运行 continue 前，必须在项目目录的 `inputs/feedback.md` 中填写真实反馈。如果该文件不存在、为空，或仍然是默认模板内容，程序会停止并提示先填写反馈，避免误用空反馈继续生成。

dry-run 测试：

```powershell
.\scripts\continue_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>" -DryRun
```

continue 会读取上一版 `latest/final.md` 或 `latest/final.docx`，结合 `inputs/feedback.md` 进行整体重写，并输出到：

```text
projects/<项目名_YYYYMMDD>/outputs/<HHMMSS-continue-v2>/
```

其中初次生成结果通常是 `<HHMMSS-pending-v1>`，第一次 continue 是 `<HHMMSS-continue-v2>`，后续依次为 `v3`、`v4`。如果同一天同一项目名下重复运行，版本号会继续递增，不会一直停留在 `v1`。

如果使用 `-DryRun`，结果会输出到 `dry_run_outputs/<HHMMSS-continue-v2>/`。

每次生成新版本后，终端会提示：

```text
使用下面的命令进行状态标记：
.\scripts\review_project.ps1 -ProjectDir "..."
```

可以用这条命令把新版本标记为 `accept`、`continue`、`abandon` 或 `skip`。

## 9. 选择采纳、放弃或暂不处理

查看某次 `pending` 结果后，可以运行：

```powershell
.\scripts\review_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>"
```

也可以直接指定某个版本目录：

```powershell
.\scripts\review_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>\outputs\<HHMMSS-continue-v2>"
.\scripts\review_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>\dry_run_outputs\<HHMMSS-continue-v2>"
```

如果只传项目目录，默认处理 `latest`；如果传具体版本目录，则只标记该版本。

程序会提示选择：

```text
accept   采纳当前结果
continue 标记为继续修改
abandon  放弃当前结果
skip     暂不处理，保持 pending
```

也可以直接指定：

```powershell
.\scripts\review_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>" -Decision accept
.\scripts\review_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>" -Decision continue
.\scripts\review_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>" -Decision abandon
.\scripts\review_project.ps1 -ProjectDir ".\projects\<项目名_YYYYMMDD>" -Decision skip
```

`accept`、`continue` 和 `abandon` 会把最新版本目录名里的状态标签替换成对应标签，例如：

```text
193728-pending-v1 -> 193728-accept-v1
193728-pending-v1 -> 193728-continue-v1
193728-pending-v1 -> 193728-abandon-v1
193728-accept-v1 -> 193728-abandon-v1
```

选择 `continue` 后，先在项目目录的 `inputs/feedback.md` 中填写反馈，再运行 `continue_project.ps1` 生成下一版。`skip` 会把当前结果标回 `pending`，并提示之后继续选择时可以使用的命令。

如果项目只有 dry-run 输出，`review_project.ps1` 和 `continue_project.ps1` 会自动使用 `dry_run_outputs`，不需要额外指定 `-DryRun`；也可以显式加 `-DryRun`。

## 3. 运行

演示/测试流程，不调用真实大模型：

```powershell
.\scripts\run_demo_docx.ps1
```

正式流程，调用真实大模型：

```powershell
.\scripts\run_real_docx.ps1
```

如果希望让大模型生成修改说明汇总：

```powershell
.\scripts\run_real_docx.ps1 -SummaryMode llm
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
  --summary-mode rule `
  --cycles 5
```

其中 `--source` 和 `--meeting-notes` 都是可选的。

`--summary-mode` 可选：

- `rule`：默认值，用程序规则生成 `changes_summary`，稳定、不额外调用大模型。
- `llm`：使用 reviewer 的 API、base URL、模型压缩较长的摘要字段，再由程序按固定格式生成 `changes_summary`。

## 4. 输出目录

默认情况下，程序会创建一个项目目录：

```text
projects/<项目名_YYYYMMDD>/
  project.json
  inputs/
  outputs/
  dry_run_outputs/
```

`<项目名>` 会优先由大模型根据文档内容和修改要求生成；如果生成失败，会回退到 source 文件名或 requirements 内容摘要。目录名会自动清洗 Windows 不允许的字符。

dry-run 输出到：

```text
projects/<项目名_YYYYMMDD>/dry_run_outputs/<HHMMSS-pending-v1>
projects/<项目名_YYYYMMDD>/dry_run_outputs/latest
```

真实模型输出到：

```text
projects/<项目名_YYYYMMDD>/outputs/<HHMMSS-pending-v1>
projects/<项目名_YYYYMMDD>/outputs/latest
```

项目目录里的 `inputs/` 会保存本次使用的输入文件快照，方便回看当时用的是哪份 source、requirements 和 meeting_notes。

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

`changes_summary` 有两种生成方式：

- 默认规则生成：程序根据每轮 writer 草稿、reviewer 审查、最终稿自动整理。
- LLM 压缩生成：运行时加 `--summary-mode llm`，由 reviewer 模型压缩较长字段，程序负责保留固定格式和运行事实。

LLM 模式下，程序会固定保留以下结构：

```text
# 修改说明汇总
## 一、运行概况
## 二、输入材料
## 三、每轮修改与审查摘要
## 四、最终结论
## 五、需人工补充或核实事项
```

其中运行概况、输入材料、轮数、评分、是否继续修改、停止原因等事实字段由程序填写，不交给大模型改写。大模型只负责压缩这些较长字段：

```text
writer 草稿摘要
reviewer 审查摘要
给 writer 的修改指令
最终审查摘要
需人工补充或核实事项
```

如果 LLM 调用失败，或返回内容无法解析，程序会自动退回规则生成，不影响最终稿输出。可在 `run_log.json` 中查看：

```text
summary_mode_requested
summary_mode_used
summary_fallback_reason
```

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
