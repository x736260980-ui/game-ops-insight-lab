# Dashboard 与证据回溯

Dashboard 的主数据源是事件目录中的 `dashboard.json`。存在根目录 `final-summary.json` 时，后端自动补充核心判断、风险、关键发现和运营方向。旧调查可以继续回退读取 `dual-agent/05-final-summary.json`；没有摘要的普通调查仍可展示分类与评论证据。

## 展示口径

- 总体情绪环图描述当前样本，不表示全体玩家态度。
- 玩家讨论类别允许多标签，类别比例不能相加为总体比例。
- 点击类别后先展示代表评论，再展示按正向、负向、中性或混合筛选的全部评论。
- UI 同时显示 `support_count` 加权表达数和折叠后的代表记录数。
- 评论卡使用“代表 N 条相似表达”，避免把代表卡片数误解为原始评论数。

Dashboard 是结果层，不展示 Agent 的内部对话。README 和技术文档可以单独展示双 Agent 机制。

## 最终结果注入

当根目录 `final-summary.json` 完成后运行：

```powershell
python .\scripts\inject_analysis_summary.py .\runs\<run_id>
```

脚本只写入 `analysis_summary`，并对 `counts`、`platforms`、`overall_sentiment`、`categories` 和最终纳入数量计算保护哈希；这些评论统计发生变化时必须停止。后端仍保留对旧案例的动态读取兼容。
