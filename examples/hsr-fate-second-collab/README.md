# 《崩坏：星穹铁道》× Fate 二次联动案例

这是 Game Ops Insight Lab 的首个脱敏公开案例，用于展示从三平台评论到运营判断的完整证据链。案例不包含用户名、账号信息、原始抓取文件、浏览器登录态或 Agent Session。

## 研究问题

玩家如何评价 Fate 二次联动的剧情演出、原作还原、角色呈现、抽卡规则和整体体验？这些反馈暴露了什么运营风险？

## 样本口径

- 881 条基础清理后的公开评论进入相关性判断；
- 650 条与研究主题相关；
- 高同质折叠后形成 615 条代表记录；
- 按 `support_count` 最终计入 648 条玩家表达；
- 来自抖音、Bilibili 和小红书；分类为非互斥统计。

## 核心判断

联动具有较强传播力、角色吸引力和后续实装需求，但上线后的剧情演出、设定融合与部分视觉交付没有完全兑现长期预热形成的期待。因此，“联动对象受欢迎”和“整体联动是否做得好”在当前样本中同时成立，并形成明显分化。

- 运营风险：`0.4 / middle`
- 判断置信度：`middle`
- 直接评价整体联动或表达行为反应的 86 条评论中，正向 41.86%，负向 40.70%；
- 最大讨论类别为剧情与演出，共 240 条；
- Web Research 只用于背景和定性佐证，不进入评论统计。

## 文件说明

- `dashboard.json`：Dashboard 的统计、类别与代表证据；
- `analysis-input.json`：匿名编号后的评论分析输入；
- `semantic-analysis.json`：评论类别、情绪与纳入结果，支持 Drill-down；
- `final-analysis.md`：完整运营分析；
- `final-summary.json`：单/双 Agent 共用的 Dashboard 摘要协议。

在仓库根目录复制案例后即可让 Dashboard 读取：

```powershell
Copy-Item -Recurse .\examples\hsr-fate-second-collab .\runs\hsr-fate-second-collab
.\insight-dashboard\start-dashboard.cmd
```

公开评论仍属于原作者。本案例仅保留研究所需的匿名文本片段和稳定记录编号，用于说明方法与结果边界。
