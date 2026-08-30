# 工作流与产物

完整运行由 `$run-game-player-research` 维护 `run-manifest.json`。本 Skill 根据清单执行其中一个具体阶段。

## 主链

1. `research_brief`：明确事件、研究问题、平台、关键词、时间范围和不能回答的问题。
2. `collection`：采集公开评论与必要的网页背景，保留原始结果但不保存公开身份或登录状态。
3. `cleaning`：稳定编号、去空、相关性判断和保守的高同质折叠。
4. `classification_sentiment`：生成动态分类、评论总体情绪与类别内情绪。
5. `dashboard_freeze`：生成并冻结 `dashboard.json` 的评论统计。
6. `sqlite_evidence_import`：只把事件、评论、动态类别、类别关系和情绪写入 SQLite。
7. `current_event_analysis`：按 `analysis_mode=single|dual` 选择且只选择一条路线；在读取历史案例前生成 `analysis/initial-analysis.md`。
8. `historical_review`：可选。初判完成后排除当前事件，从 SQLite 检索历史评论、动态类别和最终摘要。
9. `final_analysis`：生成根目录 `final-analysis.md` 与 `final-summary.json`。
10. `sqlite_analysis_upsert`：最终分析完成后再幂等写入 `analyses`。
11. `dashboard_result_injection`：把最终摘要注入 Dashboard，不改变评论统计。
12. `persona_simulation`：可选。先盲测，再读取真实评论做事后比较。

## 恢复与重跑

- 每个事件使用独立运行目录和唯一 `run-manifest.json`。
- 已标记 `completed` 且文件哈希、Schema 校验通过的阶段直接复用。
- 阶段输入未到齐时记为 `waiting`；存在格式或证据边界问题时记为 `needs_review`。
- 不覆盖原始采集文件，不用伪造文件让状态变绿。
- SQLite 不记录流程状态；它只保存研究证据、最终分析、Persona 和模拟记录。

## 统一稳定输出

无论使用 Single 还是 Dual，事件目录的权威结果都是：

```text
run-manifest.json
analysis/initial-analysis.md
final-analysis.md
final-summary.json
dashboard.json
```

启用历史复核时增加：

```text
retrieval/historical-context.json
retrieval/historical-context.md
analysis/historical-review.md
```

Dual 的盲审和讨论过程继续保存在：

```text
dual-agent/
├─ 01-codex-initial.md
├─ 02-claude-initial.md
├─ 03-transcript.md
└─ 04-disputes.json
```

`.runtime/`、Session、CLI 原始日志和历史失败稿只属于本地运行状态，不进入公开案例。
