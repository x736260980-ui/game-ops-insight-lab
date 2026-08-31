# B站采集工具契约

工具：`bilibili_collect_task`

服务：Dify 中为 `POST http://host.docker.internal:8102/collect-task`；本仓库本地为 `POST http://127.0.0.1:8102/collect-task`。

向 Dify 工具的 `request_json` 传入完整 JSON 字符串：

```json
{
  "searches": [
    {
      "keyword": "真珠",
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
  "default_comments_per_content": 50,
  "comments_per_content": {
    "BV1XPuo6uES8": 100,
    "1242626908874604548": 200
  },
  "default_danmaku_per_video": 50,
  "danmaku_per_video": {
    "BV1XPuo6uES8": 100
  },
  "include_replies": false
}
```

`searches` 与 `pinned_contents` 至少一项非空。`pinned_contents` 可混合 BV号、B站视频链接、动态数字ID和 `opus/t.bilibili.com` 链接，服务自动分类。关键词搜索当前只返回视频；图文/动态必须提供固定ID或链接。每次最多固定20个内容，固定内容优先，搜索结果按计划顺序补入。单类内容最多并发3，单内容内部评论分页保持顺序。

响应重点：

- `status`: `success / partial_success / failed`
- `data.videos[]`: 视频详情、一级评论与弹幕
- `data.posts[]`: 图文/动态正文、图片链接、回复主题和一级评论
- `selection_reasons`: 视频为 `pinned/search`，图文/动态为 `pinned_dynamic`
- `comments`、`danmaku` 中的请求量与实际返回量
- `warnings`: 搜索失败或未使用的覆盖参数

下游清洗可把同一响应中的 `data.videos[]` 与 `data.posts[]` 一起输入 `prepare_bilibili_relevance.py`，统一生成稳定的 `BILI-xxxx` 编号。原文保持不变，视频和图文不会跨内容改写。
