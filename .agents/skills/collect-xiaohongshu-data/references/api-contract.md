# API约定

## 完整任务

```json
{
  "searches": [
    {
      "keyword": "星穹铁道 真珠",
      "order": "comprehensive",
      "note_type": "all",
      "max_notes": 3,
      "page_budget": 2
    }
  ],
  "pinned_note_urls": [
    "https://www.xiaohongshu.com/explore/<note-id>"
  ],
  "default_comments_per_note": 50,
  "comments_per_note": {},
  "include_replies": false
}
```

`order` 可选 `comprehensive`、`most_popular`、`newest`；`note_type` 可选 `all`、`video`、`image`。

安全约定：示例链接不包含访问令牌。真实令牌只从用户当次提供的完整链接中读取并用于本次请求，不要写入 Git、报告、共享压缩包或长期缓存；向用户展示结果时应删除令牌和带令牌的完整 URL。

## 搜索

`POST /search` 接收单个搜索对象。返回的 `data.videos[]` 实际代表小红书笔记，兼容现有双平台数据外壳；每项同时提供 `video_id` 和语义更准确的 `note_id`。

## 固定链接采集

`POST /collect` 示例：

```json
{
  "note_urls": [
    "https://www.xiaohongshu.com/explore/<note-id>"
  ],
  "default_comments_per_note": 50,
  "comments_per_note": {},
  "include_replies": false
}
```
