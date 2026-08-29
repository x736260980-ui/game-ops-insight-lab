# 工作流与产物

## 阶段

1. 明确研究问题、平台、关键词、固定内容和样本边界。
2. 采集公开一级评论，保存原始结果但不公开登录态和用户身份。
3. 删除空文本与确定性噪声，建立平台内稳定编号。
4. 按研究主题做相关性判断，再保守折叠高度同质表达。
5. 生成统一 `analysis-input.json`，提出动态分类并由用户确认。
6. 生成 `semantic-analysis.json`、`classification-plan.json`、`analysis-audit.json` 和 `dashboard.json`。
7. 默认执行单 Agent 分析；用户明确要求时执行双 Agent。
8. Dashboard 动态读取结构化结果，支持从结论回溯到评论证据。

## 恢复与重跑

- 每个事件使用独立运行目录。
- 已存在且通过校验的阶段默认复用；只有用户明确要求重跑才归档旧产物。
- 不覆盖原始采集文件。
- 任一必要阶段失败时停止，不生成伪完整报告。

## 双 Agent 稳定输出

```text
dual-agent/
├─ 01-codex-initial.md
├─ 02-claude-initial.md
├─ 03-transcript.md
├─ 04-disputes.json
├─ 05-final-analysis.md
└─ 05-final-summary.json
```

`.runtime/`、Session、CLI 原始日志和历史失败稿只属于本地运行状态，不进入公开案例。

