# 评论相关性与高同质折叠

本目录只保留当前正式清洗协议。主线为：

```text
base-cleaned.json
        ↓
相关性二分类（保留 / 排除）
        ↓
relevance.json
        ↓
高同质评论直接折叠
        ↓
folded.json
```

## 1. 相关性二分类

使用项目 Skill：

```text
.agents/skills/judge-game-comment-relevance/SKILL.md
```

输入是明确的研究主题和各平台 `*-base-cleaned.json`。模型逐条判断评论能否回答本次研究问题：

- 能建立真实且可说明的关联：保留；
- 必须猜测缺失对象、反讽方向或不存在的因果关系才能纳入：排除。

该阶段没有相关性分数、第三种标签或逐条人工复核。边界评论必须由模型按照 Skill 规则完成二分类，不能输出 `review`、`pending` 或置信度区间。

正式 `*-relevance.json`：

- `comments` 只包含保留评论的 `record_id` 和未经改写的 `text`；
- 不包含 `decision`、`relevance_score` 或逐条理由；
- `stats` 记录相关性输入数、排除数和最终保留数；
- 保留原编号和相对顺序。

完整输入输出外壳见：

```text
.agents/skills/judge-game-comment-relevance/references/io-reference.md
```

## 2. 高同质评论直接折叠

把各平台 `*-relevance.json` 与以下提示词交给模型：

```text
prompts/fold-similar-comments.md
```

模型直接输出 `*-folded.json`。只有对象、具体方面、立场、核心判断和主要理由均一致的评论才可折叠；不确定时保持独立。

该阶段也没有逐组人工审核文件。输出必须保留代表评论原文、`support_count` 和 `merged_record_ids`，并满足数量守恒和成员唯一性。

修正示例见：

```text
prompts/fold-similar-comments-example.md
```

## 3. 与后续分类的边界

相关性清洗完成后不再逐条等待人工判断。后续动态分类会先生成 `classification-plan.json`；用户确认的是整套类别名称、定义和边界，而不是重新审核每条评论是否相关。

分类表批准后，模型才能生成全量 `semantic-analysis.json` 和 Dashboard。
