# 网页背景补充

这部分不把网页搜索结果当作第三个正式评论样本，只用于补充事件背景、给已有玩家议题提供少量跨来源佐证，并保留不同声音。

## 文件

- `prompts/dify-web-background-collector.md`：粘贴给 Dify 网页搜索 Agent。
- `prompts/codex-claude-dashboard-enrichment.md`：交给 Codex 或 Claude，在评论分析完成后补充最终看板。

## Dify 产物

Dify Agent 生成一个 `web-background.json` 文件，通过现有 8008 接口保存：

```text
POST http://host.docker.internal:8008/save-artifact
run_id = 本次调查编号
artifact_name = web-background
overwrite = false
Body = form-data
file = 网页搜索 Agent 的 files 输出
```

文件最终位于：

```text
runs/<run_id>/incoming/web-background.json
```

## 使用顺序

1. 先用B站、抖音清洗结果完成玩家反馈分析和看板草案。
2. 再读取 `web-background.json`，挑选少量有用信息补背景、找佐证或保留反例。
3. 网页资料不参与评论数量、情绪比例、平台占比和 `support_count`。

## 最终融合命令

Codex 或 Claude 生成 `runs/<run_id>/web-enrichment.json` 后，运行：

```powershell
python scripts/build_comment_dashboard.py enrich-web `
  --dashboard "runs/<run_id>/dashboard.json" `
  --web-background "runs/<run_id>/incoming/web-background.json" `
  --web-enrichment "runs/<run_id>/web-enrichment.json" `
  --output-dir "runs/<run_id>"
```

该命令会校验研究主题、`WEB-xxx` 引用、类别编号和来源 URL，然后将最终看板升级为 `game-comment-dashboard-1.1`。只复制实际引用的来源；评论数量、平台统计、情绪、类别和代表评论保持不变。

若网页候选存在但没有值得采用的内容，三个采用数组保持为空，最终状态为 `no_useful_result`，前端不会显示网页资料卡片。没有网页文件时，评论看板保持 `not_provided` 状态并正常展示。
