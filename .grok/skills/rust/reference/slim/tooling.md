# /cargo tools [target] — Rust 开发体验工具带

目的：深读仓库的 Rust 工具链、编辑器诊断、Cargo 子命令、watch/test/coverage/依赖治理工具、任务入口与 CI 安装方式，用**尽可能少的必装工具**缩短“克隆 → 能开发”和“编辑 → 得到可行动信号”的路径。裸调用只读体检；`--apply` 或同一请求明确“修/改/实现”时，才修改冻结范围内的 `rust-toolchain.toml`、`.cargo/config.toml`、工具配置、现有任务入口、CI 与开发文档。**不得静默安装、升级或删除用户全局二进制。**

先消费本轮唯一 [ProjectSnapshot](../../kernel/evidence.md)，读取 [BUILD](../../rules/build.md)、[DEP](../../rules/dep.md)、[TEST](../../rules/test.md)、[GATE](../../rules/gate.md)。构建指纹与性能归因归 [cargo](cargo.md)，最小测试证明归 [test](test.md)。工具版本、维护状态和安装源在应用前必须从官方文档或 release 复核，不能凭模型记忆写死。

## 第一性模型：工具只有产生独占信号才有价值

开发体验成本近似为：

`DX = 首次安装/升级 + 配置理解 + 编辑到诊断 + 聚焦验证 + 重复 Cargo 调度 + 失败定位 + 环境漂移`

每个候选工具必须填写六列，缺一就不引入：

| 字段 | 必须回答 |
|---|---|
| 信号 | 它发现什么，是 Cargo/rustc/现有工具发现不了的吗 |
| owner | 哪一个入口唯一负责这条信号 |
| 车道 | 编辑环、聚焦验证、提交前、CI、每夜或发布 |
| 成本 | 安装、编译、缓存、配置、升级和认知成本 |
| 可信边界 | 二进制从哪里来，版本/校验/权限如何处理 |
| 删除条件 | 何时证明它不再值得维护 |

禁止“Rust 项目都装这些”的购物清单。优先顺序固定为：**Cargo/rustup 内建能力 → 已有任务系统 → 一个有证据的外部工具 → 才考虑新增编排层**。

## 1. 仓库体检：先画真实开发路径

只读盘点以下事实，并记录文件位置与实际命令：

1. **工具链 owner**：`rust-toolchain.toml` / `rust-toolchain`、`rust-version`、rustup components/targets、devcontainer/Nix/mise/asdf/系统包管理器。
2. **Cargo 配置**：workspace 根 `.cargo/config.toml`、aliases、target/linker/runner/rustflags、环境变量；成员 crate 内的 `.cargo/config.toml` 不得被误认为从 workspace 根运行时会生效。
3. **编辑器环**：rust-analyzer 的 workspace/all-targets/features/check command/targetDir；VS Code、Zed、Neovim、RustRover 等共享配置与个人配置分开。
4. **终端环**：Makefile/justfile/Taskfile/xtask/npm scripts、Bacon、watchexec、遗留 cargo-watch；找保存一次触发几次 Cargo。
5. **测试工具**：`cargo test`、nextest、doctest、llvm-cov、快照/性质/并发工具；记录相同测试范围是否被双跑。
6. **依赖与供应链**：Cargo 内建 add/remove/info/tree/update、cargo-deny/audit/vet、cargo-machete/udeps、cargo-hack、升级工具。
7. **按需诊断**：cargo-expand、cargo-bloat、llvm-lines、flamegraph/samply、semver-checks；确认它们是否被塞进高频路径。
8. **安装 fan-out**：每个 CI job 是否都从源码 `cargo install`；版本是否漂移；本地文档、CI、容器镜像是否各钉一套版本。
9. **冷启动**：新开发者按 README 能否得到正确 toolchain、components、external tools 和一条首个绿色命令；失败是否给出可行动提示。

建议只读采集：

```text
rustup show active-toolchain
rustc -Vv
cargo -V
rustup component list --installed
rustup target list --installed
cargo install --list
cargo metadata --format-version 1 --no-deps
<已发现工具> --version
```

不要为体检先安装缺失工具；“命令不存在”本身就是证据。

## 2. 四条反馈车道：快环不背全量证明

### 编辑环：IDE 原生语义 + 一个聚焦 check owner

默认让 rust-analyzer 提供补全、跳转、原生诊断，并用 `cargo check` 做编译器诊断。审查它的 `workspace`、`allTargets`、features 与 target 是否和日常主产物一致；大型 workspace 不得默认每次保存都 `--workspace --all-targets --all-features`。

只有证据显示终端常驻视图、多 package job、错误历史或非编辑器开发能明显获益，才引入 Bacon。若 Bacon 已成为保存后 Cargo 诊断 owner，就收窄或关闭 rust-analyzer 的重复 full-workspace check；不能两边同时编完整图。rust-analyzer 与终端确实争锁时才给 RA 单独 target dir，承认它以磁盘换并发（BUILD-09）。

当前上游已归档、处于维护冻结的 cargo-watch **不作为新项目默认**。存量项目若稳定且迁移收益不足可以保留；需要新 watcher 时优先评估 Bacon，纯通用文件触发再评估 watchexec。不要为了“现代化”重写一个正常工作的 watcher。

### 聚焦验证环：改动 package/target 的最小命令

复用 `/cargo` 与 `/test` 生成的冻结指纹。开发入口只回答当前问题：

- 类型/借用/cfg：聚焦 `cargo check`
- 行为：聚焦 exact test 或 test target
- 运行时手测：目标 bin/example
- 宏展开：出现 derive/proc-macro 黑盒时临时 `cargo expand`

禁止把 fmt、clippy、build、test、doc、deny 全串到每次保存。

### 提交前环：一个可复现的 package/workspace verify 入口

沿用仓库已有 just/Make/Task/xtask 中的一个 owner，复用本地与 CI 的命令参数。简单单 Cargo 命令可用 `.cargo/config.toml` alias；多步骤、条件分支、跨平台逻辑使用**已有**任务系统，复杂度值得时才新增 xtask（GATE-01）。不要同时维护 `make check`、`just check`、`cargo xtask check` 三套同义入口。

### CI/每夜/发布环：昂贵工具按独占职责分层

feature powerset、coverage、Miri/loom、semver、全平台、release size 等进入低频车道；不能因为工具已安装就塞进每次 push。每个 job 的标题必须能说明它新增的证明，不能只是另一个“quality”。

## 3. 先榨干 Cargo/rustup 内建能力

新增外部工具前先检查这些能力是否已经足够：

| 需求 | 首选内建能力 | 不应立刻安装 |
|---|---|---|
| 加/删依赖 | `cargo add` / `cargo remove` | 仅为这两项安装 cargo-edit |
| 看 crate 与 features | `cargo info` | 浏览器脚本或自写 registry 查询 |
| 依赖路径/重复版本 | `cargo tree` / `cargo tree -d` / `-e features -i` | 新 depgraph 工具 |
| 机器读 workspace | `cargo metadata --format-version 1` | 手写 TOML 扫描器 |
| 编译器可修建议 | `cargo fix`（写入需授权） | 自写正则改源码 |
| 格式/lint/IDE | rustup 的 rustfmt、clippy、rust-analyzer components | 第三方替代品堆叠 |
| 文档浏览 | `cargo doc --no-deps --open` | 自建本地文档站 |
| 构建瓶颈 | `--timings` + `/cargo` | 先装缓存/链接器/火焰图全家桶 |

Cargo 已内建 `b/c/d/t/r/rm` 短 alias，不重复创建。项目 alias 只编码**稳定、语义清楚、单一 Cargo 调用**的范围；不得隐藏 `--all-features`、release、清缓存或网络副作用。多步骤 alias 不如复用现有任务 owner。

## 4. 外部工具选择矩阵：一个问题一个 owner

| 痛点/独占信号 | 候选 | 采用阈值 | 明确不做 |
|---|---|---|---|
| 常驻编译/测试反馈 | Bacon | rust-analyzer 单独不足，且能定义一个稳定聚焦 job | 与 RA 同时 full-workspace check；新引入 cargo-watch |
| 大量独立测试的执行调度 | cargo-nextest | 实测测试**执行**或隔离/报告是瓶颈；项目愿意维护配置 | 与 `cargo test` 双跑同一非-doctest 范围；用 retry 洗绿；声称加快测试编译 |
| feature 组合 | cargo-hack | library 有真实可选 feature/组合风险 | 每次保存 powerset；无 feature 也安装；无界笛卡尔积 |
| advisories/license/bans/sources | cargo-deny | 项目有供应链/许可门禁需求（DEP-06） | 同一 CI 再跑 cargo-audit 的相同 advisory 信号 |
| 更高供应链保证 | cargo-vet/crev | 明确高保证场景与评审资源 | 把它当零成本默认模板 |
| 未用依赖快速筛查 | cargo-machete | 需要 stable、快速、可解释的启发式 | 自动删除 finding；忽略 build.rs/codegen/宏造成的假阳性 |
| 未用依赖深查 | cargo-udeps | 已有 nightly 低频车道且启发式不够 | 为它改默认 toolchain；与 machete 在同一 PR 同时阻塞 |
| proc-macro/derive 黑盒 | cargo-expand | 具体宏诊断时按需调用 | 常驻 CI 或每次保存运行 |
| 覆盖率 | cargo-llvm-cov | 覆盖数据会驱动测试决策或外部合规 | 用百分比代替不变量；放进编辑环；把 nextest 覆盖当 doctest 覆盖 |
| 公共 API 兼容 | cargo-semver-checks | 可发布 library/public API 的发布或低频车道 | app/private crate 每 push 运行；不固定 baseline |
| release 二进制体积 | cargo-bloat（Wasm 另选工具） | 真实交付产物有体积预算 | 对 dev/check 产物下结论 |
| 泛型/单态化代码量 | cargo-llvm-lines | timings/size 已指向 monomorphization | 无证据的日常门禁 |
| 批量依赖升级 | cargo-edit 的 `cargo upgrade` 等 | 仓库明确要受控批量升级流程 | 仅为 add/remove/info 安装；无人值守升级 lock |

补充裁决：

- nextest 当前不替代 doctest；公开文档契约仍由 `cargo test --doc` 负责。
- cargo-hack 的 powerset 先用 include/exclude/group/depth 收敛；只覆盖有意义的组合。
- cargo-machete finding 必须用源码、build.rs、features 和生成代码复核后才可 `cargo remove`。
- coverage、semver、bloat 是“慢工具”，默认只消费 release/CI 的真实 target/profile/features，不另造一套指纹。
- `cross`、cargo-chef、cargo-dist 等分别归 xplat/ship；不要把所有名字都塞进 `/cargo tools`。

## 5. 安装与版本：避免为了装工具先编半个生态

1. **rustup components/targets**：团队需要的 `rustfmt`、`clippy`、`rust-src`、`rust-analyzer`、目标 std 或 `llvm-tools-preview`，由 `rust-toolchain.toml` 在项目层声明；只声明实际使用项。
2. **沿用已有环境 owner**：项目已有 Nix/devenv/mise/devcontainer/Brewfile/镜像时，在那里钉外部工具；不得再发明第二个 bootstrap 系统。
3. **预构建二进制优先但有信任门槛**：官方/维护者 release artifact、系统包或已审 CI action 能显著减少 `cargo install` 编译。使用 cargo-binstall 前必须展示最终下载源与 provenance；它可能采用第三方 artifact/fallback，不能把“更快”当自动授权。
4. **源码安装兜底**：使用 `cargo install --locked <tool>@<exact-version>`；CI 禁止裸 `cargo install <tool>` 跟随 latest。若工具发布物没有可用 lock，再明确记录例外。
5. **不要每个 job 重装**：预烘镜像、可信安装 action 或按 tool/version/host key 缓存；一次 workflow 只由一个 job/步骤拥有安装。
6. **不自动更新开发者机器**：仓库可提供缺失检测与精确安装命令，但 skill 不执行全局 install/uninstall/update；用户明确要求安装时再操作。
7. **一个版本 owner**：版本只在已有环境清单、CI 安装入口或镜像定义中的一个地方拥有；README 只引用 bootstrap 命令，不复制版本号。

## 6. 配置文件只在工具被采用后出现

| 文件 | 允许创建/修改的前提 |
|---|---|
| `rust-toolchain.toml` | 团队需要固定 channel/components/targets；不能用来假装钉外部 cargo 子命令 |
| `.cargo/config.toml` | workspace 共享且跨开发者成立的 alias/target/runner/cache 配置；个人路径、颜色、私有 token 不入库 |
| `bacon.toml` | Bacon 已被选择为唯一终端反馈 owner；job 与 `/cargo` 指纹一致 |
| `.config/nextest.toml` | nextest 已采用；retry 默认 0，timeout/partition/JUnit 有明确需求 |
| `deny.toml` | 供应链/许可策略已确认；从最小 policy 开始，不复制陌生模板的 allow 列表 |
| `Cargo.toml` tool metadata | 仅记录工具真实需要的 workspace/package 配置与有理由的 ignore |
| 编辑器 workspace settings | 团队共享的 Rust 语义配置；个人字体/UI/绝对路径不提交 |
| just/Make/Task/xtask | 复用已有 owner；没有复杂跨平台编排就不新增另一套 |

孤儿配置等于坏体验：删除工具后同步删除配置、CI 步骤和文档；配置存在但工具从未运行也算漂移。

## 7. 去重规则：工具多不等于信号多

必须选唯一 owner，或明确不同车道的不同职责：

- **保存后编译诊断**：rust-analyzer 或 Bacon 的 Cargo job，不能都跑完整 workspace。
- **普通非-doctest 测试**：cargo test 或 nextest，同一指纹只执行一次。
- **advisory**：cargo-deny 或 cargo-audit；若 deny 已覆盖 advisories，不再重复。
- **unused deps**：machete（快启发式）或 udeps（nightly 深查）；若两者并存，前者本地提示、后者每夜非阻塞，不能同层双阻塞。
- **任务入口**：一个现有 runner；IDE task、README、CI 都调用它或同一底层命令，不能复制逻辑。
- **版本**：一个环境/安装 owner；不在 README、workflow、Dockerfile 各写一遍 latest/版本号。
- **全量验证**：本地聚焦、pre-push、CI、每夜逐层新增信号，不重复上一层全部命令只为“更保险”。

## 8. `--apply` 的最小 Patch 顺序

1. 删除或合并重复 Cargo 调用、失效 alias、孤儿配置和重复工具步骤；覆盖不得静默变弱（GATE-02）。
2. 让 rust-analyzer/Bacon/本地 verify/CI 的 package、target、features、profile 使用同一语义指纹；不同车道的扩宽要显式。
3. 在**已有**任务 owner 中收敛为最多三个用户入口：聚焦开发、提交前验证、完整 CI；入口名沿用项目语言，不强制 `dev/check/ci`。
4. 只有缺少独占信号且收益证据充分时，引入一个外部工具；同时钉安装源/版本、最小配置、所属车道与删除条件。
5. 新工具先在一个 package/target 上验证，再接 CI；不能一步加入 workspace × all-targets × all-features。
6. 提供一条 fresh-clone bootstrap 路径和一条 doctor 输出；不得要求新人从五段 README 手工拼环境。
7. 任何“更快”结论回到 `/cargo` 或 `/test` 做同指纹前后测量；只改善可发现性/一致性时，明确不宣称性能提升。

写入不包含：静默执行 `cargo install`、改用户 `$CARGO_HOME`、改全局 editor 设置、清共享缓存、更新所有依赖、删除未复核的“unused dependency”。

## 9. 输出与完成条件

先输出：

| 反馈信号 | 当前 owner/命令 | 重复者 | 目标车道 | 决策 |
|---|---|---|---|---|
| 编译诊断 | … | … | 编辑环 | 保留/收窄/替换 |
| 测试 | … | … | 聚焦/CI | … |
| 依赖/供应链 | … | … | CI/每夜 | … |
| 工具安装 | … | … | bootstrap | … |

随后给：最小工具集（必需/按需/拒绝）、配置 Patch、精确安装命令、fresh-clone 路径、前后 DX 指标与未覆盖平台。至少记录：首次 bootstrap 步数/时长、保存触发的 Cargo 次数、聚焦命令墙钟、必装全局工具数、CI 重复安装次数。

完成必须满足：

- 新开发者有一个权威 bootstrap 入口，缺工具时错误可行动。
- 保存一次至多一个 Cargo 编译诊断 owner；没有隐藏的 full-workspace/all-targets/all-features。
- 本地与 CI 共享 package/target/features 语义，扩宽层级可解释。
- 必需外部工具在 CI/环境中精确钉版本和安装源；无静默 latest。
- 同一测试/advisory/unused-deps 信号不在同层双跑；retry 不掩盖 flake。
- 没有为“看起来专业”新增孤儿配置、第二任务系统或未使用工具。
- 没有全局安装、清缓存或依赖删除等越界副作用。
