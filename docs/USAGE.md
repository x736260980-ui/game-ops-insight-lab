# 使用说明

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

需要从中间阶段继续或检查完整流程时，使用总调度 Skill：

```text
使用 $run-game-player-research，读取当前 run-manifest，从下一个未完成阶段继续，不重跑已完成阶段。
```

SQLite 文件默认只生成在仓库的 `data/` 目录，并已从 Git 排除：

```powershell
python -m storage.db init --db .\data\game_ops.db
python -m storage.import_run .\runs\<run_id> --db .\data\game_ops.db
python -m storage.query search "角色待遇" --exclude-event <current_event_id> --limit 30
python -m storage.upsert_analysis .\runs\<run_id> --mode single --db .\data\game_ops.db
```


## 稳定输出协议

每次调查使用独立目录：

```text
<run>/
├─ run-manifest.json
├─ research-brief.md
├─ analysis-input.json
├─ semantic-analysis.json
├─ classification-plan.json
├─ dashboard.json
├─ final-analysis.md
├─ final-summary.json
├─ analysis/
│  └─ initial-analysis.md
├─ retrieval/                  仅启用历史复核时存在
│  ├─ historical-context.json
│  └─ historical-context.md
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
