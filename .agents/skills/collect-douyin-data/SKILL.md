---
name: collect-douyin-data
description: Plan and execute one complete Douyin collection task through the douyin_collect_task tool. Use when a task requires one or more Douyin keyword searches, pinned aweme IDs, configurable video counts or first-level comment limits, with search results and pinned IDs merged before collection.
---

# Collect Douyin Data

Prefer the `douyin_collect_task` tool when the host exposes it. In this repository, the equivalent local route is the MediaCrawler adapter started by `scripts/run_douyin_api.ps1`: send the same JSON body once to `http://127.0.0.1:8101/collect-task`. Submit one complete task instead of calling search and comment routes separately; never run both paths for the same task.

## Workflow

1. Extract every requested keyword, sort order, time range, video count, pinned aweme ID, and comment limit.
2. Preserve every user-provided aweme ID in `pinned_video_ids`; never replace it with a search result.
3. Put independent keyword searches in `searches` in the user's requested order.
4. Use `comments_per_video` only for explicit per-video overrides; otherwise use `default_comments_per_video`.
5. Call `douyin_collect_task` exactly once with the complete JSON request.
6. Read `status`, `warnings`, actual returned counts, and per-video `selection_reasons` before reporting completion.

Read [references/api-contract.md](references/api-contract.md) before constructing the tool call. The authoritative request Schema is `../../../schemas/douyin-collect-task.schema.json` (relative to this Skill directory).

## Rules

- Use only numeric aweme IDs.
- Map 综合排序 to `comprehensive`, 点赞最多 to `most_liked`, and 最新发布 to `newest`.
- Use `api_only`; never request browser scrolling from the Agent tool.
- Do not invent comments when the platform returns fewer than requested.
- Do not retry the whole task automatically after `partial_success`; report failed videos and preserve successful data.
- Treat collected material as a bounded public sample, not as all Douyin users.
- Do not expose Cookie values, browser ports, commenter identities, or local file paths.
