---
name: collect-xiaohongshu-data
description: 使用本地8103小红书 MediaCrawler FastAPI，按关键词搜索或完整笔记链接采集笔记详情和一级评论。
---

# 小红书数据采集

使用仓库脚本 `scripts/run_xiaohongshu_api.ps1` 启动的 `http://127.0.0.1:8103` 独立服务。正式任务优先调用一次 `POST /collect-task`；`/search` 和 `/collect` 只用于分步调试。

## 输入决策

- 用户给出研究关键词：写入 `searches`，每个关键词一个搜索对象。
- 用户指定笔记：必须传浏览器地址栏中的完整笔记链接到 `pinned_note_urls`。链接必须含 `xsec_token`；不要让用户手工拆 Cookie 或令牌。
- 两者同时存在：一起提交，服务会先保留固定笔记，再合并搜索结果并按 `note_id` 去重。
- 用户未指定数量时，每个关键词默认 3 篇、每篇 50 条一级评论。

## 固定约束

- `include_replies` 始终为 `false`，不请求二级评论。
- 单次最终最多 20 篇笔记，并发最多 3。
- 不下载图片或视频，不采集创作者主页。
- 采集前可调用 `GET /health?check_login=true`；未登录时提醒用户在 9224 的小红书 Chrome 窗口登录。
- `xsec_token` 只在当前请求内使用，不写入提交、报告或可分享的派生文件；`source_url` 若含令牌也按同样规则脱敏。可安全保留 `note_id`、`xsec_source` 和不含令牌的来源说明供追溯。

详细请求格式见 [API约定](references/api-contract.md)。
