# 自动修改文档原型

这是一个多模型办公文档修改工具。用户日常只需要关心三件事：

1. API 配置在哪里。
2. 初稿和修改要求放在哪里。
3. 修改结果在哪里看。

## 1. API 配置在哪里

配置文件：

```text
config/settings.env
```

如果这个文件不存在，先复制模板：

```powershell
Copy-Item .\config\settings.example.env .\config\settings.env
```

分别填写 writer 和 reviewer：

```text
WRITER_API_KEY=writer 的 API key
WRITER_BASE_URL=writer 的接口地址，可留空
WRITER_MODEL=writer 使用的模型名
WRITER_ENABLE_SEARCH=true

REVIEWER_API_KEY=reviewer 的 API key
REVIEWER_BASE_URL=reviewer 的接口地址，可留空
REVIEWER_MODEL=reviewer 使用的模型名
REVIEWER_ENABLE_SEARCH=true
```

如果使用第三方 OpenAI-compatible 平台，`BASE_URL` 通常类似：

```text
https://你的接口地址/v1
```

连接测试：

```powershell
.\scripts\check_connections.ps1
```

### . 结构化 reviewer 和提前停止

reviewer 会按固定 Markdown 结构输出审查意见：

```text
一、总体结论
是否继续修改：是/否
总体评分：1-5
结论说明：……

二、修改要求落实情况
……

三、主要问题
……

四、下一轮修改清单
……

五、给 writer 的修改指令
……
```

程序会解析：

- `是否继续修改：否`：提前停止，不再跑满 `--cycles`
- `是否继续修改：是`：继续下一轮，直到达到 `--cycles`
- `总体评分：1-5`：记录到 `run_log.json`
- `五、给 writer 的修改指令`：优先传给下一轮 writer

如果 reviewer 没有按格式输出，程序会保守处理：不提前停止，继续按最大轮数运行。若没有“给 writer 的修改指令”，程序会尝试使用“四、下一轮修改清单”作为兜底。

如果输出里显示 `search=on`，说明该角色运行时会把联网搜索参数发送给模型平台。

```text
[OK] WRITER model=...: 连接成功 search=on
[OK] REVIEWER model=...: 连接成功 search=on
```

如果某个模型不支持联网搜索，连接测试或正式运行可能会返回平台错误。此时可以把对应角色的 `ENABLE_SEARCH` 改成 `false`，或者换成平台明确支持联网搜索的模型。

### AutoGen 模型能力配置

这些字段用于告诉 AutoGen 模型支持哪些能力：

```text
MODEL_FAMILY=unknown
VISION=false
FUNCTION_CALLING=false
JSON_OUTPUT=false
STRUCTURED_OUTPUT=false
ENABLE_SEARCH=true
```

含义：

- `ENABLE_SEARCH`：是否向模型平台发送联网搜索参数。当前 DashScope 兼容接口使用 `enable_search=true`。
- `VISION`：是否支持图片输入。
- `FUNCTION_CALLING`：是否支持工具/函数调用。
- `JSON_OUTPUT`：是否支持 JSON 模式输出。
- `STRUCTURED_OUTPUT`：是否支持结构化输出。
- `MODEL_FAMILY`：AutoGen 用来判断模型家族；第三方模型通常保持 `unknown`。

当前写作-审查流程不需要图片、函数调用或结构化输出，所以这些能力保持 `false` 更稳。联网搜索可按角色单独开启或关闭。

## 2. 初稿和要求放在哪里

用户只需要替换 `inputs` 目录里的两个文件。

```text
inputs/source.docx
inputs/requirements.md
```

- `inputs/source.docx`：放 Word 初稿、原文、已有草稿。
- `inputs/requirements.md`：写修改要求、会议意见、审查重点。

`.doc` 老格式暂不直接支持，请先用 Word 或 WPS 另存为 `.docx`。

## 3. 怎么运行

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

默认会读取：

```text
inputs/source.docx
inputs/requirements.md
```

## 4. 输出结果在哪里

演示/测试输出：

```text
outputs/demo/latest
```

每次运行还会额外生成一个时间戳目录，例如：

```text
outputs/demo/20260610_093000
```

正式使用输出：

```text
outputs/autogen/latest
```

每次运行还会额外生成一个时间戳目录，例如：

```text
outputs/autogen/20260610_093000
```

`latest` 始终是最近一次运行结果；时间戳目录用于保留历史运行记录。

输出文件：

- `final.docx`：最终 Word 修改稿。
- `final.md`：最终稿的 Markdown 文本版本。
- `review.md`：最终审查意见。
- `run_log.json`：每一轮写作和审查记录。

此外，还会保留每轮writer的输出和reviewer的审核结果:

```text
drafts/
  round_01_draft.md
  round_01_draft.docx
  round_02_draft.md
  round_02_draft.docx
  ...

reviews/
  round_01_review.md
  round_01_review.docx
  round_02_review.md
  round_02_review.docx
  ...
```

`drafts/` 保存writer每轮的输出. `reviews/` 保存reviewer每轮的审核内容. 如果reviewer提前停止流程，只有已完成的轮次会被保存。

因为 reviewer 可以写 `是否继续修改：否` 来提前停止，所以把最大轮数设高一些更灵活；它代表“最多 5 轮”，不是一定跑满 5 轮。

## 5. 常用自定义

如果要改轮数：

```powershell
.\.venv\Scripts\python.exe .\run_revision.py --cycles 3
```

如果要临时指定其他输入文件：

```powershell
.\.venv\Scripts\python.exe .\run_revision.py `
  --source .\inputs\other.docx `
  --requirements .\inputs\other_requirements.md
```

如果要改 writer 或 reviewer 的角色提示词：

```text
config/writer_system_prompt.md
config/reviewer_system_prompt.md
```

## 6. 当前支持范围

`.docx` 支持：

- 标题
- 普通段落
- 表格文本
- 加粗文本
- 表格内换行

暂不完整支持：

- `.doc` 老格式
- 复杂页眉页脚
- Word 批注
- 修订痕迹
- 文本框和复杂版式

## 7. 判断基础流程是否正常

运行自动测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
```

看到 `OK` 就说明本地程序逻辑正常。API 是否可用仍以连接测试为准：

```powershell
.\scripts\check_connections.ps1
```
## 8. 输入文件上传和隐私

仓库只应上传模板示例，不应上传真实办公文档。

可上传的模板文件：

```text
inputs/source.example.docx
inputs/requirements.example.md
```

本地真实使用文件：

```text
inputs/source.docx
inputs/requirements.md
```

这两个真实文件已经写入 `.gitignore`，不会再被 git 新增跟踪。首次使用或重置模板时，可以复制：

```powershell
Copy-Item .\inputs\source.example.docx .\inputs\source.docx
Copy-Item .\inputs\requirements.example.md .\inputs\requirements.md
```

如果真实内容已经被提交但还没有上传远程仓库，使用普通提交删除跟踪即可：

```powershell
git rm --cached -- inputs/source.docx inputs/requirements.md
git add .gitignore inputs/source.example.docx inputs/requirements.example.md
git commit -m "chore: ignore local input documents"
```

如果真实内容已经上传到 GitHub/Gitee 等远程仓库，仅 `git rm --cached` 只能让后续提交不再包含它们，历史提交里仍然可能存在。此时建议：

1. 立即更换或撤销文档中包含的敏感信息、密钥、账号等。
2. 将远程仓库改为私有，或删除公开仓库。
3. 如需彻底清理历史，使用 `git filter-repo` 或 BFG Repo-Cleaner 重写历史后强制推送。
4. 通知所有协作者重新克隆仓库，避免旧历史继续传播。

现在默认脚本把最大轮数设为 5：

```powershell
.\scripts\run_demo_docx.ps1
.\scripts\run_real_docx.ps1
```

