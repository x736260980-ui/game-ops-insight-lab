# Game Ops Insight Lab

> 从公开玩家评论中提取可验证问题，把运营判断逐层回溯到真实证据。

Game Ops Insight Lab 是一套 **Windows 优先的游戏运营事件研究工作台**。它将 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 的公开评论采集能力，与本项目的评论清洗、语义折叠、玩家情感分析、单/双 Agent 复核和可交互 Dashboard 串成一条完整证据链。

本项目不是简单的“评论情绪总结器”：它保留样本边界、同质表达量、反向意见和原始评论编号，不把有限社媒样本包装成全体玩家民调，也不根据评论推断真实流水、留存或退游规模。

## 项目展示

| Dashboard 总览 | Codex × Claude 双 Agent CMD |
|:---:|:---:|
| <img width="2499" height="1236" alt="Game Ops Insight Dashboard" src="https://github.com/user-attachments/assets/b9011a52-966f-4cf6-af55-277657d03897" /> | <img width="1735" height="926" alt="Codex 与 Claude 双 Agent 讨论" src="https://github.com/user-attachments/assets/a8c54d25-980b-4a1c-9985-948c3059a44d" /> |

## 它解决什么问题

| 常见问题 | 本项目的处理方式 | 最终可验证结果 |
|:---|:---|:---|
| 短评论容易被当作无效内容 | 只要对象明确且能贡献态度、体验或行为信号，就保留 | “建模不错”“剧情太少”仍进入分析 |
| 去重后看不出真实表达量 | 高同质折叠保留 `support_count` | 同时展示代表记录数与加权表达数 |
| 情绪总结缺少证据 | 每条代表评论保留稳定编号和真实原文 | 结论可回溯到类别、情绪和评论 |
| Agent 容易把猜测写成事实 | 强制区分评论证据、网页背景与待核实推断 | 报告明确保留证据边界和反向意见 |
| 所有事件都跑双模型成本过高 | 普通事件走单 Agent，复杂争议按需交叉讨论 | 两种路径输出同一份稳定协议 |

## 完整工作流

```text
┌──────────────────────────────────────────────────────────────────────┐
│                            研究主题                                  │
│                事件对象 · 玩家群体 · 研究问题边界                      │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         公开评论与背景采集                            │
│             抖音 · Bilibili · 小红书 · 网页背景资料                    │
│                         MediaCrawler                                 │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                            证据处理                                  │
│       去空与稳定编号 → 相关性筛选 → 高同质表达折叠                      │
│              保留真实原文、support_count 与评论编号                    │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                       动态分类与玩家情绪                              │
│          类别 · 情绪 · 代表评论 · 反向意见 · 证据边界                   │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                       按事件复杂度选择分析路径
                 ┌───────────────┴───────────────┐
                 │                               │
                 ▼                               ▼
┌──────────────────────────────┐   ┌──────────────────────────────────┐
│        单 Agent 分析         │   │       Codex × Claude 双 Agent     │
│                              │   │                                  │
│  普通调查默认路径             │   │  复杂争议对等讨论                  │
│  更快、更节省模型额度         │   │  两份盲审 → 议题 → 交叉验证         │
└───────────────┬──────────────┘   └────────────────┬─────────────────┘
                │                                   │
                └─────────────────┬─────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          统一结果协议                                 │
│                   final-analysis.md                                  │
│                   final-summary.json                                 │
└────────────────────────────────┬─────────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Insight Dashboard                            │
│                结论 → 类别 → 情绪 → 评论证据                           │
│                    逐层回溯真实玩家表达                                │ 
└──────────────────────────────────────────────────────────────────────┘
```

采集层使用固定版本的 MediaCrawler 子模块；清洗后的分析与展示逻辑由本仓库实现。普通调查默认单 Agent，只有用户明确要求复核时才启动双 Agent，避免为了形式消耗第二个模型。

### 单 Agent 与双 Agent 如何选择

| 分析路径 | 适用场景 | 过程 | 权威输出 |
|:---|:---|:---|:---|
| **单 Agent** | 常规版本反馈、问题结构清晰、风险较低 | 基于分类结果和评论证据独立分析 | `final-analysis.md` + `final-summary.json` |
| **双 Agent** | 根因存在竞争解释、玩家群体明显分化、信任与机制问题交织 | 两份盲审 → 提名实质议题 → 对等讨论 → 统一终稿 | 同一套 `final-analysis.md` + `final-summary.json` |

Dashboard 不区分报告来自哪条路径；双 Agent 的初审、议题和对话只作为后台审议过程保留，不占据业务页面主体。

## 30 秒案例：Fate 二次联动

[查看完整脱敏案例 →](examples/hsr-fate-second-collab/README.md)

| 数据阶段 | 结果 | 含义 |
|:---|---:|:---|
| 基础清理评论 | 881 条 | 进入相关性判断的公开评论 |
| 相关评论 | 650 条 | 与研究问题确实相关 |
| 折叠代表记录 | 615 条 | 只合并高度同质表达 |
| 最终计入表达 | 648 条 | 按 `support_count` 加权 |
| 最大议题 | 剧情与演出，240 条 | 样本内最集中的讨论方向 |
| 整体联动直接评价 | 正向 41.86% / 负向 40.70% | 评价明显分化，而非单边口碑 |

> **核心判断：** 联动的传播力和角色吸引力较强，但剧情演出、设定融合与部分视觉交付没有完全兑现长期预热形成的期待；当前表现为中等运营风险，而不是已经证实的信任危机或商业损失。

## 关键设计

| 设计 | 核心规则 | 为什么重要 |
|:---|:---|:---|
| **相关性优先** | 对象明确的有效短句也保留 | 避免系统只留下会写长评的玩家 |
| **高同质折叠** | 对象、方面、立场、判断和理由均高度一致才合并 | 减少复读，同时不抹掉表达数量 |
| **动态分类** | 分类围绕当前事件生成，类别非互斥 | 不把不同事件强塞进固定情绪标签 |
| **证据回溯** | 结论关联类别、情绪、代表评论与原始编号 | 运营判断能够被复查，而非只看模型结论 |
| **边界约束** | 官方动机、商业结果和样本外规模默认待核实 | 防止有限评论被包装成全体玩家事实 |

## 项目结构

```text
.agents/skills/game-ops-insight-suite/  一体化 Codex Skill
adapter/                               三平台 FastAPI 适配层
comment-cleaning/                      相关性与折叠协议
dual-agent/                            Codex × Claude 主持程序
examples/                              脱敏精选案例
insight-dashboard/                     FastAPI + React Dashboard
scripts/                               确定性处理与启动脚本
schemas/                               采集任务 Schema
source/                                MediaCrawler 固定版本子模块
```

## 快速开始（Windows）

需要 Python 3.11、Node.js 20.19+、Git for Windows 和 Chrome。双 Agent 模式还需要已安装并登录的 Codex CLI 与 Claude CLI。

```powershell
git clone --recurse-submodules https://github.com/x736260980-ui/game-ops-insight-lab.git
cd game-ops-insight-lab
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

查看公开案例：

```powershell
Copy-Item -Recurse .\examples\hsr-fate-second-collab .\runs\hsr-fate-second-collab
.\insight-dashboard\start-dashboard.cmd
```

启动三平台采集服务：

```powershell
.\scripts\run_douyin_api.ps1
.\scripts\run_bilibili_api.ps1
.\scripts\run_xiaohongshu_api.ps1
```

按需启动双 Agent：

```powershell
.\dual-agent\start_dual_agent.cmd
```

在 Codex 中也可以直接调用仓库 Skill：

```text
使用 $game-ops-insight-suite，研究指定游戏运营事件。默认先走单 Agent；只有我明确确认时才启动双 Agent。
```

## 稳定输出协议

每次调查使用独立目录：

```text
<run>/
├─ analysis-input.json
├─ semantic-analysis.json
├─ classification-plan.json
├─ dashboard.json
├─ final-analysis.md
├─ final-summary.json
└─ dual-agent/                 仅双 Agent 调查存在
   ├─ 01-codex-initial.md
   ├─ 02-claude-initial.md
   ├─ 03-transcript.md
   └─ 04-disputes.json
```

`final-summary.json` 使用 `game-ops-final-summary-1.0`：风险为 `0—1` 分数并映射为 `low / middle / high`，置信度单独描述证据强弱。

## 研究边界

- 公开评论是带有平台和采样偏差的玩家信号，不代表全体玩家；
- 分类为非互斥统计，类别比例不能相加成总体比例；
- 玩家关于官方动机、销量、退游或付费变化的说法默认属于待核实内容；
- 网页资料只用于背景、定性佐证和反向信号，不进入评论数量与情绪统计；
- Dashboard 展示研究结果，Agent 的完整对话不进入业务页面主体。

## 开源与第三方许可

本仓库原创代码使用 [MIT License](LICENSE)。

评论采集部分通过 Git 子模块使用 [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)，固定兼容提交为 `d6f7c5bb906b6dac40ddf343ef9e26438a3de092`。MediaCrawler 使用 `NON-COMMERCIAL LEARNING LICENSE 1.1`，仅限非商业学习与研究，其许可证不受本项目 MIT License 覆盖。详见 [第三方组件说明](THIRD_PARTY_NOTICES.md)。

## 项目演进

早期版本基于 Dify 工作流，侧重多 Agent 编排与长期记忆；当前版本转向本地可复现、证据有边界、结果可回溯的研究工作台。历史版本保留在 [Dify--trend-crawler](https://github.com/x736260980-ui/Dify--trend-crawler)。

