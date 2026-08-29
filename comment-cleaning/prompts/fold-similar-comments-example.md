# 高同质评论直接折叠：修正案例

研究主题：《崩坏：星穹铁道》SP知更鸟（水鸟）的抽取与适配讨论。

## 输入（12条）

```json
{
  "platform": "douyin",
  "comments": [
    {"record_id": "DY-0001", "text": "掉个月卡[玫瑰]"},
    {"record_id": "DY-0002", "text": "掉一个"},
    {"record_id": "DY-0009", "text": "来一张月卡[黄脸祈祷]"},
    {"record_id": "DY-0010", "text": "广东人蹲蹲月卡"},
    {"record_id": "DY-0012", "text": "来张月卡呗[色]"},
    {"record_id": "DY-0014", "text": "月卡月卡月卡，重要的事情说三遍\n[呲牙][呲牙][呲牙]"},
    {"record_id": "DY-0018", "text": "下个版本只抽知更鸟"},
    {"record_id": "DY-0024", "text": "01昔推荐换水鸟吗"},
    {"record_id": "DY-0026", "text": "昔涟光锥能用吗？"},
    {"record_id": "DY-0027", "text": "抽鸟还是等真虚[发呆]"},
    {"record_id": "DY-0028", "text": "鸟能用昔涟专吗"},
    {"record_id": "DY-0033", "text": "这个水鸟抽了对希儿有提升吗？"}
  ]
}
```

## 正确输出（12条 → 6条）

```json
{
  "platform": "douyin",
  "comments": [
    {
      "record_id": "DY-0001",
      "text": "掉个月卡[玫瑰]",
      "support_count": 6,
      "merged_record_ids": ["DY-0001", "DY-0002", "DY-0009", "DY-0010", "DY-0012", "DY-0014"]
    },
    {"record_id": "DY-0018", "text": "下个版本只抽知更鸟"},
    {"record_id": "DY-0024", "text": "01昔推荐换水鸟吗"},
    {
      "record_id": "DY-0026",
      "text": "昔涟光锥能用吗？",
      "support_count": 2,
      "merged_record_ids": ["DY-0026", "DY-0028"]
    },
    {"record_id": "DY-0027", "text": "抽鸟还是等真虚[发呆]"},
    {"record_id": "DY-0033", "text": "这个水鸟抽了对希儿有提升吗？"}
  ],
  "stats": {
    "input_count": 12,
    "output_count": 6,
    "folded_count": 6
  }
}
```

## 为什么 `DY-0024` 与 `DY-0027` 必须分开

- `DY-0024` 的条件是已有昔涟一魂，判断“换水鸟”是否值得；
- `DY-0027` 比较的是水鸟与未来真虚，替代选项和资源决策不同；
- 两者都提到抽水鸟，但账号条件、比较对象和主要理由不一致，合并会抹掉真实决策差异。

`DY-0026` 与 `DY-0028` 可以合并，因为二者都在问同一个具体问题：昔涟专属光锥能否给水鸟使用，没有增加不同条件或理由。
