# rust-skills — Rust 工程技能包

`/rust-skills:rust <命令> [target]`：一个入口、30 条命令。同一份技能源同步到支持的全部 harness。

> 立场：先守用户边界和项目事实，再追求正确、精简、可验证。规则是候选约束，不是把现有项目改造成统一模板的许可。**只推崇 edition 2024**（MSRV ≥ 1.85）。新仓 resolver 3；成熟 2024 仓钉 resolver 2 不迁。2018/2021 当迁移债务。

## 先记住四件事

1. **多数时候不必选命令。** 人在 Cargo 项目里改代码或贴 rustc，技能应主动走 craft / triage。命令用来要一份确定格式的报告或授权写入。
2. **裸命令默认不改你的代码。** 评审永远只读。改造类要 `--apply` 或说「改」才动。
3. **旧代码优化用 `distill`，不要等 `/optimize` 或 `/split`。** 拆不拆 crate 用 `crate`，由你拍板。
4. **大仓探索才开 swarm。** 多文件命令按 [kernel/swarm.md](skills/rust/kernel/swarm.md) 并行只读取证，合并进一份 ProjectSnapshot。`craft` / `triage` / 火焰图改帧循环禁止扇出。

不确定用哪条：直接说人话，或敲 `/rust-skills:rust` 看推荐。首轮提示见 [examples/first-prompts.md](examples/first-prompts.md)。

机械检查是 **E1/E2**（结构 + 磁盘 fixture），不是 E3 LLM 盲测：`./scripts/check-consistency.sh`。不得把绿灯写成「行为已验证」。

## 写授权：一条规则

- **评审类**（`review` `audit` `triage` `doctor`）永远只读，只出报告。
- **改造 / 语言语义 / 框架 / 交付类**（`harden` `modernize` `distill` `slim` `gate` `bench` `concurrency` `process` `async` `serde` `obs` `axum` `tauri` `seaorm` `sqlx` `cli` `ship` `xplat`）裸调用只体检、列计划；带 `--apply` 或明确说「改」才动代码。
- **搭建 / 治理类**（`init` `document` `capture`）只写自己声明的文件：RUST.md 或项目 outbox。
- `shape`、`crate` 默认只出建议。`crate` 你回复「拆」之后才改 workspace。`stack` 回复「改」后只给缺失层加依赖，不删活栈。
- `--record` 只额外写 RUST.md 的 managed 块，不改业务代码。

---

## 用例：你怎么说，它怎么做

每条都是可复制的。把路径换成你的模块即可。

### 1. 刚进一个老仓库

```text
/rust-skills:rust document
```

生成 / 刷新根目录 `RUST.md`（crate 图、facets、基线）。其余命令靠它提速。不改业务代码。

还没基线、lint 很乱时：

```text
/rust-skills:rust init
```

补 edition 2024、workspace lint 等最小工程差。**已是 2024 且 resolver 2 不会被改成 3。** 会先展示再落盘。

过一阵画像是否过期：

```text
/rust-skills:rust doctor
```

只读。edition 还是 2021 会标 DRIFT；2024 + resolver 2 + 只有 `rust-toolchain.toml` 是 OK。

### 2. 写功能（多数情况不用命令）

直接说：

```text
给 invoices 加上按状态筛选，改 crates/app/src/invoice.rs
```

技能应走 craft：`&str` 而不是 `&String`，钱不用 `f64`，不为过编译器 `.clone()`。

动手前想先定模型：

```text
/rust-skills:rust shape 发票按状态筛选
```

只出一页设计（落点 / 类型 / 错误 / 并发），不写码。拿不准拆不拆库时它会让你去 `crate`，不会自己搬家。

### 3. 编译器报 E0382 / borrow checker

贴报错即可，不必先选命令：

```text
交易系统报 E0382：audit.push(record); ledger.push(record);
```

或显式：

```text
/rust-skills:rust triage
/rust-skills:rust triage error[E0382]: borrow of moved value
```

合格输出是 HOW → WHY → WHAT，不会先丢 `record.clone()`。审计类不可变事实倾向 `Arc`。拼写 / 缺 import 一次修掉，不走三层。

### 4. 改完想自查

```text
/rust-skills:rust review
/rust-skills:rust review crates/app/src/invoice.rs
/rust-skills:rust review --record
```

无 target = 当前 git 改动；给路径 = 看这个路径的完整内容。永远只读。`--record` 只往 RUST.md 记一条评审快照。回复「改」才按表修。

单域挖深（仍只读）：

```text
/rust-skills:rust audit unsafe
/rust-skills:rust audit tests
/rust-skills:rust audit deps
```

域：`unsafe` / `deps` / `tests` / `build` / `async` / `api` / `security`。

### 5. 优化一段旧代码（精简 + 结构，不擅拆 crate）

```text
/rust-skills:rust distill src/legacy.rs
/rust-skills:rust distill src/legacy.rs --apply
```

必须点路径，不扫全仓。只读时列五遍候选：死码、塌层、去仪式、去无用分配、结构梯子（抽函数 / 拆 `mod`）。`--apply` 可改码、可拆 `mod`，**不会改 Cargo.toml**。值得独立成库时只会建议下一条。

### 6. 这个模块要不要独立成 crate

```text
/rust-skills:rust crate src/billing
```

三路对抗审查（赞成 / 反对 / 依赖方向），三选一：建议拆 / 建议留 / 证据不足。行数不是理由。你回复「拆」才按已展示映射改 workspace。

不要用 `crate` 当「文件太长」的拆分器——那是 `distill` / craft。

### 7. 能跑，但要上生产

```text
/rust-skills:rust harden crates/server
/rust-skills:rust harden crates/server --apply
```

补错误路径、边界、可观测、停机。裸调用只体检。

过时 API / 还在 2021：

```text
/rust-skills:rust modernize
/rust-skills:rust modernize --apply
```

`lazy_static` → `OnceLock`，edition 2018/2021 → 2024（`cargo fix --edition`）。授权后才改。

编译太慢（要有 timings，不猜）：

```text
/rust-skills:rust slim
```

先体检；拆 crate 仍要 WS-12 证据，不按行数拆。

磁盘被 `target/` 和过期开发文件吃满（不是「代码太多」）：

```text
/rust-skills:rust slim
```

先出四层表：可再生 `target/`、Cargo 全局缓存、未入库的 `perf.data`/火焰图、入库却没人引用的孤儿 `.rs`。不要 `rm -rf ~/.cargo`，也不要用 `cargo clean` 当加速。说「清磁盘」才动构建缓存；说「删」才动源文件。活文件里的死函数走 `distill`。

把门禁落成真检查：

```text
/rust-skills:rust gate
/rust-skills:rust gate --apply
```

假绿桩不算覆盖。不覆盖你已有的 `.git/hooks`。

### 8. 项目里已经在用这些框架

有 Cargo 证据才加载，不要先猜栈：

```text
/rust-skills:rust axum crates/server
/rust-skills:rust sqlx crates/storage
/rust-skills:rust seaorm crates/storage
/rust-skills:rust tauri crates/app
```

裸调用 = 体检（超时、池默认值、`query!` 离线、N+1…）。说「改」或 `--apply` 才动对应范围。

深入问题走同一条命令，owner 会按你的信号只加载 1–2 个子 playbook（`reference/axum/`、`reference/tauri/`），不整目录读：

```text
/rust-skills:rust axum 这个 JWT extractor 升到 0.8 后编译不过
/rust-skills:rust axum crates/server WebSocket 断线没人发现
/rust-skills:rust tauri capabilities 里 fs scope 怎么收紧
/rust-skills:rust tauri src-tauri 托盘左键在 mac 和 Windows 行为不一样
```

axum 子 playbook：scaffold / routing / extractors / handlers / middleware / realtime / auth / data / observability / testing / deploy / migrate。Tauri 子 playbook：setup / security / ipc / window / plugins / mobile / develop。

通用深层问题：

```text
/rust-skills:rust async crates/server
/rust-skills:rust process src/runner.rs
/rust-skills:rust concurrency
/rust-skills:rust serde crates/api
```

### 9. 发版、比性能、Windows 才坏

```text
/rust-skills:rust bench crates/core
/rust-skills:rust ship
/rust-skills:rust xplat
```

`bench` 必须有 target，要同机前后数据。`ship` / `xplat` 默认跟主产物（service / desktop），旁路工具 crate 不进范围。

### 10. 踩坑记下来 / 整理 docs

```text
/rust-skills:rust capture 为过编译器 clone 把审计记录复制成两份
/rust-skills:rust docs
/rust-skills:rust docs --apply
```

`capture` 写入项目 `.rust-skills/capture-outbox.md`，不会直接改技能包。`docs` 默认只读。

---

## 人话 → 命令（路由速查）

| 你说 | 走 |
|---|---|
| （贴 rustc /「报 E0382」） | 主动 triage，不必喊命令 |
| 「改 / 实现 / 补测试」 | 主动 craft |
| 「优化旧代码 / 这段太乱」+ 路径 | `distill` |
| 「要不要拆 crate」+ 模块 | `crate` |
| 「文件太长要拆吗」 | 写码中 → craft；旧文件 → `distill` |
| 「帮我 review」 | `review` |
| 「函数名 / crate 名 / get_xx / as_ 还是 into_」 | `name` |
| 「鉴权 / WebSocket / 中间件次序 / 0.8 迁移」 | `axum`（自动深入子 playbook） |
| 「capabilities / 插件 / 托盘 / 移动端 / v1 迁移」 | `tauri`（自动深入子 playbook） |
| 「新项目 / 补基线」 | `init` |
| 「先了解这个仓库」 | `document` |
| 裸 `/rust-skills:rust` | 只推荐 2–3 步，不执行 |

---

## 七个分类

| 分类 | 什么时候用它 |
|---|---|
| 搭建与设计 | 进项目、动手前：`init` 搭基线、`document` 生成画像、`shape` 先设计、`crate` 决定拆不拆 |
| 评审 | 只想看有没有问题，永远只读 |
| 改造 | 要动手改（加固/减肥/现代化/精简/门禁），裸调用只体检 |
| 语言语义 | 任何 Rust 项目的通用深层问题：并发、多进程、异步、序列化、函数/crate 命名 |
| 框架 | 项目用了对应框架才有证据加载：axum / Tauri / SeaORM / SQLx |
| 交付 | 测性能（bench）、发版（ship）、跨平台一致性（xplat） |
| 治理 | 文档集合治理（docs）、踩坑沉淀（capture） |

## 命令速查

命令表由 `scripts/command-metadata.json` 生成，勿手改；改源后跑 `./scripts/gen-command-tables.py`。

<!-- commands-table:start -->
#### 搭建与设计
/rust-skills:rust init                       # 把工程调和到最小基线并生成/刷新 RUST.md 画像；新项目从这里开始
/rust-skills:rust shape <feature>            # 写码前设计：落点/类型/错误/并发四问，只出一页设计小结
/rust-skills:rust crate <module>             # 对抗审查一个模块值不值得拆成 crate，只出建议
/rust-skills:rust document                   # 从当前项目事实生成/刷新 RUST.md 画像；老项目先跑这个
/rust-skills:rust stack [target] [--apply]   # 分析仓库与口述产物，推荐并（仅 --apply/「改」）按表给缺失层加依赖；不删活栈

#### 评审
/rust-skills:rust review [target]            # 按分级规则评审当前改动或指定路径，只读出问题清单
/rust-skills:rust audit <domain>             # 单域深审：unsafe / deps / tests / build / async / api / security
/rust-skills:rust triage [error]             # 编译错误分诊：先回答设计问题再动手，三次不过升级设计
/rust-skills:rust doctor                     # 体检技能库与项目画像的一致性/漂移，只读

#### 改造
/rust-skills:rust harden [target]            # 生产加固：错误路径、边界、可观测性、优雅停机
/rust-skills:rust slim [target]              # 构建减肥与文件卫生：timings 定位、裁依赖；过期开发文件/target 分层清理
/rust-skills:rust modernize [target]         # 把过时写法换成现代等价物（lazy_static → OnceLock 等）
/rust-skills:rust distill [target]           # 旧代码优化入口：删抽象、结构梯子、crate 只建议不擅迁
/rust-skills:rust gate                       # 生成/维护 xtask 门禁与 clippy 基线（只收紧不放宽）

#### 语言语义
/rust-skills:rust concurrency [target]       # 并发/并行选型与调优：rayon/tokio 桥、锁与调度；正确性测法见 testing.md
/rust-skills:rust process [target]           # 多进程选型与编排：隔离/故障域、Command 生命周期、fork 边界、进程池、IPC、信号停机
/rust-skills:rust async [target]             # 异步深审：取消安全、结构化停机、Stream 背压
/rust-skills:rust serde [target]             # 序列化边界：零拷贝、enum 表示、字段纪律、兼容演进
/rust-skills:rust obs [target]               # tracing 接线：只在 main 装一次、EnvFilter、json/pretty、字段/span 基数、WorkerGuard、测试 try_init
/rust-skills:rust name [target] [--apply]    # 函数/方法/crate 命名：as_/to_/into_、getter 禁 get_、From 构造器、包名 kebab 禁 -rs；按 API Guidelines 体检或改名

#### 框架
/rust-skills:rust axum [target]              # axum 0.8 服务：状态、边界防护、流式、超时；按信号深入路由/提取器/中间件/鉴权/实时/测试/迁移
/rust-skills:rust tauri [target]             # Tauri v2：体积、启动、IPC 选型；按信号深入权限/命令/窗口/插件/移动端/迁移
/rust-skills:rust seaorm [target]            # SeaORM 2.x：Entity Loader 策略/内存六杠杆、ActiveValue/NotSet、嵌套 save、upsert、迁移原子性
/rust-skills:rust sqlx [target]              # SQLx 0.8/0.9：池、query!、sqlx.toml、事务 Executor、row/领域分界
/rust-skills:rust cli [target]               # clap 4.6 CLI：derive、子命令、env、退出码、补全；解析只在 bin

#### 交付
/rust-skills:rust bench <target>             # 性能纪律：同机前后对比；火焰图测→看 self 帧→改一处→墙钟复测
/rust-skills:rust ship [target]              # 发布工程：容器产线 / 桌面签名 + 公证 + updater
/rust-skills:rust xplat [target]             # 跨平台一致性：平台边界、CI 矩阵、差异账本

#### 治理
/rust-skills:rust docs [target]              # 治理文档集合：首页/权威源/生命周期/链接，默认只读
/rust-skills:rust capture [lesson]           # 把踩坑蒸馏进项目 outbox，人工确认后提升为规则
<!-- commands-table:end -->

## 输出长什么样

所有命令同一骨架：一句话结论 → 范围行 → 明细（规则号只在这里）→ 验证 → 置信度 → 可复制的下一步。

> **结论**：这次改动没有必须修的 M 级问题；2 处建议顺手处理。
> 范围：\<项目根\> · 当前改动 · 12 个文件 · 只读
> | 位置 | 规则号 | 级别 | 问题 | 修复建议 |
> |---|---|---|---|---|
> | src/parser.rs:42 | ERR-03 | S | 生产路径裸 unwrap | 换成错误枚举传播 |
> 验证：未跑构建（只读评审）；置信度中。
> 下一步：`/rust-skills:rust review src/parser.rs` 深看单文件；回复「改」让我按表修复。
> 未改动任何文件。

---

## 安装

技能正文只维护 `skills/rust/`。各 agent 的清单、发现目录，以及仓库根给一层扫描器准备的兼容链接（`SKILL.md` / `reference/` / `rules/`）由 `./scripts/sync-providers.py` 生成，不要手改副本。

### 插件安装

```bash
# Claude Code
claude
> /plugin marketplace add /path/to/rust-skills   # 或推 GitHub 后 <you>/rust-skills
> /plugin install rust-skills@rust-skills

# Grok
grok plugin marketplace add /path/to/rust-skills
grok plugin install rust-skills --trust

# Oh My Pi (omp)
omp marketplace add /path/to/rust-skills
omp install rust-skills@rust-skills
# 或直接：omp plugin install /path/to/rust-skills
```

Claude Code 另有稳定别名 `/rust-skills:review`；不要使用裸 `/review`，它可能与内置命令冲突。Cursor / Codex 也可把本仓库当插件装（`.cursor-plugin/`、`.codex-plugin/`）。

### 发现目录

把仓库加进项目或链到用户技能目录后，各 harness 读下面这些路径（都指向同一份 `skills/rust`）。Codex 走 `.agents`，不单独铺 `.codex/skills`。dsh 也会扫 `.agents/skills`，但项目内优先 `.dsh/skills`。

把**整仓**当作一条技能目录安装时（例如 `~/.dsh/skills/rust-skills`），仓库根的 `SKILL.md`、`reference/`、`rules/` 是指向 `skills/rust/` 的兼容链接。DeepSeek Harness 等只扫一层的 harness 依赖这个；技能名仍是 frontmatter 里的 `rust`，不是目录名 `rust-skills`。

| Harness | 技能目录 |
|---|---|
| Claude Code | `.claude/skills/rust` |
| Cursor | `.cursor/skills/rust` |
| Codex | `.agents/skills/rust` |
| Grok Build | `.grok/skills/rust` |
| Kiro | `.kiro/skills/rust` |
| OpenCode | `.opencode/skills/rust` |
| Pi | `.pi/skills/rust` |
| Oh My Pi (omp) | `.omp/skills/rust` |
| DeepSeek Harness (dsh) | `.dsh/skills/rust` |
| Qoder | `.qoder/skills/rust` |
| Trae | `.trae/skills/rust` |
| Trae China | `.trae-cn/skills/rust` |
| Antigravity | `.agent/skills/rust` |
| Hermes Agent | `.hermes/skills/rust` |

用户级示例：

```bash
mkdir -p ~/.agents/skills ~/.cursor/skills ~/.omp/agent/skills ~/.dsh/skills
ln -s /path/to/rust-skills/skills/rust ~/.agents/skills/rust
ln -s /path/to/rust-skills/skills/rust ~/.cursor/skills/rust
ln -s /path/to/rust-skills/skills/rust ~/.omp/agent/skills/rust
ln -s /path/to/rust-skills/skills/rust ~/.dsh/skills/rust
```

首次进入一个 Rust 项目：`/rust-skills:rust document`（老项目）或 `/rust-skills:rust init`（新项目）。非 Claude / Grok 的技能名是 `rust`，同一套子命令。

## 维护与升级

- 踩坑/被打回 → `/rust-skills:rust capture`，先落项目 outbox，人工确认后才在源码仓库提升为规则与压力场景。
- 每周：跑一遍 `tests/pressure-scenarios.md` 与 `./scripts/check-consistency.sh`（含 `eval-fixtures.py`、`eval-triggers.py`）；`/rust-skills:rust doctor` 看漂移。本机装 ripgrep（`brew install ripgrep`）。
- 架构与规则治理细节见 [docs/DESIGN.md](docs/DESIGN.md)。
- 版本从 `0.0.1` 起按补丁递增，权威文件是 `.claude-plugin/plugin.json`；改完后跑 `./scripts/sync-providers.py`（它会先重生成命令表）。
- 仓库一致性检查：`./scripts/check-consistency.sh`。
