# Bun 工程纪律对 rust-skills 的可迁移启发

范围：只读 Bun 官方仓库 [`01c4e2f`](https://github.com/oven-sh/bun/commit/01c4e2fd6d94adf2e9157d1e6329c328eb37dfae) 与 Bun 官方文档；不把 Bun 的产品架构当作 Rust 通用规范。结论只保留本轮已经落地的五类改进。

## 结论

| 本轮改进 | Bun 一手证据 | 可迁移到 rust-skills 的纪律 | Bun 特有、不要照搬 |
|---|---|---|---|
| 修 bug 先找同类路径与共同根因 | Bun 要求 grep 每个同类位置：平行分支、sync/async、快/慢路径、POSIX/Windows、以及变更 helper 的所有调用方；共同 guard 优先放进共享 helper。[REVIEW.md：bug class 与 single source of truth](https://github.com/oven-sh/bun/blob/01c4e2fd6d94adf2e9157d1e6329c328eb37dfae/REVIEW.md#L31-L40) | `D-1`、`craft`、`review` 现在明确要求枚举调用方、平行入口、`#[cfg]` 分支、生成输入；修拥有不变量的一层，排除项逐项解释。 | Bun 的 JSC、Node/Web 兼容层、各 OS backend 是它自己的同类路径；Rust 项目只查实际存在的分支。 |
| 回归测试必须证明旧行为见红 | Bun 不接受只会通过的测试：测试要因正确原因失败，删除修复的关键子句应让测试失败，并断言最强、可失败的不变量。[REVIEW.md：tests reviewers reject](https://github.com/oven-sh/bun/blob/01c4e2fd6d94adf2e9157d1e6329c328eb37dfae/REVIEW.md#L7-L17) 行为变更优先追加到现有覆盖文件，而不是另建重复 setup。[CLAUDE.md：test organization](https://github.com/oven-sh/bun/blob/01c4e2fd6d94adf2e9157d1e6329c328eb37dfae/CLAUDE.md#L47-L60) | `TEST-01/08` 与场景 58 现在要求“现有覆盖文件 + 规格期望 + 旧行为/隔离副本/受控回滚见红”；无法安全证明时必须列缺口。 | `USE_SYSTEM_BUN=1` 是 Bun 用已发布 Bun 作负对照的专用办法；Rust 项目应按自身条件选旧 commit、隔离副本或受控回滚。 |
| 验证必须运行当前源码产物 | Bun 明确禁止直接用 PATH 中的 `bun test` 验证本地改动，统一走 build-then-exec 的 `bun bd test`；纯 `.d.ts` 改动才有显式例外。[CLAUDE.md：build and run](https://github.com/oven-sh/bun/blob/01c4e2fd6d94adf2e9157d1e6329c328eb37dfae/CLAUDE.md#L3-L37) | `craft` 与场景 58 现在要求确认项目包装入口命中当前 checkout 产物，不能把旧全局二进制的绿色当作本次验证。 | 不复制 `bun bd` 名称或 Bun 的 WebKit 构建链；复用目标仓现有的 `cargo xtask`、脚本或 Cargo 入口。 |
| 平台分支必须由对应 target 证明 | Bun 要求平台修复审计 sibling backend；平台代码要在实际 CI 平台测试，Rust 的 `#[cfg]` 代码还要跑跨 target 检查，因为宿主构建不会类型检查未命中分支。[landing-prs.md：cross-platform](https://github.com/oven-sh/bun/blob/01c4e2fd6d94adf2e9157d1e6329c328eb37dfae/.claude/docs/landing-prs.md#L37-L43) [CLAUDE.md：cross-target check](https://github.com/oven-sh/bun/blob/01c4e2fd6d94adf2e9157d1e6329c328eb37dfae/CLAUDE.md#L191-L208) | `XP-03`、`xplat`、`review` 与场景 58 现在把“声明支持平台 → 对应 target 编译/测试”设为证据；缺工具链时明确写“该分支未编译”，不拿宿主绿色代替。 | Bun 的 Windows/macOS/Linux 全矩阵来自其产品支持面；rust-skills 只覆盖目标项目声明发布的平台，Linux-only 服务不强加三端矩阵。 |
| 性能主张绑定真实 profile 与前后基线 | Bun 要求使用仓内 bench 给出 before/after，覆盖输入类别；反对凭直觉搬优化、调高优化级别或用平均值掩盖退化。[landing-prs.md：performance](https://github.com/oven-sh/bun/blob/01c4e2fd6d94adf2e9157d1e6329c328eb37dfae/.claude/docs/landing-prs.md#L29-L35) | `bench` 现在要求同机同负载、真实交付 profile、至少三轮区间；debug 结果只定位，不外推发布性能，无 before 则停止因果结论。 | Bun 还要求对比 Node/上一版 Bun，这是兼容运行时的产品基线；普通 Rust 项目只需项目定义的竞争基线。 |

## 裁决

值得迁移的是“证据闭环”，不是 Bun 的规模：根因面完整、测试先证明能失败、验证命中当前产物、平台声明由对应 target 背书、性能只认可复核基线。当前 skill 已有同一事实源、渐进加载和一致性脚本，无需增加命令、依赖或新的测试框架。
