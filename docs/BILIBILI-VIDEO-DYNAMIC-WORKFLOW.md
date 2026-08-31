# B站视频与图文动态统一采集流程

## 目标

B站只运行一个本地服务：`http://127.0.0.1:8102`。正式任务只调用一次：

```text
POST /collect-task
```

调用方不需要判断输入是视频还是图文动态。8102 根据内容引用自动分类：

- `BV...` 或 `/video/BV...`：视频；
- 纯数字动态ID、`/opus/<id>` 或 `t.bilibili.com/<id>`：图文/动态。

关键词搜索当前只返回视频。图文动态需要提供固定ID或链接。

## 输入

```json
{
  "searches": [
    {
      "keyword": "4.5末日幻影膨胀",
      "order": "totalrank",
      "publish_time": "all",
      "max_videos": 3,
      "page_budget": 3
    }
  ],
  "pinned_contents": [
    "BV1XPuo6uES8",
    "https://www.bilibili.com/opus/1242626908874604548"
  ],
  "default_comments_per_content": 200,
  "comments_per_content": {
    "BV1XPuo6uES8": 500
  },
  "default_danmaku_per_video": 0,
  "include_replies": false
}
```

`pinned_contents` 最多20项，可混合视频和图文动态。`comments_per_content` 的键也会自动规范化；视频弹幕设置只对BV视频生效。

## 服务内部处理

```text
统一任务请求
  → 规范化并识别 pinned_contents
  → 搜索视频候选
  → 固定视频＋搜索视频合并去重
  → 视频详情、一级评论、可选弹幕
  → 图文动态详情、图片链接、一级评论
  → 一个统一响应
```

响应结构：

```json
{
  "platform": "bilibili",
  "operation": "collect_task",
  "status": "success",
  "data": {
    "videos": [],
    "posts": []
  },
  "meta": {
    "video_count": 0,
    "post_count": 0,
    "content_count": 0
  },
  "warnings": []
}
```

`/collect` 和 `/collect-dynamic` 仅保留为本地排障组件，正式Skill和Cloud流程不调用。

## 文件落地与Base Clean

推荐把统一响应原样保存为：

```text
runs/<run_id>/raw/bilibili-collection-result.json
```

或按当前运行目录习惯保存到 `incoming/bilibili-raw.json`。原始文件不得被后续清洗覆盖。

编号：

```powershell
E:\codex-workspace\MediaCrawler\source\.venv\Scripts\python.exe `
  E:\codex-workspace\MediaCrawler\scripts\prepare_bilibili_relevance.py `
  --input "<run-dir>\raw\bilibili-collection-result.json" `
  --output "<run-dir>\bilibili-numbered.json" `
  --target "<研究主题>"
```

编号脚本同时读取 `data.videos[]` 和 `data.posts[]`，按原始评论ID去重，统一生成稳定的 `BILI-xxxx`。历史任务若分别保存视频与图文文件，可把两个路径一起传给 `--input`。

去空：

```powershell
E:\codex-workspace\MediaCrawler\source\.venv\Scripts\python.exe `
  E:\codex-workspace\MediaCrawler\scripts\dedup_empty_comments.py `
  "<run-dir>\bilibili-numbered.json" `
  "<run-dir>\bilibili-base-cleaned.json"
```

从 `bilibili-base-cleaned.json` 开始，相关性判断、同质折叠、分类、情绪、Dashboard和SQLite流程均不再区分评论来自视频还是图文。需要追溯时回查原始文件中的内容ID和评论ID。

## 运行边界

- 先检查 `GET /health?check_login=true`，确认 `logged_in=true`；未登录时可能只能获得少量预览评论。
- 平台返回不足时如实保留实际数量，不伪造到请求上限。
- 每个内容最多请求1000条一级评论；不采集二级回复。
- B站视频与图文属于同一平台样本，但不能据此推断全体玩家意见。
- Cookie、浏览器用户目录和登录资料不进入任何同步包。
