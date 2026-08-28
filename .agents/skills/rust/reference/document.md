# /rust-skills:rust document — 投影项目画像

目的：把当前 Rust 项目事实投影为 RUST.md；直接调用时只写 RUST.md，供 `init` 在修改基线后复用同一流程。老项目通常先 document 再决定 init 改多少，但显式 init 不以此为前置条件。

## 一次取证

1. **结构**：读取根/成员 Cargo.toml 与一次 lock-safe `cargo metadata`（失败则按 SKILL 降级），记录 workspace 形态、lints/profile/features、crate 图、最长链与出度 0 素材（WS-08/12）。
2. **域与模块**：判断 src 是业务域还是技术层（WS-06），核对 tests 布局（TEST-02/03），抽查 mod 可达图与文件清单找孤儿 `.rs`。
3. **风险**：只记录不修改 unsafe/extern、生产 unwrap、println、无界 channel、通配 opt-level 与 Cargo.lock 策略/状态；每项给计数和位置样例，只有可行动发现才生成稳定 debt key，合规/N-A 项只进画像证据。先读 artifact、发布方式与项目约定再判断 lock：缺失本身不是债务，只有项目已选择跟踪或可复现交付确实需要时才报 DEP-07。
4. **Facets**：逐 crate 推断 `artifact=lib|service|cli|desktop` 与 `maturity=prototype|production`。证据充分则投影；歧义项标 `待确认` 并说明影响，不用 workspace 级猜测覆盖所有成员。

完成取证后一次性生成画像；不要为每个节重复扫描。由 init 复用时，可以沿用未受修改影响的证据，但必须刷新受改动的 manifest、依赖图、基线和风险计数。

## 格式与合并

按 SKILL 的 RUST.md 投影契约写入：基于写前回读的最新文件替换四个投影节；风险扫描只 upsert/复核自己的 debt key；保留其他账本键和未识别 managed 节。没有再次 review 就不得改写历史评审结论。

```markdown
# RUST.md — 项目工程画像（/rust-skills:rust 系列命令的状态文件）
<!-- rust-skills:managed:start schema=1 -->
## Facets
默认: artifact=service, maturity=production
覆盖: crates/sdk=artifact:lib, crates/app=artifact:desktop
待确认: <crate + 不确定项 + 影响；没有则省略>
## 基线
edition <项目值> · MSRV <项目值> · resolver <项目值> · 规范版本 v<当前 SKILL frontmatter version>（143 条分级规则）
## Crate 图
core-domain ← storage ← server（叶子在左；出度 0 仅作候选素材）
## 域划分
billing/ user/ …（当前证据与待确认项）
## 债务清单
- [ ] debt:ERR-03:crates/storage · 存量 unwrap 37 处（证据/棘轮）
## 最近评审
- review:2026-08-16:scope-hash · M 违规 0，S 违规 3（历史快照）
<!-- 其他 managed 账本节按原文保留 -->
<!-- rust-skills:managed:end -->

<!-- rust-skills:human:start -->
## 人工上下文
领域术语、取舍与无法从代码推导的约束。
<!-- rust-skills:human:end -->
```

## 输出与完成

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

输出 managed diff、保留的账本键/未知节计数、人工作用域摘要，以及最大结构风险、最值得先做的命令和预估 init 改动面。直接调用不得修改源码、manifest、CI 或门禁；由 init 复用时，画像只描述磁盘上的 post-state，不记录计划但未落地的值。

完成条件：步骤 1–4 要求的事实均进入对应投影、document 自有账本，或明确标 `待确认`；除 RUST.md 外目标项目无写入，其他命令的账本和人工内容无丢失；相同项目状态再次 document 不产生 diff。
