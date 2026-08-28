# /cargo [tools|target] — Cargo 最短反馈回路

目的：深读用户仓库的 workspace、package/target、feature、profile、依赖、build.rs、缓存、Rust 配套工具与 CI 命令，把“编辑 → 足够可信的编译/链接信号”压到最短；不是无脑把机器跑满，也不是把 release build 变成日常默认。裸调用只读体检；只有 `--apply` 或同一请求明确“修/改/实现”才写冻结范围内的 Cargo.toml、`.cargo/config.toml`、toolchain、工具配置、xtask/CI 文件。

先消费本轮唯一 [ProjectSnapshot](../../kernel/evidence.md)，并读取 [BUILD](../../rules/build.md)、[DEP](../../rules/dep.md)；总体前后对比仍归 [slim](../slim.md)。测试编译/执行交给 [test](test.md)，不要在两个 playbook 重跑同一图。

## 开发体验分支：`/cargo tools [target]`

用户提到“开发体验、配套设施、Cargo 工具、watch、nextest、rust-analyzer、工具安装/版本、IDE 与 CI 一致性”时，先加载 [Rust 开发体验工具带](tooling.md)。它负责选工具、去重复 Cargo 调度、统一 bootstrap 与配置 owner；本文件继续负责构建指纹和性能归因。

- 工具盘点、孤儿配置清理、版本/安装源归一、命令可发现性改善，可以在不宣称性能提升的前提下按仓库证据落地。
- 任何“更快”“节省多少编译/测试时间”的结论仍必须在相同构建指纹下给出前后基线。
- `/cargo tools` 不是 `cargo install` 代理；不得静默改用户全局工具链或 `$CARGO_HOME`。

## 第一性模型：优化“足够的证明”，不是优化命令名字

一次反馈的墙钟近似为：

`T = resolve/fetch + compile + codegen/link + build-script/proc-macro + execute + duplicated work`

优先消掉 `duplicated work`，再优化关键路径。最快的命令必须回答当前问题：

- 只问类型、借用、trait、cfg 是否成立 → `cargo check`
- 需要链接器、链接脚本、native lib、最终二进制或 codegen 错误 → `cargo build`
- 需要证明行为 → 直接进入 `/test`，不要先无条件 check、再 build、再 test 三遍
- 需要发布产物 → 用真实 release/ship 路径；不得拿 dev check 的速度冒充发布速度
- 需要改善工具使用体验 → `/cargo tools` 先判定独占信号；不因工具流行就安装

同一轮先冻结**命令指纹**：toolchain + manifest/workspace + package 集 + target 集 + target triple + profile + features + Cargo config/RUSTFLAGS + target dir。指纹不同的两次运行不是可靠前后对比，也通常不能完整复用缓存。

## 1. 深读仓库：先找“为什么编了这么多”

只读盘点，并把证据落到文件/target：

1. workspace：members / exclude / `default-members` / resolver；裸 cargo 命令实际会选谁。
2. package targets：lib/bin/example/test/bench、crate-type、`required-features`、build.rs。
3. features：default feature、可选依赖、互斥/平台 feature、CI feature 矩阵；找“本次功能没用却被默认打开”的边。
4. 依赖图：normal/build/dev 三类、重复版本、重 proc-macro/native/codegen；只看当前目标可达图，不把全 lockfile 都算热路径。
5. 构建配置：profiles/package override/build-override、`.cargo/config*`、toolchain、target triple、linker、rustflags、incremental/debug。
6. 缓存与锁：终端、IDE/rust-analyzer、CI 是否共用或分裂 target dir；是否并行启动多个 Cargo 抢 package-cache/target 锁。
7. 命令 fan-out：Makefile/justfile/xtask/npm scripts/CI 是否连续执行相同 package+target+features 的 check/build/test/clippy，或多个 job 重复完全相同指纹。
8. build.rs：是否没有精确 `rerun-if-changed` / `rerun-if-env-changed`，导致包内任意文件变化都重跑；生成物是否只写 OUT_DIR。
9. DX 工具：rust-toolchain、rust-analyzer、Bacon/watcher、nextest、cargo-hack/deny/coverage 等是否各自拥有独占信号，还是只重复 Cargo；细化走 `tooling.md`。

输出一张“触发 → 编译单元 → 原因”表。没有代码/manifest 证据，不猜缓存失效原因。

## 2. 先给最窄命令，再逐级扩宽

根据改动包和真实目标生成命令，不机械照抄下列占位符：

```bash
# 类型级反馈：只选被改 package 与真实 target
cargo check -p <pkg> --lib
cargo check -p <pkg> --bin <bin> --features '<needed>'

# 只有确实需要链接时
cargo build -p <pkg> --bin <bin> --features '<needed>'

# 测试代码只做编译门禁；要运行时直接交给 /test
cargo check -p <pkg> --test <integration-target> --profile test
```

扩宽阶梯固定为：**target → package → 受影响的反向依赖/契约 → workspace → feature/platform 矩阵**。前一级已足以回答问题就停止。以下只放 CI、发布或明确全量请求，不做本地默认：

- `--workspace`
- `--all-targets`
- `--all-features`
- 所有 target triple
- release + dev + test 的笛卡尔积

`workspace.default-members` 只在裸命令长期误选大量非主产物且团队语义明确时修改；它不是隐藏坏 workspace 的扫把。

## 3. 测量：冷、热、重编译原因分开

- **热增量**：在用户当前 target dir 对“真实慢命令”加 `--timings`，记录总时长、units、关键路径、并发空洞与 custom-build。
- **冷构建**：用独立临时 `CARGO_TARGET_DIR` 跑同一指纹；不得 `cargo clean`、`cargo sweep` 或删除共享 target（BUILD-07）。
- **图证据**：`cargo tree -d` 找重复版本；`cargo tree -e features -i <crate>` 反查是谁打开重 feature。
- **重编译原因**：先用 `-vv`、dep-info、build.rs 输出和文件变更证据；只有项目已选 nightly `-Zbuild-analysis` 时才用 `cargo report sessions/rebuilds/timings`，并标实验能力，不能要求 stable 用户安装 nightly。
- **锁等待**：区分“CPU 忙”“依赖未解锁”“另一个 Cargo/IDE 持锁”。不要用提高 `-j` 掩盖锁与串行关键路径。
- **保存 fan-out**：开发体验诉求额外记录保存一次启动的 Cargo 进程数与指纹；RA/Bacon/watcher 重复 full-workspace 属于可先删除的纯浪费。

长构建未获授权时，给可粘贴命令与预期采集字段，明确“未实测”；不得据此改 profile 或承诺百分比。

## 4. 最小改造顺序

一次只落 1 类，改后复测同一指纹：

1. **命令去重/缩域**：脚本与 CI 选 package/target/features；删掉同一门禁链里没有新增信号的重复 build。若 `cargo test` 已完成目标编译，不再先跑相同图的 `cargo build`。
2. **开发工具去重**：按 `tooling.md` 选保存诊断、测试、advisory、unused-deps 与任务入口的唯一 owner；先删重复调用，再讨论换工具。
3. **稳定缓存指纹**：团队命令统一 toolchain/target/profile/features/target-dir；不要在同一主机无理由混用隐式 host 与显式 `--target <host>`。RA 只有确证抢锁时才单独 target dir（BUILD-09），并承认它以缓存分裂换交互稳定。
4. **依赖与 feature**：关未用 default-features、移除不可达依赖、收敛重复版本；每个变化都要有行为/API/平台验证，不能为“少一个 crate”破坏用户能力。
5. **build.rs / proc-macro / native**：收窄 rerun 边界、避免扫描大目录、缓存稳定生成物；重 build-dependency 与 normal dependency 是否重复编译要按 host/target/profile 看证据。
6. **profile / debuginfo / linker**：先 `line-tables-only` 候选，再平台实测 linker；package override 与 build-override 分开试。禁止 `[profile.dev.package."*"] opt-level=3`。
7. **结构边界**：只有 timings 证明大 crate 位于频繁重编译关键路径，且拆分能形成稳定依赖方向时才拆；不为并行度制造几十个无所有权 crate。
8. **共享缓存**：sccache/远端缓存是跨 workspace/CI 的 MAY 项；先证明本地关键路径已缩域且命中率、网络与可信边界合算，不能作为第一剂药。

## 5. 明确拒绝的“快”与“专业工具箱”

- 清缓存后宣称更快，或用不同 features/profile/target 做前后对比。
- 把 `--workspace --all-targets --all-features` 设成本地默认。
- 同时启动多条 Cargo 命令争同一个 target/package cache。
- 只调 `jobs`，不看 critical path、内存和 build script jobserver。
- 照抄 mold/lld/sccache/rustflags，不在目标平台实测。
- 为速度关闭必要测试、改变 release 语义、把测试 helper 暴露进生产 API。
- 未确认项目 MSRV/CI 就写 nightly-only 配置。
- 为了“Rust 全家桶”同时引入 watcher、nextest、hack、deny、coverage、udeps、semver、bloat，却没有独占信号与车道。
- 静默 `cargo install`/更新用户全局工具，或在 CI 每个 job 从源码重装 latest。

## 输出与完成条件

先给：

| 信号 | 最小命令指纹/owner | 避免编译或工具成本 | 何时扩宽 |
|---|---|---|---|
| 类型/借用 | package + target + needed features | 其他 members/targets/link | 公共契约或 cfg 边界变化 |
| 链接/产物 | package + final target | examples/tests/benches | 发布矩阵 |
| 行为 | 转 `/test` | 重复 check/build | 测试证明不足 |
| 开发工具/DX | 转 `/cargo tools` | 重复 watcher/runner/install/config | 独占信号与收益证据成立 |

随后给冷/热基线、Top 1–3 根因、最小 Patch、同指纹复测和未覆盖矩阵。完成必须满足：没有清共享缓存；没有重复运行同一证明；性能结论有前后数据；保存环没有重复 full-workspace Cargo owner；工具选择有独占信号、版本/安装源和所属车道；写入只触达冻结文件；无收益改动已回滚。
