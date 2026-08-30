# SQLite 数据层 Agent 使用规范

本文件用于让 Codex、Claude 或其他本地 Agent 在后续任务中直接选择正确查询方式，不需要临时重新设计 SQL。

## 固定位置与边界

- 数据库固定为：当前仓库根目录下的 `data/game_ops.db`。
- 使用 Python 标准库 `sqlite3`，统一通过 `storage.repository.Repository` 或 `python -m storage.query` 访问。
- `runs/<run_id>/` 中的 JSON/Markdown 仍是单次研究权威产物；SQLite 是跨事件索引，不反向修改分类、评论或 Dashboard。
- 不把 `support_count` 当成独立玩家人数。
- 不从数据库推断 Cookie、身份、真实付费、留存或玩家总体比例。

## 查询选择

### 1. 不知道有哪些事件

先列事件：

```powershell
python -m storage.query events
```

### 2. 已知事件，只需要结构化筛选

按事件读取评论，可选平台和总体情绪：

```powershell
python -m storage.query comments jingliu-20260825-1953 --platform bilibili --sentiment negative --limit 50
```

按原始动态类别读取：

```powershell
python -m storage.query category jingliu-20260825-1953 <category_id> --limit 50
```

类别必须使用该 run 原始 `classification-plan.json` 中的 `category_id`，不得自行重命名后查询。

### 3. 需要寻找包含某个表达的评论

跨事件搜索：

```powershell
python -m storage.query search "角色待遇" --limit 50
```

排除当前事件做历史复核：

```powershell
python -m storage.query search "付费加强" --exclude-event current-event-id --sentiment negative --limit 30
```

在已知事件中搜索：

```powershell
python -m storage.query search "专武" --event jingliu-20260825-1953 --limit 50
```

同时过滤事件、平台、情绪和类别：

```powershell
python -m storage.query search "联动" `
  --event hsr-fate-second-collab-3platform-rerun-20260829 `
  --platform bilibili `
  --sentiment negative `
  --category overall_collab_response `
  --limit 30
```

多个空格分隔的词按“同时包含”处理。当前关键词检索不理解同义词；“卖新卡工具”不会自动等同于“逼氪”或“抬新踩旧”。需要语义相似检索时，等未来 embedding/Vec1 层完成后再使用。

### 4. 需要 Persona 或模拟结果

```powershell
python -m storage.query persona P1
python -m storage.query simulations --persona P1
```

Persona 输出属于虚拟玩家模拟，不得计入真实评论统计。

## Python API

只有需要在脚本中继续处理结果时才直接使用 Python：

```python
from storage.repository import Repository

repo = Repository("data/game_ops.db")
results = repo.search_comments(
    "角色待遇",
    event_id="feiying",
    sentiment="negative",
    limit=50,
)
```

普通人工查询优先使用 `python -m storage.query`，避免每次重写临时 SQL。

## 新事件导入

新 run 完成 `analysis-input.json`、`classification-plan.json`、`semantic-analysis.json` 和 `dashboard.json` 后先执行证据导入：

```powershell
python -m storage.import_run .\runs\<run_id> --db .\data\game_ops.db
```

最终 `final-analysis.md` 与 `final-summary.json` 完成后，再单独写入分析：

```powershell
python -m storage.upsert_analysis .\runs\<run_id> --mode single --db .\data\game_ops.db
```

若启用历史复核，必须在当前事件初判后执行：

```powershell
python -m storage.context_pack .\runs\<run_id> --query "自然语言主题" --limit 30
```

检查命令输出：

- `comment_count` 应等于 `analysis-input.json` 的代表评论数量。
- `represented_count` 应等于全部 `support_count` 之和。
- `included_represented_count` 应与 `dashboard_final_analyzed_count` 一致。
- 有 warning 时先检查源文件口径，不得为了消除 warning 擅自补造或重分类数据。
- Evidence Import 不应增加 `analyses`；Analysis Upsert 不应修改评论和分类数量。
