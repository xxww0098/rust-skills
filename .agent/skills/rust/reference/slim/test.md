# /test [target] — 最小充分测试

目的：深读用户仓库的改动面、测试目标、已有断言与 CI 运行图，用**最小且不重复的证明集**覆盖本次行为；同一不变量只保留一个最强、最便宜、最稳定的 owner。裸调用只读体检；只有 `--apply` 或同一请求明确“修/改/实现”才改冻结范围内的测试、manifest、nextest/xtask/CI 配置。

先消费本轮唯一 ProjectSnapshot，读取 [TEST](../../rules/test.md) 与 [测试设计](../testing.md)。本文件只负责“选哪些、编几次、跑几次、哪些合并”；并发/时间/flake/性质测试的具体形状仍由 testing.md 决定。Cargo 指纹与构建根因交给 [cargo](cargo.md)。

## 第一性模型：测试是证明义务，不是文件数量

对每个候选测试先填：

```text
不变量：<一句话规格>
会因何失败：<旧缺陷/边界/交错>
owner：<现有 test target + 完整测试名，或无>
本次改动为何可达：<生产符号/公共契约/feature/build.rs 证据>
```

填不出就不运行、不新增。测试总成本近似为：

`T_test = 测试目标编译/链接 + fixture/setup + 执行 + 重复证明 + flake 重跑`

优先删 `重复证明`。相同 toolchain/target/profile/features/test-target/env 的同一套测试，在同一验证链只运行一次；“再绿一次”不增加规格覆盖。失败后只重跑为定位/确定性复现，不能用 retry 把红洗绿。

## 1. 深读仓库：建“不变量 → owner”索引

围绕当前 diff/target 搜索，而不是先 `cargo test --workspace`：

1. 改动生产面：package、模块/符号、public API、序列化/协议、数据库/文件格式、feature/cfg、build.rs/proc-macro、unsafe/FFI、并发与时间边界。
2. 测试目标：模块内 `#[cfg(test)]`、同模块 `tests.rs`、每个 `tests/*.rs` 集成目标、doctest、example、snapshot/property/model/loom/Miri、外部服务与 ignored 测试。
3. 现有 owner：用断言和 fixture 判断测的**规格**，不能靠测试函数名相似度。记录输入域、观察点、隔离要求与失败模式。
4. 重复候选：
   - 同一输入/边界与同一最强断言散落在 unit/integration/doctest
   - 多个 examples 逐条重复一个 property
   - snapshot 已锁完整结构，又有逐字段镜像断言
   - 每个 integration `.rs` 都重复启动同一昂贵服务/链接同一大图
   - 多个 CI job 用完全相同 package/target/features/profile/runner 跑同一套
5. 缺口：新行为没有 owner；现有测试只复述实现；测试文件未被 mod 图到达；静默 skip；真实 sleep/全局 env/cwd/固定端口导致 flake。

输出索引：

| 不变量 | 当前 owner | 本次可达证据 | 重复/缺口 | 决策 |
|---|---|---|---|---|
| … | `target::module::test` | `src/x.rs:<symbol>` | 被 property 包含 | 合并/保留/新增 |

## 2. 先认清 Cargo 实际会做什么

- 裸 `cargo test` 不只跑“当前几个单测”：会按选中 package 构建 lib、相关 bin、examples、unit/integration 与 lib doctest。
- `--tests` / `--all-targets` 可能让 lib 以不同角色构建不止一次；`--all-targets` 还包含 benches/examples。只有这些目标确实属于证明时才选。
- 每个 integration test target 是独立测试可执行文件；大量小 `tests/*.rs` 会重复链接。只有共享 setup/链接成本明显且隔离语义允许时才合并，不能造一个巨型串行 tests.rs。
- 名称 filter 默认是子串。先 `-- --list`（或项目已有 nextest 的 `cargo nextest list`）拿完整名，再用 `--exact`，避免误跑同名家族。
- `cargo test --no-run` 只在“本阶段只验证能编译”或 CI 要把编译产物交给后续执行器时使用；若下一步立刻运行同一范围，直接 run，别为仪式多一次 Cargo 调度。
- 项目已采用 nextest 才沿用；`cargo nextest run` 与 `cargo test` 不得对同一非-doctest 范围双跑。nextest 目前不运行 doctest，需要的公开文档示例单独 `cargo test -p <pkg> --doc`。retry 默认保持 0。

## 3. 最小执行阶梯

命令必须替换为仓库真实 package/target/features；每一级通过且已足够证明就停止：

### G0 — 编译测试代码，不执行

只在本轮确实需要“测试代码可编译”而暂不运行时：

```bash
cargo check -p <pkg> --lib --profile test
cargo check -p <pkg> --test <integration-target> --profile test
```

### G1 — 最接近改动的一条规格

```bash
# 模块内 unit test；完整名字从 --list 获取
cargo test -p <pkg> --lib '<module::test_name>' -- --exact

# 一个 integration target 内的一条测试
cargo test -p <pkg> --test <integration-target> '<module::test_name>' -- --exact

# 只有公开文档契约变化时
cargo test -p <pkg> --doc
```

项目已用 nextest 时，可用其 `list` + exact/filterset 选同一 owner；不要为了快临时引入 nextest 依赖与配置。

### G2 — owner 所在测试目标

```bash
cargo test -p <pkg> --lib
cargo test -p <pkg> --test <integration-target>
```

### G3 — 受影响 package

```bash
cargo test -p <pkg>
```

### G4 — 契约/反向依赖/workspace/feature/platform

仅在以下证据出现时扩宽：公共 API 或 wire/schema 变化、workspace/manifest/profile/build.rs/proc-macro 变化、跨 crate trait/feature 组合、平台 cfg、共享 test-util、全局资源隔离。全 workspace、all-features、Miri/loom、真实服务 E2E 与跨平台矩阵属于 CI/夜间/明确全量，不是每次本地编辑默认。

Cargo 没有稳定、完美的“按 git diff 自动选全部受影响测试”真相源。可以用依赖图与代码所有权保守推导，但必须列出未覆盖边界，不能假装精准。

## 4. 去重：少写测试，增强 owner

按优先级处理：

1. **已有 owner 已锁同一不变量**：改 fixture 或追加更强断言；不新建文件、不加同义测试名。
2. **新性质完全包含旧 examples**：保留一个 property/model owner，删或参数化被包含的样例；重要历史 bug 可留一个可读的命名回归。
3. **unit 与 integration 重叠**：纯内部分支留 unit；跨 public 边界/链接/进程/协议留 integration。不要两层逐字复制相同输入与期望。
4. **doctest 与测试重叠**：doctest 只为用户可见示例和 API 可编译性；复杂边界由普通测试 owner。内部 crate 仅在成本可见且无文档契约时考虑 `doctest = false`（TEST-06）。
5. **集成目标过碎**：若多个文件共享昂贵启动/链接且无需进程隔离，合入较少 target 并共享 fixture；若依赖 env/cwd/panic/allocator/进程边界，保持独立。
6. **共享 helper**：test-util crate > integration target 内模块 > 遗留 `tests/common/mod.rs`；不把 helper 塞进生产 pub API。
7. **CI 重复**：给每个 job 标唯一证明职责。fmt/clippy/build/test/nextest 不得在无新增信号时重复相同测试运行；feature/platform 矩阵要做覆盖集合，不做无意义笛卡尔积。

净测试行数可以为负。删除前必须证明新 owner 的输入域和观察不变量包含旧测试，不能只因“看起来重复”。

## 5. 失败与 flake 不靠重复运行解决

- 单条 exact 红且固定输入稳定复现 → 回归，修生产或规格。
- 单跑绿、整目标红 → 查进程级共享（env/cwd/端口/OnceLock）、未 join task、测试顺序。
- 随种子/调度红 → 固定种子，按 testing.md 选模型/loom/shuttle/paused time；禁止 sleep 和 retry。
- 缺服务/工具 → fail-loud 或带原因 ignore/quarantine，不能静默 return。
- nextest/cargo retry 维持 0；已配置 retry 的仓库要把它列为债务，不用“最终通过”当绿。

## 6. 写入边界与完成条件

`--apply` 只允许在冻结范围内：

- 合并/参数化/删除被强 owner 完全包含的测试
- 把新增断言落到现有 owner
- 收敛 integration target、test-util、doctest target flag
- 去掉 CI 中完全相同的重复测试命令，或把矩阵改成有明确覆盖职责的集合
- 修复确定性与资源生命周期

每次行为改动默认新增 **0–3** 个测试；第 4 个前先展示四条互不包含的不变量。完成输出必须包含：

1. `改动面 → 不变量 → owner → 实际命令` 表。
2. 实际运行次数、测试 target 数和未运行范围；不能只写“tests passed”。
3. 合并/删除的重复证明及包含关系。
4. 回归测试“旧行为见红、新行为见绿”的证据；无法安全见红则列缺口。
5. 从 G1/G2 扩到 G3/G4 的具体理由。
6. 同一指纹没有被 cargo test/nextest/CI 重复执行，flake 没有被 retry 隐藏。
