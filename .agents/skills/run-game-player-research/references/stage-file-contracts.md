# 阶段文件契约

| 阶段 | 最小输入 | 规范输出 |
|---|---|---|
| research_brief | 用户主题 | `research-brief.md` |
| collection | research brief | `incoming/` 或 `raw/` 至少一个采集文件；B站推荐单文件同时含 `data.videos` 与 `data.posts` |
| cleaning | incoming | `analysis-input.json`；中间清洗文件可保留 |
| classification_sentiment | analysis input | `classification-plan.json`, `semantic-analysis.json` |
| dashboard_freeze | classification + semantic | `dashboard.json` |
| sqlite_evidence_import | 上述四个 JSON | 本地 SQLite 中 event/comments/categories/comment_categories；清单记录命令结果 |
| current_event_analysis | analysis input + semantic + dashboard + 可选网页证据 | `analysis/initial-analysis.md`；dual 可另留 `dual-agent/` |
| historical_review | initial analysis + SQLite | `retrieval/historical-context.json`, `retrieval/historical-context.md`, `analysis/historical-review.md` |
| final_analysis | initial analysis + 可选 historical review | `final-analysis.md`, `final-summary.json` |
| sqlite_analysis_upsert | final outputs | SQLite `analyses` 幂等记录 |
| dashboard_result_injection | dashboard + final summary | 含 `analysis_summary` 的 `dashboard.json` |
| persona_simulation | 已确认事实 + personas | `simulation/` 下的预测与事后对照 |

## 外部交接

外部执行者不需要了解整条流水线，只需输出该阶段契约文件。接收方先校验，再把阶段标为 `completed`。仅口头声称完成、没有文件，不能标记完成。

B站采集文件允许两种等价交接：推荐的统一 `bilibili-collection-result.json`，或历史的“视频文件＋图文动态文件”。清洗时必须读取实际存在的全部B站文件，按原评论ID去重并统一编号，不能只取 `data.videos` 或只取 `data.posts`。

## 哈希

清单输出记录相对于 run 根目录的路径、字节数和 SHA-256。源文件更新后，旧哈希用于识别变更；V1 不做自动双向同步。
