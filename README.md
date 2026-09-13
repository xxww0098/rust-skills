# rust-skills — Rust 工程技能包

`/rust-skills:rust <cmd> [target]`：一个入口，31 条命令；多数 Rust 工作直接说人话即可。

> **立场**：先守用户边界和项目事实，再追求正确、精简、可验证。新项目默认 edition 2024（MSRV ≥ 1.85）；成熟的 edition 2024 + resolver 2 项目不要为了“更新”迁到 resolver 3。

## 安装

推荐用 [SkillStar](https://github.com/xxww0098/SkillStar)：

```bash
skillstar add xxww0098/rust-skills
```

安装单元是一个 `.<harness>/` 层，或该层里的 `skills/rust`；**不是整个仓库**。单元内已包含所需运行时资源；不要再把仓库根的 `tests/`、`scripts/`、`docs/` 和其它 harness 投影一起安装。

技能正文的 SSOT 是 [`skills/rust/`](skills/rust/)。已有 clone、需要手动接入 harness 时，链接 `skills/rust/`，不要链接仓库根。按 harness / 插件安装细节见 [docs/DESIGN.md](docs/DESIGN.md)。

## 60 秒开始

第一次进老仓库：

```text
先读这个 Rust workspace 的实际结构和约束，生成项目画像；不要改业务代码。
```

要实现功能：

```text
给 invoices 加按状态筛选。先遵守现有边界和错误模型，再实现并补最小必要测试。
```

遇到编译错误：

```text
error[E0382]: borrow of moved value
先解释根因，再给最小正确修复；不要为了过编译器直接 clone。
```

更多可复制提示词见 [`examples/first-prompts.md`](examples/first-prompts.md)。

## 写授权：只记一条规则

**没有明确写授权，就先 inspect，不擅自改。**

- `review` / `audit` / `triage` / `doctor` 永远只读。
- 改造 / 语言语义 / 框架 / 交付类默认只体检；说「改」或带 `--apply` 才写代码。
- 搭建 / 治理类只写命令声明的文件（如 `RUST.md`、项目 outbox），不借机改业务代码。
- `shape` / `crate` / `stack` / `batteries` 先给建议再过 apply gate：`crate` 要明确「拆」；`stack` / `batteries` 要「改」或 `--apply`。
- `--record` 只额外写 `RUST.md` 的 managed 块，不等于业务写授权。

## Engage：通常不用先挑命令

在 Cargo 项目里直接描述任务即可。编码请求自动走 **craft**；贴 rustc / borrow-checker 错误自动走 **triage**。

每一轮只选 **一个 primary**，最多补 **一个 side-note**。不要因为缺画像或基线，就把 `document + review + init` 串成一轮全做。

裸 `/rust-skills:rust` 只推荐接下来 2–3 步，不自动执行。

## Top journeys

### 1. 老仓库：先建立事实，不先重构

```text
/rust-skills:rust document
/rust-skills:rust doctor
/rust-skills:rust review
```

`document` 生成/刷新 `RUST.md`；`doctor` 看漂移；`review` 看当前改动或指定路径。三者都不授权顺手改业务代码。

### 2. 新功能：先说需求；需要设计时再 shape

多数时候直接说：

```text
给 crates/app/src/invoice.rs 加按状态筛选，沿用现有错误类型和测试风格。
```

需要先定模型：

```text
/rust-skills:rust shape 发票按状态筛选
```

`shape` 只收敛落点、类型、错误和并发边界。拆不拆 crate 交给 `crate`；“文件长”不等于“该拆 crate”。

### 3. 报错：贴 rustc，先 HOW → WHY → WHAT

```text
/rust-skills:rust triage error[E0382]: borrow of moved value
```

目标不是最快塞 `.clone()`，而是先判断 ownership 是否正确，再给最小修复。

### 4. 技术栈 + batteries：先选层，再补最小 kit

```text
/rust-skills:rust stack 这是一个 HTTP API + Postgres 服务
/rust-skills:rust batteries 这是一个 HTTP API + Postgres 服务
```

`stack` = 技术选型（ST-*）；`batteries` = 按项目图 / Facets 组装最小 kit（BAT-*）。都先展示，不先改 `Cargo.toml`；不替换活栈。

绿场常见顺序（**不要一次全做**）：

```text
init → shape → document → doctor → gate → stack → batteries → craft
```

另外：`slim ≠ distill`。`slim` 管编译慢 / `target` / 过期文件；`distill` 管旧代码抽象、仪式、分配和模块结构。

## 人话 → command

| 你说 | 路由 |
|---|---|
| 「实现 / 改这个功能 / 补测试」 | 自动 craft |
| 贴 rustc / borrow-checker 错误 | 自动 triage |
| 「先设计这个功能」 | `shape` |
| 「帮我 review」 | `review` |
| 「单独深审 unsafe / deps / tests」 | `audit` |
| 「优化这段旧代码」+ 路径 | `distill` |
| 「要不要拆成 crate」 | `crate` |
| 「编译太慢 / target 太大」 | `slim` |
| 「用什么框架 / 技术栈」 | `stack` |
| 「还缺哪些 crate」 | `batteries` |
| 「上生产前加固」 | `harden` |
| 「axum / Tauri / SeaORM / SQLx / clap」 | 对应 framework command |

## Command categories

| Category | Commands |
|---|---|
| 搭建与设计 | `init` `shape` `crate` `document` `stack` `batteries` |
| 评审 | `review` `audit` `triage` `doctor` |
| 改造 | `harden` `slim` `modernize` `distill` `gate` |
| 语言语义 | `concurrency` `process` `async` `serde` `obs` `name` |
| 框架 | `axum` `tauri` `seaorm` `sqlx` `cli` |
| 交付 | `bench` `ship` `xplat` |
| 治理 | `docs` `capture` |

完整命令表由 `scripts/command-metadata.json` 生成。下面两个 markers 是 generator contract，**必须保留**；改 metadata 后跑 `./scripts/gen-command-tables.py`，不要手工维护生成区。

<!-- commands-table:start -->
#### 搭建与设计
/rust-skills:rust init                           # 把工程调和到最小基线并生成/刷新 RUST.md 画像；新项目从这里开始
/rust-skills:rust shape <feature>                # 写码前设计：落点/类型/错误/并发四问，只出一页设计小结
/rust-skills:rust crate <module>                 # 对抗审查一个模块值不值得拆成 crate，只出建议
/rust-skills:rust document                       # 从当前项目事实生成/刷新 RUST.md 画像；老项目先跑这个
/rust-skills:rust stack [target] [--apply]       # 分析仓库与口述产物，推荐并（仅 --apply/「改」）按表给缺失层加依赖；不删活栈
/rust-skills:rust batteries [target] [--apply]   # 按项目图 / Facets 组装最小 crate 工具箱；默认只读，改/--apply 才加缺失层

#### 评审
/rust-skills:rust review [target]                # 按分级规则评审当前改动或指定路径，只读出问题清单
/rust-skills:rust audit <domain>                 # 单域深审：unsafe / deps / tests / build / async / api / security
/rust-skills:rust triage [error]                 # 编译错误分诊：先回答设计问题再动手，三次不过升级设计
/rust-skills:rust doctor                         # 体检技能库与项目画像的一致性/漂移，只读

#### 改造
/rust-skills:rust harden [target]                # 生产加固：错误路径、边界、可观测性、优雅停机
/rust-skills:rust slim [target]                  # 构建减肥与文件卫生：timings 定位、裁依赖；过期开发文件/target 分层清理
/rust-skills:rust modernize [target]             # 把过时写法换成现代等价物（lazy_static → OnceLock 等）
/rust-skills:rust distill [target]               # 旧代码优化入口：删抽象、结构梯子、crate 只建议不擅迁
/rust-skills:rust gate                           # 生成/维护 xtask 门禁与 clippy 基线（只收紧不放宽）

#### 语言语义
/rust-skills:rust concurrency [target]           # 并发/并行选型与调优：rayon/tokio 桥、锁与调度；正确性测法见 testing.md
/rust-skills:rust process [target]               # 多进程选型与编排：隔离/故障域、Command 生命周期、fork 边界、进程池、IPC、信号停机
/rust-skills:rust async [target]                 # 异步深审：取消安全、结构化停机、Stream 背压
/rust-skills:rust serde [target]                 # 序列化边界：零拷贝、enum 表示、字段纪律、兼容演进
/rust-skills:rust obs [target]                   # tracing 接线：只在 main 装一次、EnvFilter、json/pretty、字段/span 基数、WorkerGuard、测试 try_init
/rust-skills:rust name [target] [--apply]        # 函数/方法/crate 命名：as_/to_/into_、getter 禁 get_、From 构造器、包名 kebab 禁 -rs；按 API Guidelines 体检或改名

#### 框架
/rust-skills:rust axum [target]                  # axum 0.8 服务：状态、边界防护、流式、超时；按信号深入路由/提取器/中间件/鉴权/实时/测试/迁移
/rust-skills:rust tauri [target]                 # Tauri v2：体积、启动、IPC 选型；按信号深入权限/命令/窗口/插件/移动端/迁移
/rust-skills:rust seaorm [target]                # SeaORM 2.x：Entity Loader 策略/内存六杠杆/泄漏分诊、ActiveValue/NotSet、嵌套 save、upsert、迁移原子性
/rust-skills:rust sqlx [target]                  # SQLx 0.8/0.9：池、query!、sqlx.toml、事务 Executor、row/领域分界
/rust-skills:rust cli [target]                   # clap 4.6 CLI：derive、子命令、env、退出码、补全；解析只在 bin

#### 交付
/rust-skills:rust bench <target>                 # 性能纪律：高层 SQL/HTTP/锁先于火焰图；同机前后对比；测→看 self→改一处→墙钟
/rust-skills:rust ship [target]                  # 发布工程：容器产线 / 桌面签名 + 公证 + updater
/rust-skills:rust xplat [target]                 # 跨平台一致性：平台边界、CI 矩阵、差异账本

#### 治理
/rust-skills:rust docs [target]                  # 治理文档集合：首页/权威源/生命周期/链接，默认只读
/rust-skills:rust capture [lesson]               # 把踩坑蒸馏进项目 outbox，人工确认后提升为规则
<!-- commands-table:end -->

## 输出契约

命令输出统一：**结论 → scope → findings → verification → confidence → next step**。规则号留在明细里。

`check-consistency.sh` 绿灯只说明 **E1/E2**（结构 + 磁盘 fixture）通过，**不等于** behavioral verification / E3。E3 契约与 prompt 集在 [`evals/`](evals/)；真跑 agent 才是 `python3 scripts/eval-agent.py --live`。


## 深入阅读

- [examples/first-prompts.md](examples/first-prompts.md)：更多可复制入口
- [evals/](evals/)：技能评测（prompt → run → checks → score）
- [docs/DESIGN.md](docs/DESIGN.md)：架构、规则治理、harness sync、maintainer 细节
- [CHANGELOG.md](CHANGELOG.md)
- [skills/rust/](skills/rust/)：技能正文 SSOT
- [SkillStar](https://github.com/xxww0098/SkillStar)

维护者：改 metadata 后保持 generator 可运行；harness projection 由仓库脚本生成，不要把用户路径和 provider-sync 细节重新混进 README。
