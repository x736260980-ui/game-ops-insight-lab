---
name: collect-bilibili-data
description: Plan and execute one complete Bilibili video and image-text/dynamic collection task through the bilibili_collect_task tool or local adapter. Use for keyword video searches, pinned BV IDs, opus/dynamic IDs or URLs, first-level comments, and optional video danmaku.
---

# Collect Bilibili Data

Prefer the `bilibili_collect_task` tool when the host exposes it. In this repository, the equivalent local route is the adapter started by `scripts/run_bilibili_api.ps1`: send the same JSON body once to `http://127.0.0.1:8102/collect-task`. Submit one complete task instead of calling search and comment routes separately; never run both paths for the same task.

## Workflow

1. Extract every requested keyword, sort order, time range, video count, pinned BV ID, pinned image-text/dynamic ID or URL, comment limit, and danmaku limit.
2. Put every user-provided BV号、视频链接、图文动态ID或链接 into the single `pinned_contents` list. The service classifies each reference; never replace a fixed item with a search result.
4. Put independent keyword searches in `searches` in the user's requested order. Current keyword search returns videos only; image-text/dynamic posts require a fixed ID or URL.
5. Use `default_comments_per_content` for the shared limit and `comments_per_content` only when the user explicitly requests a different limit for one item.
6. Call `bilibili_collect_task` exactly once with the complete JSON request.
7. Read `status`, `warnings`, `data.videos`, `data.posts`, actual comment/danmaku counts, and `selection_reasons` before reporting completion.

Read [references/api-contract.md](references/api-contract.md) before constructing the request. The authoritative request Schema is `../../../schemas/bilibili-collect-task.schema.json` (relative to this Skill directory).

## Rules

- Use BV IDs for videos, never `av` IDs. Use numeric dynamic IDs or complete supported Bilibili links for image-text/dynamic posts.
- Map 综合排序 to `totalrank`, 播放量 to `click`, and 最新发布 to `pubdate`.
- Use one comment-limit contract for videos and dynamics; keep video-only danmaku limits separate.
- Do not invent comments or danmaku when the platform returns fewer than requested.
- Do not retry the whole task automatically after `partial_success`; report failed videos/posts and preserve successful data.
- Treat collected material as a bounded public sample, not as all Bilibili users.
- Do not expose Cookie values, browser ports, commenter identities, danmaku sender hashes, or local file paths.
