# 输入输出契约

## 1. `analysis-input.json`

由 `build_comment_dashboard.py prepare` 生成。`support_count` 包含代表评论本身；`merged_record_ids` 必须完整列出其代表的原编号。

```json
{
  "schema_version": "game-comment-insight-input-1.0",
  "research_target": "本次研究主题",
  "platforms": [
    {
      "platform": "douyin",
      "relevance_count": 174,
      "folded_count": 138,
      "represented_count": 174
    }
  ],
  "comments": [
    {
      "record_id": "DY-0036",
      "platform": "douyin",
      "text": "真实代表评论",
      "support_count": 2,
      "merged_record_ids": ["DY-0036", "DY-0218"]
    }
  ]
}
```

## 2. `classification-plan.json`

先生成 `draft`，由用户确认后改为 `approved`。类别包含 4—8 个动态类别和唯一的 `other`。

```json
{
  "schema_version": "game-comment-classification-plan-1.0",
  "plan_version": "target-2026-08-22-v1",
  "research_target": "本次研究主题",
  "status": "draft",
  "categories": [
    {
      "category_id": "team_fit",
      "name": "配队适配",
      "definition": "讨论角色适配的队伍、队友和替换关系。",
      "include_if": ["询问或评价具体队伍适配"],
      "exclude_if": ["只讨论外观或剧情"]
    },
    {
      "category_id": "other",
      "name": "其他",
      "definition": "与研究主题相关但无法归入具体类别。",
      "include_if": ["相关且不符合已有类别"],
      "exclude_if": ["明显无关"]
    }
  ]
}
```

## 3. `semantic-analysis.json`

纳入项必须有总体情绪和至少一个方面；排除项必须有排除理由，且总体情绪为 `null`、方面为空。只为实际出现的类别生成 `category_outputs`。

```json
{
  "schema_version": "game-comment-semantic-analysis-1.0",
  "research_target": "本次研究主题",
  "results": [
    {
      "record_id": "DY-0036",
      "include_in_dashboard": true,
      "overall_sentiment": "neutral",
      "aspects": [
        {"category_id": "team_fit", "sentiment": "neutral"}
      ]
    },
    {
      "record_id": "DY-0099",
      "include_in_dashboard": false,
      "overall_sentiment": null,
      "aspects": [],
      "exclusion_reason": "只讨论主播互动，与研究主题无关"
    }
  ],
  "category_outputs": [
    {
      "category_id": "team_fit",
      "summary": "玩家主要询问角色适配队伍和替换价值。",
      "representative_ids": ["DY-0036"]
    }
  ]
}
```

## 情绪枚举

| 值 | 含义 |
|---|---|
| `positive` | 明确认可、满意、期待或正向评价 |
| `negative` | 明确否定、不满、担忧或负向评价 |
| `neutral` | 咨询、事实陈述或无明显褒贬 |
| `mixed` | 同一判断层级同时包含明确正负两面 |

不要因为一条评论属于多个类别，就自动把总体情绪设为 `mixed`；只有评论整体确实同时表达正负评价时才使用。

## 数量口径

- Python 按 `support_count` 加权；Codex 不手工计算数量。
- 总体情绪互斥，四类数量之和必须等于最终纳入量。
- 类别多选，类别数量或占比之和可以超过总量或 100%。
- 类别内情绪对该类别互斥，四类数量之和必须等于该类别加权数量。

