# 游戏调研看板

这是 Game Ops Insight Lab 调研产物的本地浏览看板。它由 FastAPI 提供 API 与已构建的前端文件；日常查看不需要启动 Vite 开发服务器，也不包含数据库或任务控制功能。

## 数据目录与文件职责

看板自动读取仓库根目录的 `runs/`：`game-ops-insight-lab/runs/<调查目录>/`。每个可显示的调查至少需要：

```text
game-ops-insight-lab/
├─ runs/
│  └─ <调查目录>/
│     ├─ dashboard.json  # 看板列表、统计、分类与证据的结构化数据（必需）
│     ├─ final-analysis.md  # 可选的统一 Markdown 报告
│     └─ final-summary.json # 可选的统一 Dashboard 分析摘要
└─ insight-dashboard/
```

- `dashboard.json` 是看板的主数据源；只要它存在且为合法 JSON，该调查就会出现在列表中。
- `final-analysis.md` 和 `final-summary.json` 是单/双 Agent 共用的统一结果。旧调查仍兼容 `dual-agent/05-final-*` 和 `report.md`；没有报告或摘要不影响分类与评论浏览。

## 首次安装

需要 Python 3.11+、Node.js 20.19+ 或 22.12+（含 npm；Vite 8 的要求）。在本目录打开终端后执行：

```powershell
python -m pip install -r requirements.txt
npm install
npm run build
```

`npm run build` 会生成 `dist/index.html`。启动器会检查该文件；若缺失，会明确提示再次执行 `npm install` 和 `npm run build`。

## 日常启动

在 `MediaCrawler/insight-dashboard` 目录执行：

```powershell
python start_dashboard.py
```

默认监听 `http://127.0.0.1:8090`，并在约 1 秒后自动打开浏览器。也可在 Windows 中双击 `start-dashboard.cmd`；它只调用同一个 Python 启动入口。

常用参数：

```powershell
# 不自动打开浏览器
python start_dashboard.py --no-browser

# 改用其他地址或端口
python start_dashboard.py --host 0.0.0.0 --port 9010
```

服务运行时按 `Ctrl+C` 即可停止。

## 新调查与刷新

当上游流程在仓库 `runs/` 下新增一个包含 `dashboard.json` 的调查目录后，无需重启服务。回到调查列表点击“刷新”，或直接刷新浏览器页面，新调查就会自动出现。列表会按 `dashboard.json` 的 `generated_at`（缺失时按文件修改时间）从新到旧排列。

## 开发模式

只有修改前端 TypeScript/React/CSS 时才需要 Vite。由于 `start_dashboard.py` 会先校验 `dist/index.html`，首次进入开发模式也要先构建一次：

```powershell
npm install
npm run build
npm run dev
```

开发服务器会把 `/api/dashboard` 代理给 `http://127.0.0.1:8090`，因此仍需另开一个终端运行 `python start_dashboard.py --no-browser`。完成前端修改后，停止 Vite 并执行 `npm run build`，日常使用仍只启动 Python 入口。

如果只想在没有 `dist/` 的情况下调试 API，可改用不执行静态产物检查的命令：

```powershell
python -m uvicorn app:app --host 127.0.0.1 --port 8090
```

## API

服务地址默认为 `http://127.0.0.1:8090`：

- `GET /api/dashboard/health`：健康检查。
- `GET /api/dashboard/runs`：调查摘要列表。
- `GET /api/dashboard/runs/{run_id}`：单个调查的完整 `dashboard.json` 数据。
- `GET /api/dashboard/runs/{run_id}/report`：读取可选的 `report.md`；文件不存在时返回 404。

## 常见错误

- **提示找不到 `dist/index.html`**：在本目录运行 `npm install`，再运行 `npm run build`。
- **`ModuleNotFoundError: fastapi` 或 `uvicorn`**：运行 `python -m pip install -r requirements.txt`，并确认使用的是启动器对应的 Python。
- **浏览器无法访问**：确认终端仍在运行，地址与端口和启动参数一致；若端口被占用，可使用 `--port 9010`。
- **看板没有任何调查**：确认数据放在 `MediaCrawler/runs/<调查目录>/dashboard.json`，且 JSON 格式合法。
- **报告接口返回 404**：该调查没有 `report.md`；这不会影响正常看板查看。
