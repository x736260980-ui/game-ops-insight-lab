# V1 流程契约

## 固定主链

1. `research_brief`：研究范围与不能回答的问题。
2. `collection`：采集，可由 Cloud、Dify 或人工完成。B站一个任务可同时产出视频 `data.videos` 与图文动态 `data.posts`。
3. `cleaning`：先把各平台内容统一成稳定评论编号，再去空、相关性筛选和高同质折叠；B站视频与图文动态统一使用 `BILI-xxxx`。可外部完成。
4. `classification_sentiment`：动态分类与总体/类别情绪。
5. `dashboard_freeze`：冻结评论统计与前端基础数据。
6. `sqlite_evidence_import`：只写事件、评论、动态类别、类别关系与情绪。
7. `current_event_analysis`：在看历史案例前走 `single` 或 `dual` 其中一条路线，生成初判。
8. `historical_review`：可选。初判完成后才检索历史证据，用于比较、质疑和限定。
9. `final_analysis`：融合当前事件证据与可选历史复核，生成最终分析。
10. `sqlite_analysis_upsert`：单独写入最终摘要和产物路径。
11. `dashboard_result_injection`：把最终摘要注入 `dashboard.json`，不改评论统计。
12. `persona_simulation`：可选、盲测优先。

## 真相源

- `run-manifest.json`：唯一流程状态真相源。
- SQLite：唯一结构化研究数据真相源，不保存 V1 流程状态。
- `runs/<run_id>/`：该事件的完整源文件和派生文件真相源。

## 恢复原则

- 已完成阶段只校验，不重跑。
- 外部执行和本地执行使用同一文件契约。
- 文件缺失时将对应阶段记为 `waiting`；格式错误或证据边界问题记为 `needs_review`。
- `failed` 表示执行失败，不代表整个研究不可恢复。
