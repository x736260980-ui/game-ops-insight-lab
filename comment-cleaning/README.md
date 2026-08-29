# 评论相关性清洗与高同质折叠

本流程读取 `prepare_douyin_relevance.py` 或 `prepare_bilibili_relevance.py` 生成的简化编号 JSON。程序本身不调用模型：它准备 LLM 输入、验证 LLM 输出、等待人工决定并生成最终极简数据。

## 文件流

1. `relevance-request.json`：删除空评论后的相关性 LLM 输入。
2. `hard-excluded.json`：被确定性删除的空评论编号。
3. `relevance-scores.json`：验证后的 LLM 分数。
4. `relevance-review.json`：只包含 `0.30 <= score < 0.70` 的人工审核项。
5. `relevance-result.json`：自动高分与人工保留项的合集。
6. `cluster-request.json`：高同质聚类 LLM 输入。
7. `cluster-review.json` / `cluster-review.md`：聚类机器审核文件与人类阅读版。
8. `cluster-index.json`：批准折叠后的成员关系。
9. `final-cleaned-comments.json`：最终交给下游的极简数据。

所有步骤使用同一个 `run-dir`。示例中的 Python 是 MediaCrawler 虚拟环境解释器。

## 1. 准备相关性输入

```powershell
.\source\.venv\Scripts\python.exe `
  .\scripts\comment_cleaning_pipeline.py prepare `
  --input .\collection-data\numbered-comments\douyin-relevance-input.json `
  --run-dir .\runs\cleaning-demo `
  --target "研究玩家对目标角色塑造的评价"
```

将 `relevance-request.json` 与 `prompts/relevance-scoring.md` 交给 LLM，把纯 JSON 输出保存为任意文件。

## 2. 校验分数并生成相关性审核队列

```powershell
.\source\.venv\Scripts\python.exe `
  .\scripts\comment_cleaning_pipeline.py route-relevance `
  --run-dir .\runs\cleaning-demo `
  --scores .\path\to\llm-relevance-scores.json
```

编辑 `relevance-review.json`，把每个 `human_decision` 从 `pending` 改为 `keep` 或 `exclude`，然后运行：

```powershell
.\source\.venv\Scripts\python.exe `
  .\scripts\comment_cleaning_pipeline.py finalize-relevance `
  --run-dir .\runs\cleaning-demo
```

只要还有 `pending`，程序就会停止。

## 3. 审核高同质折叠

将 `cluster-request.json` 与 `prompts/high-homogeneity-clustering.md` 交给 LLM，然后运行：

```powershell
.\source\.venv\Scripts\python.exe `
  .\scripts\comment_cleaning_pipeline.py build-cluster-review `
  --run-dir .\runs\cleaning-demo `
  --proposals .\path\to\llm-cluster-proposals.json
```

先阅读 `cluster-review.md`，再编辑 `cluster-review.json`：

- `merge_all`：全部成员折叠；`accepted_member_ids` 留空即可。
- `keep_separate`：全部保持独立；`accepted_member_ids` 留空。
- `merge_selected`：只折叠 `accepted_member_ids` 中至少两项，但不能填写全部成员。
- 可以修改 `representative_id`，但它必须属于最终合并成员。

## 4. 生成最终数据

```powershell
.\source\.venv\Scripts\python.exe `
  .\scripts\comment_cleaning_pipeline.py finalize `
  --run-dir .\runs\cleaning-demo
```

最终文件只包含：

```json
{
  "platform": "douyin",
  "comments": {
    "DY-0012": {
      "text": "真实评论原文",
      "support_count": 3
    }
  }
}
```

代表原文不会被改写，未折叠评论的 `support_count` 固定为 1。

## 5. 折叠后的 Codex 洞察看板链

Dify 可以继续完成相关性筛选和直接折叠；本地链也可以产出 `relevance-result.json`、`final-cleaned-comments.json` 与 `cluster-index.json`。两条路径从这里进入同一个确定性接口。

先生成统一输入：

```powershell
python scripts/build_comment_dashboard.py prepare `
  --target "本次研究主题" `
  --relevance E:\path\to\douyin-relevance.json `
  --folded E:\path\to\douyin-folded.json `
  --relevance E:\path\to\bilibili-relevance.json `
  --folded E:\path\to\bilibili-folded.json `
  --output-dir E:\path\to\dashboard-run
```

使用项目 Skill `.agents/skills/game-ops-insight-suite` 的 Dashboard 阶段：

1. Codex 基于 `analysis-input.json` 生成4—8个动态类别和 `other`，保存为 `classification-plan.json`，状态为 `draft`。
2. 用户修改并批准分类表后，Codex才生成完整的 `semantic-analysis.json`。
3. Python执行二次排除对账、多标签加权统计和最终文件输出。

```powershell
python scripts/build_comment_dashboard.py finalize `
  --analysis-input E:\path\to\dashboard-run\analysis-input.json `
  --classification-plan E:\path\to\dashboard-run\classification-plan.json `
  --semantic-analysis E:\path\to\dashboard-run\semantic-analysis.json `
  --output-dir E:\path\to\dashboard-run
```

正式终点是 `dashboard.json`，同时保留 `analysis-audit.json`。旧分类聚合节点不进入正式链路；旧文件可以继续作为历史参考，但不得与新看板统计混用。
