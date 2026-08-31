---
name: build-game-comment-dashboard
description: Use when folded game comments need a user-approved dynamic taxonomy, a conservative second relevance gate, multi-label aspect sentiment analysis, representative source comments, and a validated dashboard JSON.
---

# 构建游戏评论洞察看板

把 Dify 或本地清洗链产出的“相关性结果＋相似评论折叠结果”转换为可审计的游戏评论看板。语义工作由 Codex 完成，编号校验、加权计数和最终文件输出交给 `scripts/build_comment_dashboard.py`。

核心原则：语义判断与确定性统计分离。Codex 只决定是否纳入、属于哪些类别、各类别情绪和代表评论；Python 是最终数量的唯一计算者。

## 适用边界

本 Skill 只处理折叠之后的洞察看板阶段：

- 允许对明显漏网的无关评论做一次保守的二次剔除；
- 为本次研究主题生成动态类别；
- 进行多标签分类、总体情绪和类别情绪判断；
- 选择真实代表评论并生成类别摘要；
- 调用确定性脚本产出 `dashboard.json` 和 `analysis-audit.json`。

本 Skill 不执行以下工作：

- 不重新判断 Dify 已批准的折叠，不拆组或改组；
- 不重新抓取评论，不联网补充事实；
- 不改写原评论；
- 不输出严重度、运营报告、商业影响结论、用户画像或共情内容；
- 不把公开评论解释为全体玩家意见。

## 输入准备

如果已有 `analysis-input.json`，先校验再使用。如果只有相关性和折叠结果，运行：

```powershell
python scripts/build_comment_dashboard.py prepare `
  --target "本次研究主题" `
  --relevance "路径/抖音相关性.json" `
  --folded "路径/抖音折叠.json" `
  --relevance "路径/B站相关性.json" `
  --folded "路径/B站折叠.json" `
  --output-dir "路径/本次运行"
```

本地链路的折叠结果若不带 `merged_record_ids`，为对应平台增加：

```powershell
--cluster-index "路径/cluster-index.json"
```

脚本接受纯 JSON、完整 ` ```json ` 代码块，以及数组或编号映射两种 `comments` 结构。它会拒绝缺失、重复、虚构编号、被修改的代表原文和非法 `support_count`。

### 通用收件箱模式

FastAPI 只保存文件，用户决定何时让 Codex 开始。用户点名某个 `run_id` 后，先读取 `manifest.json` 并扫描：

```text
runs/<run_id>/incoming/*.json
```

以磁盘实际文件为准列出已收到的产物，再根据用户本次声明的研究范围判断是否存在实质缺口。不得根据固定文件数量、固定平台清单或文件到达顺序擅自宣布材料齐全。

将所有符合折叠评论契约的 `*-folded.json` 作为评论输入；平台数量不固定，例如可以同时包含抖音、B站、小红书或未来新增平台。其他JSON（Dify分类草案、网页背景、官方公告、调研资料等）只作为参考上下文，不得混入评论数量。

对本次实际发现的全部折叠文件运行：

```powershell
python scripts/build_comment_dashboard.py prepare-folded `
  --target "本次研究主题" `
  --folded "runs/<run_id>/incoming/douyin-folded.json" `
  --folded "runs/<run_id>/incoming/bilibili-folded.json" `
  --folded "runs/<run_id>/incoming/xiaohongshu-folded.json" `
  --output-dir "runs/<run_id>"
```

命令中的 `--folded` 数量必须按实际文件增减，不要求示例中的三个都存在。该模式把折叠文件中的 `support_count` 和 `merged_record_ids` 作为上游交接结果进行数量对账，不重新判断折叠语义，也无法核验非代表成员的原文。Dify 分类草案只作参考：读取它来发现可能的类别和分歧，但不得直接复制其中的数量、比例、严重度或 `other` 口径。正式类别、逐条标签、情绪和统计仍由 Codex 与确定性脚本重新生成。

详细字段见 [references/io-contract.md](references/io-contract.md)。需要制作或检查文件时，读取该参考。

## 两阶段工作流

### 0. 执行方式：脚本预筛 + 模型精筛（两级）

- 语义分析（逐条分类、情绪、二次相关性）可先用一个关键词/正则脚本做第一遍粗筛：脚本按词表为每条评论初分类别、初判情绪、标记候选排除，并产出 `record_id` 清单。脚本只用于加速定位、降低遗漏，不作为最终判断。
- 无论脚本给出什么结果，模型必须逐条语义复核全部评论，修正分类、情绪与排除项；脚本建议仅作起点，最终结果以模型逐条判断为准。脚本预筛命中率低或主题特殊时，直接全部交给模型判断。
- 代表评论、类别摘要与总体判断始终由模型完成；脚本不得自动决定 `include_in_dashboard` 的最终值。

### 第一阶段：生成分类草案

完整阅读研究主题和 `analysis-input.json` 的评论。根据实际出现的讨论对象生成 4—8 个动态类别，再增加固定兜底类别 `other`。

每个动态类别必须：

- 对应玩家讨论中稳定、可解释的一个具体方面；
- 使用稳定的小写英文或下划线 `category_id`；
- 有中文名称、定义、纳入条件和排除条件；
- 与相邻类别边界清楚，但不要求互斥；
- 对本次研究主题有分析价值，而不是照搬通用游戏问题清单。

分类粒度应能支持判断。不要把几乎所有评论塞进一个宽泛类别，也不要为个别评论创建一次性类别。抽卡咨询、配队询问、实战机制、视听表现、角色叙事等是否成立，取决于研究主题和实际数据，而非固定模板。

输出 `classification-plan.json`，初始必须是：

```json
{
  "schema_version": "game-comment-classification-plan-1.0",
  "plan_version": "本次研究的稳定版本号",
  "research_target": "与analysis-input完全一致的研究主题",
  "status": "draft",
  "categories": []
}
```

向用户展示类别名称、定义和关键边界。用户批准前必须停止，不得生成全量 `semantic-analysis.json`，也不得把 `status` 自行改成 `approved`。

只有一个明确例外：用户点名某个收件箱调查，并且用户已明确授权 Codex 直接完成分类、生成看板时，Codex 可以在完整检查全部折叠评论和已有参考资料后，自行修订类别并可以自行设为 `approved`，无需再次打断用户。没有这两项可观察条件时仍执行普通审批门。

用户可以修改名称、定义、边界和类别数量。只有用户确认后，才将 `status` 改为 `approved`，并运行：

```powershell
python scripts/build_comment_dashboard.py validate-taxonomy `
  --classification-plan "路径/classification-plan.json" `
  --require-approved
```

### 第二阶段：生成语义分析

以批准后的分类表为唯一类别版本，逐条覆盖 `analysis-input.comments`。可以分批判断，但合并后的 `results` 必须无遗漏、无重复、无虚构编号。

#### 二次相关性闸门

`include_in_dashboard=false` 只用于明显不回答研究主题、且进入看板会污染结论的内容。采取保守策略：

- 只要评论对研究对象提供态度、判断、问题、诉求、经验或具体信息，就优先保留；
- 语句短、表达口语化或情绪化，不等于无关；
- 抽卡咨询和配队问题是否相关，由研究主题决定；
- 仅主播互动、纯爆料源可信度闲聊、与目标对象无关的剧情闲聊等，只有在确实脱离研究主题时才排除；
- 不确定时保留并归入最合适类别或 `other`，不要为了“清洗干净”过度剔除。

排除项必须写具体 `exclusion_reason`，并设置：

```json
{
  "record_id": "DY-0001",
  "include_in_dashboard": false,
  "overall_sentiment": null,
  "aspects": [],
  "exclusion_reason": "只讨论主播开播时间，与研究主题无关"
}
```

#### 多标签与情绪

一条评论可以进入多个类别。每个类别分别判断 `positive / negative / neutral / mixed`，同时为整条评论判断一次 `overall_sentiment`。

例如“强度一般，但特效很好看”应同时进入强度和视听类别：强度为 `negative`，视听为 `positive`，总体为 `mixed`。不要把它压成一个单一类别或用总体情绪覆盖各方面情绪。

使用 `other` 时不得同时使用具体类别。`other` 只是与研究主题相关但无法归类的兜底项，不是无关评论垃圾桶。

#### 摘要与代表评论

对每个实际出现的类别生成一项 `category_outputs`：

- `summary` 概括该类别中主要观点及重要分歧，不能虚构评论没有表达的事实；
- `representative_ids` 最多两条；
- 代表评论必须已纳入看板、确实属于该类别；
- 优先选择观点典型、信息充分、表达清楚的真实评论，而非机械选择 `support_count` 最大者；
- 同一条评论可以成为不同类别的代表评论；
- 不得改写原评论，最终原文由 Python 从 `analysis-input.json` 回填。

输出结构参考 [references/io-contract.md](references/io-contract.md) 和 [references/examples/semantic-analysis.sample.json](references/examples/semantic-analysis.sample.json)。

## 最终化

完成 `semantic-analysis.json` 后运行：

```powershell
python scripts/build_comment_dashboard.py finalize `
  --analysis-input "路径/analysis-input.json" `
  --classification-plan "路径/classification-plan.json" `
  --semantic-analysis "路径/semantic-analysis.json" `
  --output-dir "路径/本次运行"
```

脚本必须成功生成：

- `dashboard.json`：UI 使用的统计和典型原评论；
- `analysis-audit.json`：分类表版本、二次排除、编号与折叠数量对账。

若脚本报错，修正语义文件中的漏号、重复号、非法类别、情绪或代表评论关系；不要绕过校验，也不要手工修改看板数字。

## 完成检查

- 分类表已经由用户明确批准，或满足“用户点名收件箱调查＋明确委托 Codex 直接完成”的例外；
- `results` 完整覆盖所有折叠后记录；
- 二次排除是保守且可解释的；
- 一条评论的多个方面没有被压成单标签；
- `overall_sentiment` 每条记录只判断一次；
- 每类代表评论不超过两条且原文未改写；
- `dashboard.json` 的总体情绪数量严格等于最终纳入数量；
- 类别统计明确标注为非互斥；
- `analysis-audit.json` 保留全部二次排除与折叠对账。
