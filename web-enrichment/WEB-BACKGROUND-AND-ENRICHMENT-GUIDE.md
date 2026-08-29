# Web Background 与 Web Enrichment 获取规范

本文件说明云端 AI 如何获取网页资料，以及如何把网页资料接入最终 `dashboard.json`。网页资料只做事件背景和定性佐证，不计入玩家评论统计。

## 一、两个文件分别是什么

### `web-background.json`

这是“搜索结果原材料”。由具备网页搜索能力的 Agent 获取，保留真实 URL、标题、来源和与主题有关的摘录。

保存位置：`runs/<run_id>/incoming/web-background.json`

### `web-enrichment.json`

这是“采用结果”。由分析 Agent 阅读 `web-background.json` 和当前看板草案后生成，只挑选真正有用的背景、佐证和不同声音。

保存位置：`runs/<run_id>/web-enrichment.json`

## 二、如何获取 `web-background.json`

输入至少包括研究主题 `research_target`，以及游戏名、版本、角色名或事件关键词（如果有）。使用当前可用的网页搜索工具（例如 Tavily、Google Search 或云端内置搜索），围绕以下角度各搜索一次即可：

1. 事件、角色或版本的基本情况；
2. 官方公告、官方说明或可信资料；
3. TapTap、NGA 等社区的相关讨论；
4. 对争议有直接帮助的攻略、测评或媒体材料。

不要为了凑数量反复搜索。通常保留 5—20 条有效结果即可；结果不足时允许少于这个数量。排除无关、重复、只有标题、没有可回查 URL 或明显无法确认的内容。

每条结果必须保留：

```json
{
  "web_id": "WEB-001",
  "title": "网页标题",
  "url": "https://example.com/page",
  "source": "来源名称",
  "published_at": null,
  "source_hint": "official / taptap / nga / media / review / other",
  "content": "与主题直接相关的原文摘录或忠实摘要"
}
```

编号从 `WEB-001` 连续生成；不能编造网址、标题、日期或网页内容。最终必须输出完整的 `web-background.json` 文件，而不是只在文字回复里描述搜索结果。

## 三、如何获取 `web-enrichment.json`

搜索完成后，分析 Agent 读取 `incoming/web-background.json`、`dashboard.json`（或当前看板草案）、`analysis-input.json`、`classification-plan.json` 和 `semantic-analysis.json`。从网页结果中只选择三类内容：

- `event_background`：解释事件是什么、涉及哪个版本或角色；
- `corroborations`：其他来源出现了与评论样本相似的讨论；
- `counter_signals`：与当前评论样本不同、但值得保留的合理观点。

每类只保留少量最有帮助的内容。没有有用网页资料时允许全部为空，不能强行引用。

输出结构：

```json
{
  "schema_version": "web-enrichment-1.0",
  "research_target": "本次研究主题",
  "event_background": [{"text": "事件背景说明", "source_refs": ["WEB-001"]}],
  "corroborations": [{"dashboard_category_id": "team_fit", "text": "其他来源也出现类似讨论", "source_refs": ["WEB-004"]}],
  "counter_signals": [],
  "source_limitations": ["网页资料不是系统抽样的玩家样本"],
  "used_source_ids": ["WEB-001", "WEB-004"]
}
```

`source_refs` 和 `used_source_ids` 必须能回查到 `web-background.json` 的 `WEB-xxx` 与 URL。

## 四、接入最终看板

生成 `web-enrichment.json` 后，使用确定性脚本融合：

```powershell
python scripts/build_comment_dashboard.py enrich-web `
  --dashboard "runs/<run_id>/dashboard.json" `
  --web-background "runs/<run_id>/incoming/web-background.json" `
  --web-enrichment "runs/<run_id>/web-enrichment.json" `
  --output-dir "runs/<run_id>"
```

融合时不得改变玩家评论数量、平台数量、情绪/分类统计、`support_count` 或评论原文。网页资料不能被写成“全体玩家认为”，也不能作为第三个平台参与统计。

## 五、云端交付清单

```text
incoming/web-background.json
web-enrichment.json
dashboard.json
report.md（可选）
analysis-audit.json（可选）
```

本地看板至少需要 `dashboard.json`；要保留网页证据链，则应同时下载前两个 Web 文件。
