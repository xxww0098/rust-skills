# kernel/finding — 如何证明问题 + 如何向用户说

禁止只输出「某处违反 WS-07，建议解耦」。每条 Finding 必须能回答因果链：目标 → 约束 → 范围 → 快照 → 不变量所有权 → 可观察问题 → 拥有该问题的层 → 最小修复 → 验证。

## Finding（字段与 schemas/finding.schema.json 对齐）

| 字段 | 必须回答 |
|---|---|
| `id` | 本轮稳定短 id |
| `rule_id` | 已读取的规则号；普通实现可空，但评审/改造不可空 |
| `severity` | M / S / Y |
| `confidence` | high / medium / low（low 必须列未验证假设） |
| `scope` | 主目标路径，不是邻接 |
| `location` | 文件:行 或符号 |
| `premise` | 规则为什么适用于这里 |
| `evidence` | 代码或快照图上的证据 |
| `counterevidence` | 可能不适用的理由；没有就写「未见」 |
| `violated_invariant` | 被破坏的不变量（谁拥有它） |
| `observable_effect` | 当前或可验证后果，不是假想未来 |
| `owner_layer` | 修复应落在哪一层 |
| `minimal_fix` | 最小安全修复；禁止扩大冻结范围 |
| `blast_radius` | 一次改动会传播到哪些 crate/调用方 |
| `compatibility_risk` | pub API / MSRV / 依赖是否被扩大 |
| `verification` | 已跑的最小命令，或「未跑：原因」 |

counterevidence 用来挡住教条：单实现 trait 可能是插件边界；`Box<dyn>` 可能真要运行时异构；`serde_json::Value` 可能是透传；旧 edition 可能是发布库 MSRV；大文件可能是生成代码。

## 输出骨架（所有命令）

1. **一句话结论**：用户语言，不带规则号。
2. **范围行**：`项目根 · 范围 · N 文件 · 只读|写入`（来自 snapshot.scope）。
3. **正文**：Finding 表或命令表；规则号只出现在这里。
4. **验证**：已运行检查；没跑就写原因。
5. **置信度与缺口**。
6. **下一步**：0–2 条可复制完整命令。
7. **写授权收尾**：未改文件须注明；等待落地的给出「回复『改』或 `--apply`」。

评审类表头：`位置 | 规则 | 级别 | 前提 | 证据 | 反证 | 所有权层 | 最小修复`。

## 对抗审查

检查器给出的是**信号**，不是 Finding。`check_patch` 的 `signals`（`.clone()`、`&String`、下标循环）必须先被自己反驳，写得出反证才能降级或删除；写不出反证也不能把信号直接抄进结论表。

不合格 Finding（不得当结论）：

- `counterevidence` 空、缺省或复制 `evidence`
- `verification` 写成「已检查 / cargo test 过」但没有命令指纹
- 唯一证据是扫描命中，没有指出所有权层和不变量

对抗顺序：先试图用反证推翻本条，再决定 M/S/Y。推翻不了才保留。
