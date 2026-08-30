# SQLite Design Review

这是本仓库 `runs/` 的可选长期数据层。它不会替换、移动或改写任何 JSON/JSONL/Markdown。V1 通过总调度 Skill 接入流程，但 SQLite 只保存研究数据，不保存阶段状态。

## 为什么这样设计

对 9 个正式 run 的实际检查显示：

- `analysis-input.json` 稳定保存折叠代表评论、平台、原文、`support_count` 和 `merged_record_ids`。
- `semantic-analysis.json` 保存评论总体情绪、是否进入 Dashboard，以及非互斥 `aspects`。
- `classification-plan.json` 保存动态类别名称和定义。
- `dashboard.json` 保存经过校验的聚合统计，但不应反向覆盖评论事实。
- `final-summary.json` 和 `final-analysis.md` 只在部分 run 中存在。

因此第一版关系模型为：

- `events`：一次稳定的 `runs/<run_id>` 研究事件。
- `comments`：折叠后的代表评论；`UNIQUE(event_id, record_id)`，因为编号只在事件内稳定。
- `categories`：当前事件的动态类别定义。
- `comment_categories`：评论与类别的多对多关系，同时保存类别内 sentiment。
- `analyses`：最终结构化摘要和各权威文件的路径。
- `personas`、`persona_evidence`：未来 Player Persona 及其真实评论证据。
- `simulations`：未来 Persona 对事件或场景的模拟结果。

命名映射只发生在数据库层：`research_target`/`research_title` 都映射到事件；`overall_sentiment` 是评论总体情绪，aspect 中的 `sentiment` 是类别内情绪。数据库不会把 `support_count` 或 `merged_record_ids` 解释为独立玩家人数。

完整语义分析、Dashboard、网页资料、Markdown 报告和双 Agent 对话仍留在文件中。SQLite 只保存查询需要的关系、结构化摘要和文件路径，不保存 Cookie、浏览器登录态、Token、头像或评论者身份。

## 命令行

在仓库根目录执行：

```powershell
python -m storage.db init --db .\data\game_ops.db
python -m storage.import_run .\runs\hsr-fate-second-collab-3platform-rerun-20260829 --db .\data\game_ops.db
python -m storage.upsert_analysis .\runs\hsr-fate-second-collab-3platform-rerun-20260829 --mode single --db .\data\game_ops.db
python -m storage.query events
python -m storage.query search "角色待遇" --limit 50
```

`storage.import_run` 只导入事件、评论、动态类别、类别关系与情绪证据。`storage.upsert_analysis` 只在最终分析完成后写入 `analyses`。两步都幂等，避免尚未生成分析时写入半成品。

## 查询

```python
from storage.repository import Repository

repo = Repository("data/game_ops.db")
events = repo.list_events()
comments = repo.get_comments(
    "hsr-fate-second-collab-3platform-rerun-20260829",
    platform="bilibili",
)
story_comments = repo.get_comments_by_category(
    "hsr-fate-second-collab-3platform-rerun-20260829",
    "story_presentation",
)
```

## 关键词搜索

FTS5 是 SQLite 自带的全文检索模块，不是额外数据库，也不会把数据传到外部。当前实现使用 `trigram` 文本索引，适合中文连续短语；查询词不足 3 个字符时自动退回安全的字面子串匹配。

```python
results = repo.search_comments("角色待遇")

results = repo.search_comments(
    "剧情 演出",
    event_id="hsr-fate-second-collab-3platform-rerun-20260829",
    platform="bilibili",
    sentiment="negative",
    category_id="story_presentation",
    limit=30,
)

historical_only = repo.search_comments(
    "付费加强",
    exclude_event_id="current-event-id",
    sentiment="negative",
    limit=30,
)
```

`query` 必填；`event_id`、`exclude_event_id`、`platform`、`sentiment` 和 `category_id` 都是可选过滤器。历史复核必须排除当前事件。动态类别 ID 只在各自事件内成立，不能作为跨事件统一口径。

当前事件初判完成后，可构建历史复核包：

```powershell
python -m storage.context_pack .\runs\<run_id> `
  --query "付费加强" `
  --query "旧资源失效" `
  --sentiment negative `
  --limit 30
```

命令要求 `analysis/initial-analysis.md` 已存在，并输出 `retrieval/historical-context.json` 与 `.md`。它读取历史事件的动态类别名称、定义、摘要和命中评论，不依赖固定类别 ID。

Agent 或人工日常使用的完整选择规则见 `storage/AGENT-USAGE.md`。

Persona API：

```python
repo.import_persona(persona_payload, evidence_bundle)
repo.get_persona("P1")
repo.get_persona_evidence("P1")
repo.add_simulation(simulation_payload)
```

`import_persona` 把传入的 evidence bundle 视为该 Persona 当前完整证据集：重复导入会更新 Persona，并替换该 Persona 的旧证据关系。

## 边界与未来选项

本轮不做 embedding 或向量数据库。未来评论达到数万或十万、需要跨事件语义检索时，可以评估 `sqlite-vec`、SQLite Vec1 或独立向量检索层。届时应新增独立 embedding 表，记录模型、版本和维度，并继续使用 `event_id + record_id` 关联评论；当前 Schema 不会阻碍这种旁路扩展。

数据库默认位于当前仓库的 `data/game_ops.db`，并由 `.gitignore` 排除；不要提交本地数据库文件、浏览器状态或真实私人材料。
