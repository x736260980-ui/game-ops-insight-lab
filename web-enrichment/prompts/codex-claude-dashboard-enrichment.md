# Codex / Claude 网页背景补充与看板融合提示词

你负责在正式评论分析已经完成后，使用网页搜索资料为游戏玩家反馈看板补充背景与少量交叉佐证。网页材料是外围资料，不是经过系统抽样的第三个平台评论集。

## 输入位置

本次调查目录：

```text
runs/<run_id>/
```

优先读取：

```text
incoming/douyin-folded.json
incoming/bilibili-folded.json
incoming/dify-classification.json
incoming/web-background.json
analysis-input.json
classification-plan.json
semantic-analysis.json
dashboard.json 或当前看板草案
```

文件不一定全部存在。先列出实际可用文件，不要因某个辅助文件缺失而停止整个任务。

## 可用网页搜索工具

如果已经存在 `incoming/web-background.json`，优先使用现有文件，不必重新搜索。只有背景明显不足、关键官方信息缺失或用户明确要求补搜时，才调用已安装的 Tavily、Google Search 或其他网页搜索 MCP。

补搜时围绕事件概况、官方信息、TapTap和NGA做少量针对性查询。新增结果继续使用 `WEB-xxx` 编号，并写回：

```text
runs/<run_id>/incoming/web-background.json
```

安装新的 MCP 后，应先确认工具实际可调用，再将其加入这一步；不要在工具不可用时虚构搜索结果。

## 工作顺序

1. 先阅读清洗后的评论、语义分析和当前看板草案，理解已有玩家议题；
2. 再阅读网页资料，避免网页材料预先改变评论分类；
3. 从网页结果中挑选少量真正有帮助的内容；
4. 将它们分成背景补充、跨来源佐证、不同声音和来源限制；
5. 把这些内容加入最终看板，但保持原评论统计不变。

不需要逐条网页与几百条评论机械对照。只围绕当前看板中的主要议题做整体核对即可。

输出控制：

- `event_background` 保留 2—4 条，资料不足时可以少于 2 条；
- 每个看板类别最多保留 1 条 `corroborations`；
- 每个看板类别最多保留 1 条 `counter_signals`；
- 同一个补充可以引用多个网页来源；
- `used_source_ids` 必须与三个采用数组实际引用的来源编号完全一致；
- 没有真正有用的内容时，三个采用数组和 `used_source_ids` 都输出空数组。

## 采用规则

### 背景补充

用于解释事件是什么、何时发生、涉及哪个版本或角色、官方公开说过什么。客观事实优先使用官方来源；普通网页只能作为辅助说明。

### 跨来源佐证

当TapTap、NGA、攻略或测评中出现与清洗后评论相似的观点时，可以写成“其他社区也出现类似讨论”。这只能证明该观点跨来源存在，不能证明玩家对游戏机制的判断一定正确。

### 不同声音

如果网页资料中存在与当前样本不同的合理观点，保留少量有代表性的反例，避免看板只呈现单边结论。

### 排除

与主题无关、重复、来源不可回查、疑似拼接洗稿、只有标题没有有效内容、孤立爆料或明显误读的结果可以不使用。无需为每条被排除结果写审计理由。

## 统计边界

网页资料不得：

- 增加B站或抖音评论数量；
- 改变情绪比例、平台占比或分类比例；
- 增加评论的 `support_count`；
- 被表述为对全体玩家的统计代表；
- 覆盖清洗后的真实评论原文。

## 建议中间产物

将实际采用的网页信息保存为：

```text
runs/<run_id>/web-enrichment.json
```

参考结构：

```json
{
  "schema_version": "web-enrichment-1.0",
  "research_target": "本次研究主题",
  "event_background": [
    {
      "text": "用于解释事件背景的信息",
      "source_refs": ["WEB-001"]
    }
  ],
  "corroborations": [
    {
      "dashboard_category_id": "当前看板中的分类ID",
      "text": "其他来源出现的相似讨论",
      "source_refs": ["WEB-004", "WEB-007"]
    }
  ],
  "counter_signals": [
    {
      "dashboard_category_id": "当前看板中的分类ID",
      "text": "值得保留的不同声音",
      "source_refs": ["WEB-009"]
    }
  ],
  "source_limitations": [
    "网页搜索结果非系统抽样，只用于背景和定性参考"
  ],
  "used_source_ids": ["WEB-001", "WEB-004", "WEB-007", "WEB-009"]
}
```

## 最终看板

在不破坏现有字段的前提下，将网页补充内容写入最终 `dashboard.json` 的独立字段，例如：

```json
{
  "web_context": {
    "event_background": [],
    "corroborations": [],
    "counter_signals": [],
    "source_limitations": [],
    "sources": []
  }
}
```

同时在可读报告或看板文字中自然引用这些材料。引用必须能回查到 `web-background.json` 中的 `WEB-xxx` 和 URL。没有真正有用的网页材料时允许保持数组为空，不要为了显得资料丰富而强行引用。

生成 `web-enrichment.json` 后，不要手工修改评论看板数字。调用确定性融合命令：

```powershell
python scripts/build_comment_dashboard.py enrich-web `
  --dashboard "runs/<run_id>/dashboard.json" `
  --web-background "runs/<run_id>/incoming/web-background.json" `
  --web-enrichment "runs/<run_id>/web-enrichment.json" `
  --output-dir "runs/<run_id>"
```
