# /rust-skills:rust doctor — 库与项目体检

目的：只读检查本技能库自身、以及它与项目之间的漂移。**不做修复、设计或代码工作**。

## 检查项

**库自身**

1. 仅当能从技能根或仓库根解析到含 `scripts/check-consistency.sh` 的 rust-skills 源仓时，才运行库检；否则输出 `SKILL_REPO_UNAVAILABLE` 并只做项目侧检查。脚本核对：命令↔reference、命令表生成（gen-command-tables.py）、全局/局部编号存在性与局部连续性、跨 owner 定义、SKILL 写入边界↔reference 分类、压力场景结构覆盖、provider sync、**fixture eval**（`scripts/eval-fixtures.py`，每个命令 ≥1 个磁盘 fixture）、**trigger eval**（`scripts/eval-triggers.py`，正/负触发短语）、**version floor**（`scripts/check-floor.py`）。不能把 AS/AX/CC/CK/CL/PR/SE/SH/SO/ST/SX/TA/TR/XP 误报为全局坏引用。优先本机 `rg`；无 `rg` 时允许 grep 垫片，但不得在 `LC_ALL=C` 下假红命令覆盖。
2. 命令表 ↔ reference 文件一一对应：表里有行无文件、有文件无行都报；命令表由 `scripts/command-metadata.json` 生成，生成脚本核对无漂移。
3. 压力场景结构覆盖：每个命令 ≥1 个独立场景标题，且含提问/坏答案/验收。这只证明文案存在。有磁盘 fixture 的场景由 `eval-fixtures.py` 验证反模式仍在、playbook 仍点名规则（每个命令 ≥1 个 `tests/fixtures/scene-*/`）；LLM 行为回归仍要外部 runner 或人工新会话，不得把“场景文件存在”或“机械契约绿”写成“行为已验证”。
4. 本技能的规范源是 `rules/<domain>.md`（全量审计才读 `rules/rules-full.md`）+ `reference/`；若维护者另有外部规范副本，只在明确提供路径时核对版本/编号漂移（META-03）。

**项目侧（有 RUST.md 时）**

5. RUST.md 时效：crate 图与当前 `cargo metadata` 一致吗；「最近评审」——无快照 → STALE（建议首次 `/rust-skills:rust review`）；有快照且超过 30 天 → STALE（建议复跑）。
6. **规范版本**：RUST.md 记录的 rust-skills 版本 vs 当前技能 `version`；不一致 → **DRIFT**（建议 `/rust-skills:rust document`）。单独一行，勿埋进工具链项。
7. 棘轮基线：仅当存在明确棘轮文件（如 clippy JSON 基线、`ratchet.toml`）时对比当前 clippy 实测——更低 → 提示收紧；更高 → 红色警报。无此类文件 → **N-A**，禁止为对比安装工具或强跑 clippy。`[workspace.lints]` 不是棘轮文件。
8. 工具链漂移：rust-toolchain / MSRV / edition 与 RUST.md 记录一致吗。**edition < 2024 → DRIFT**（`init`/`modernize`），不得把 2018/2021 标成 OK。edition 2024 + resolver 2 → **OK**（记录，不因数字 2 标 DRIFT）。无 `rust-version` 但有 `rust-toolchain.toml` 且 channel ≥ 1.85 → OK。

输出须回显已排除的旁路 crate 路径（与 SKILL 默认范围一致）。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

```
| 项 | 状态 | 建议动作 |
```

三态：OK / DRIFT（给一条命令或一个 Edit 就能修）/ STALE（需要跑某命令刷新，如 `/rust-skills:rust document`）。doctor 默认只读；不得在同次调用中修复 DRIFT。结尾一句总评：库当前健康度与最该做的一件事。
