# 阶段文件契约

| 阶段 | 最小输入 | 规范输出 |
|---|---|---|
| research_brief | 用户主题 | `research-brief.md` |
| collection | research brief | `incoming/` 至少一个采集文件 |
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

## 阶段衔接

每个阶段只依赖上游规范文件。运行者先校验输入，完成后再校验输出并标记为 `completed`。仅有文字说明、没有规范文件，不能标记完成。

## 哈希

清单输出记录相对于 run 根目录的路径、字节数和 SHA-256。源文件更新后，旧哈希用于识别变更；V1 不做自动双向同步。
