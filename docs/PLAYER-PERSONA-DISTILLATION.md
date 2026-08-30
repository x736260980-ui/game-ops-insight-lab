# Player Persona Distillation（实验性）

## 目的

Player Persona 层用于验证：一组经过筛选、可追溯且有权使用的玩家评论，能否蒸馏出稳定、彼此不同、接近社区表达的虚拟玩家 Skill。

它不用于复制真实个人，也不用于推断玩家年龄、性别、职业、收入、现实人格或总体人口比例。

## 上游方法

这一层参考并可选使用 [titanwings/distilly](https://github.com/titanwings/distilly) 的蒸馏结构：

```text
materials → intake → analyzer → merger → persona builder → skill writer
```

Distilly 不随本仓库分发。请从官方仓库单独安装，并确认其当前文档和许可证。

## 数据要求

- 只使用用户拥有合法处理权限的材料。
- Anchor：直接、稳定地体现核心模式的证据。
- Support：补充或重复支持该模式的证据。
- Context：用于限制过度概括、保留反例和条件。
- `support_count` 只表示同质表达折叠量，不等于独立玩家人数，也不与蒸馏权重相乘。
- 不提交原始私人材料、账号身份、Cookie、Token 或浏览器状态。

## 推荐输出

```text
SKILL.md
evidence_map.json
distillation_report.md
meta.json
```

- `SKILL.md`：可调用的虚拟玩家表达与判断规则。
- `evidence_map.json`：画像结论到原始证据编号的映射。
- `distillation_report.md`：批次、冲突、边界审计和局限。
- `meta.json`：版本、材料数量、生成时间和输入摘要。

## 与主流程的关系

Persona 是 Dashboard 最终结果之后的可选实验层。盲测时只输入事件和已确认事实，不提前读取当前事件真实评论；预测完成后才从 SQLite 读取真实评论进行比较。Persona 结果不能计入真实评论统计。
