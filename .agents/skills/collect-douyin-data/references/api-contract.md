# 抖音采集工具契约

工具：`douyin_collect_task`

服务：`POST http://host.docker.internal:8101/collect-task`

向 Dify 工具的 `request_json` 传入完整 JSON 字符串：

```json
{
  "searches": [
    {
      "keyword": "真珠",
      "order": "comprehensive",
      "publish_time": "all",
      "max_videos": 3,
      "page_budget": 3
    }
  ],
  "pinned_video_ids": ["7658314504920452403"],
  "default_comments_per_video": 50,
  "comments_per_video": {
    "7658314504920452403": 100
  },
  "include_replies": false,
  "comment_mode": "api_only"
}
```

`searches` 与 `pinned_video_ids` 至少一项非空。最终唯一视频最多 20 个。固定 ID 优先，搜索结果按计划顺序补入。服务按视频并发 3，单视频内部评论分页保持顺序。

响应重点：

- `status`: `success / partial_success / failed`
- `data.videos[]`: 视频详情与一级评论
- `selection_reasons`: `pinned` 或命中的搜索计划
- `comments.requested_count / returned_count`: 请求量与平台实际返回量
- `warnings`: 搜索失败或未使用的覆盖参数
