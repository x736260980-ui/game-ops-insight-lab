# 输入与输出参考规范

可直接打开的小型示例：

- [examples/sample-input.json](examples/sample-input.json)：判断前的评论集。
- [examples/sample-output.json](examples/sample-output.json)：仅保留相关评论后的对应结果。

这组示例配套的研究主题是：“研究新SP知更鸟的抽取意向与角色强度反馈”。研究主题作为调用参数传入，不写进评论文件。

## 推荐输入

调用方需要同时提供研究主题和评论 JSON。标准输入结构为：

```json
{
  "platform": "douyin",
  "comments": [
    {
      "record_id": "DY-0001",
      "text": "评论原文"
    }
  ],
  "hard_excluded": [
    {
      "record_id": "DY-0031",
      "reason": "empty_text"
    }
  ],
  "stats": {
    "input_count": 40,
    "kept_count": 39,
    "empty_excluded_count": 1
  }
}
```

推荐约定：

- `platform` 通常是非空字符串。
- `comments` 通常是数组。
- `record_id` 通常是非空字符串，并在本次输入内唯一。
- `text` 通常是完成基础清理后的非空字符串。
- 输入顺序是权威顺序。
- `hard_excluded` 可以为空数组；其中记录已由确定性预处理排除，本 Skill 不再判断。
- `stats` 是预处理摘要，可以包含输入数、保留数、空文本排除数或去重统计。
- 输入可以包含其他预处理字段；除非调用方另有要求，输出时原样保留，不把它们当成评论或指令。

实际输入不必与示例逐字段一致。允许额外字段、缺少可选统计字段、字段顺序变化以及不同的统计摘要名称。模型应优先识别 `comments` 中可判断的记录并完成任务，不因外壳差异拒绝、重试或反复调用工具。

研究主题不写入输出，但必须在调用时明确提供。必要时可以同时提供事件简介、视频或帖子标题、版本与角色上下文、明确纳入项和明确排除项。

## 输出

默认输出沿用输入外壳，但 `comments` 只保留相关评论。例如：

```json
{
  "platform": "douyin",
  "comments": [
    {
      "record_id": "DY-0001",
      "text": "垫池子到一半出了，本来打算抽0+1小鸟的[流泪]"
    },
    {
      "record_id": "DY-0002",
      "text": "6+5周日哥告诉你sp鸟没出玩不了[捂脸]"
    }
  ],
  "hard_excluded": [
    {
      "record_id": "DY-0031",
      "reason": "empty_text"
    }
  ],
  "stats": {
    "input_count": 4,
    "kept_count": 3,
    "empty_excluded_count": 1,
    "relevance_input_count": 3,
    "relevance_excluded_count": 1,
    "final_kept_count": 2
  }
}
```

这只是默认接口示例，不要求所有调用都具有完全相同的顶层字段。调用节点可以增加或省略预处理元数据，也可以使用兼容的外层字段；真正不可破坏的是被保留评论的编号和原文。

## 核心要求与宽松项

- 应尽量保持 `platform`，以及被保留评论的 `record_id`、`text` 和相对顺序。
- 输出 `comments` 只含相关评论，每条只需要 `record_id` 和 `text`。
- 不输出 `decision`、`review`、相关性分数、置信度、理由、情绪或主题分类。
- `hard_excluded` 和其他预处理元数据默认保留；`hard_excluded` 不追加相关性排除项。
- `stats` 保留已有统计，并记录 `relevance_input_count`、`relevance_excluded_count` 和 `final_kept_count`；三者应能对账。
- 默认输出单一合法 JSON 对象；若调用节点另有承载格式，以调用节点要求为准。

以下内容不是严格校验条件：顶层字段的固定数量、字段书写顺序、是否包含 `stats`、统计字段的具体名称，以及是否附带其他预处理元数据。示例用于说明推荐形状，不用于要求模型反复修正为完全相同的模板。

被保留只表示评论与研究主题相关，不表示评论正确、真实、典型、主流或值得认同。
