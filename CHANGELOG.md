# Changelog

## 0.0.56 — 2026-08-28

- `/name` 覆盖项目 crate 命名：NM-11 C-CRATE（kebab、禁 `-rs`/`-rust`）、NM-12 成员按职责+产品前缀（禁 `utils`/`common`）、NM-13 包名/ident/模块对齐、NM-14 C-FEATURE。
- 权威 [C-CASE](https://rust-lang.github.io/api-guidelines/naming.html)「Every crate is Rust」+ Cargo [`-sys`](https://doc.rust-lang.org/cargo/reference/build-scripts.html#-sys-packages)。`--apply` 仍只改函数；改包名必须说「改 crate 名」。
- 场景 87。触发：「crate命名 / 包名 / -rs 后缀」。

## 0.0.55 — 2026-08-28

- 新命令 `name`：函数/方法命名体检。权威 [Rust API Guidelines Naming](https://rust-lang.github.io/api-guidelines/naming.html)（C-CASE / C-CONV / C-GETTER / C-ITER / C-CTOR）。
- X：[Raphael Luba](https://x.com/LubaRaphael/status/2048444288866934979) `Thing::from_stuff` 对齐类型，不要 `stuff_to_thing`；方法优于 C 式 `type_verb`。
- API-07 指向本命令。场景 86。触发：「函数命名 / get_ 前缀 / as_ to_ into_」。

## 0.0.54 — 2026-08-28

- 命令级 swarm：`kernel/swarm.md` 给需要并行取证的命令列出车道；子 agent 只读，合并进同一份 ProjectSnapshot。
- 开：document/review/doctor/crate/stack/audit/harden/slim/distill/gate/modernize 与语言/框架/交付体检。禁：craft/triage/shape/capture/init 与火焰图改帧循环。
- bench 火焰图子 playbook（profile/read/loop/optimize）+ PERF-06：`[unknown]` 禁止改码，agent 不 sudo。

## 0.0.53 — 2026-08-28

- SH-16 桌面构建矩阵：macOS「双端」= 原生 mac 包 + cargo-xwin **未签名** NSIS。Tauri 只认 MSVC；WiX/MSI 与 Authenticode 必须 Windows。
- 交叉链前提：`lld`（Homebrew llvm 不含 lld-link）、`nasm`、`cargo fetch --target` 先于 offline、UTF-8 locale、产物在 `target/<triple>/release/bundle/nsis/`。
- TA-47 renderer `localStorage` 不是设置存储；跨会话偏好走宿主 command 写 `app_data_dir`。
- 触发：「交叉编译 / 双端编译 / cargo-xwin / NSIS / localStorage」。场景 83。

## 0.0.52 — 2026-08-28

- 合并 [#1](https://github.com/xxww0098/rust-skills/pull/1)：`/cargo`、`/test`、`/cargo tools` 作为 `slim` 子模式，不增加隐式路由。
- Cargo / 测试 / 工具带共用一份 ProjectSnapshot 与命令指纹；禁止为仪式重复 metadata。
- `bench` 火焰图闭环：profiling profile → 点名 self 符号 → 改一帧 → 同命令测墙钟。

## 0.0.51 — 2026-08-28

- 蒸馏 Axum「分层路由 + 全局异常」：不是 Spring `@ControllerAdvice`。
- AX-53 错误所有权分层（repo 不知 HTTP；状态码只在 `IntoResponse`）。
- AX-54 禁止中间件读响应体 / `HandleErrorLayer` 包 Router 抓 `AppError`。
- 「分层路由」「全局异常」触发进 `axum` → `routing`/`handlers`。

## 0.0.50 — 2026-08-28


- 蒸馏 Rust 静态分析工具链：一层一职（rustc → fmt → clippy → deny → 选择性 Miri/semver-checks/hack/Kani）。
- LINT-07 同层不双跑（deny advisories 覆盖 cargo-audit）；LINT-08 工具链钉 clippy/rustfmt；GATE-06 禁止 G4 进每次 push。
- **未做**：默认装 Kani/Sonar、cargo-geiger 当门禁。

## 0.0.49 — 2026-08-28


- 深度闭环：inspect 增加 fan-in 与 unwrap/println 信号；`render_rust_md.py` 钉死 RUST.md 四个投影节；`check_patch.py` 机械拒绝 clone/unwrap/println。
- `kernel/verification.md`：写完必须跑 check_patch + Patch 里的 cargo 命令。document 禁止手绘 crate 图。
- **未做**：E4 模型评 Patch、provider 迁 dist、callers/cfg 全量图。

## 0.0.48 — 2026-08-28


- 写出路径：`kernel/write.md` Patch 契约。实现/修/改必须按规范形状落盘，不能先写绿再等 review。
- META-07：写不出 Patch 不准改文件。拒绝 clone-to-compile、生产 unwrap、服务端 println、无规格测试。
- 修复 SKILL.md 重复的不变量/执行协议段。
- **未做**：E4 模型跑 Patch、RUST.md renderer、provider 迁 dist。

## 0.0.47 — 2026-08-28


- PR 1（对抗审查）：kernel 收口。不改 29 条命令、不迁 provider 树。
- `kernel/scope.md` / `evidence.md` / `finding.md`；`schemas/project-snapshot.schema.json` + `finding.schema.json`。
- META-06：review/document/doctor/crate/distill/harden 本轮只消费一份 ProjectSnapshot。
- `scripts/inspect_project.py`：crate 图、环、孤儿、入口；`tests/projects/` 四个真实 Cargo fixture。
- `.github/workflows/check.yml`。edition 2024 在 SKILL 中降为生成默认，不再当存量健康不变量。
- **未做**：provider 树迁 dist/、拆 check-consistency.sh、E4 模型行为测试、inspect 的 callers/cfg 全量。

## 0.0.46 — 2026-08-28


- 蒸馏「Rust 日志终极指南」（tracing 概念/架构/Span/Registry+Layer）。不整篇搬教程。
- OBS-07 / TR-19：`fmt::init()` ≠ `fmt().init()` 默认过滤器。
- TR-20：多 sink 用 Registry+Layer；修正 TR-03——禁止的是同一 writer 两层 fmt，不是「永远只能一层」。
- TR-21 `in_scope`；TR-22 `FmtSpan` 默认关；`#[instrument]` 只标业务边界。
- **未做**：强制 `tracing-error`、把 XML/YAML 日志配置引进 Rust。

## 0.0.45 — 2026-08-26


- 蒸馏：[Anthropic skill authoring](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)（body ≤500 行、description ≤1024）；[Jesse Vincent](https://www.ksred.com/best-claude-code-skills-which-ones-are-actually-worth-installing/) Claude Code 15k 描述预算静默丢 skill；[Macroscope AI Rust review](https://macroscope.com/content/ai-code-review-rust) 信任边界 panic；[Microsoft Rust Engineering](https://microsoft.github.io/RustTraining/engineering-book/) + [cargo-hack](https://github.com/taiki-e/cargo-hack) powerset。
- ERR-09 `xs[i]` / 入站 `/`；SIMP-13 AI 过编译器味；GATE-05 `cargo hack --feature-powerset --no-dev-deps`。
- `eval-triggers.py` 卡住 SKILL 体量与 pin description 总长。
- **未做**：覆盖率棘轮、heapless MUST、RoutePlan IR、把 SKILL 再砍到 8KB（当前 body 138 行，已低于 500）。

## 0.0.44 — 2026-08-26


- 蒸馏 ChatGPT 对 v0.0.43 内核审查（转译/透传/上下文）。P0 only。
- `scripts/activation.json` 成为 description 唯一事实源；plugin / SKILL / openai.yaml 由 sync 生成。description **不再**写 Python/翻译等负向词（embedding 假阳性）。
- `eval-triggers.py` 改测：正样本在 description；skip 在「非目标」；`near_neighbors` 被消费。
- `sync-providers.py`：无 symlink 时 **copy**，`--check` 缺文件即失败；为全部命令生成 slash pin。
- 路由固定优先级：显式命令 > 写入意图 > rustc > 动词 > 领域。`review --apply` 仍只读。
- **未做**：RoutePlan IR、staging 事务同步、SKILL 8KB 硬预算、把 check-consistency.sh 改成 Python 薄包装。

## 0.0.43 — 2026-08-26


- 蒸馏 Cursor `thermo-nuclear-code-quality-review`：可移植机制是「删复杂度，不搬家」。**不**新开命令，**不**把「go for it」写进只读 `review`。
- SIMP-09 文件跨 1000 行红旗（处置仍 WS-11）；SIMP-10 spaghetti 特判；SIMP-11 层/helper；SIMP-12 无故串行/半应用。
- `review` 热核档：结构优先、测试绿不是批准；judo 候选指向 `distill`。
- 场景 74。

## 0.0.42 — 2026-08-23


- 蒸馏 arrayref 投毒窗口 + Cargo RFC 3923：DEP-11 CI `--locked` / 禁无人值守 `cargo update`；DEP-12 deny/audit/vet 不覆盖零日头几小时；DEP-13 应用侧 min-publish-age（实验性 `-Z`，不改默认 toolchain）。
- GATE-04：G3 `--locked`；G4 可选 nightly 冷却期解析。gate playbook 给出 `.cargo/config.toml` 候选与热修绕过。
- audit deps/security、init、stack、harden 叠一层。场景 73。

## 0.0.41 — 2026-08-23


- 用 dao-skill / yao-meta-skill 的元规范做最小补丁：触发面排除项、诚实证据级别（E1/E2 ≠ LLM 已验证）、agents 可移植、正负触发契约。
- description 增加 Skip Python/Go/JS、translation、generic summaries；SKILL 增加「非目标」。
- README 命令数 28→29；写授权补 `obs`/`cli`/`stack`。
- 新增 `evals/triggers.json` + `scripts/eval-triggers.py`、`examples/first-prompts.md`、`SECURITY.md`、`skills/rust/agents/openai.yaml`。
- **不**引入 yao.py / Skill IR / Review Studio（与 rust 工程技能的根问题无关）。

## 0.0.40 — 2026-08-22


- `stack` 落地（ST-14）：默认仍只出表；「改」/`--apply` 只给**缺失层** `cargo add` 并钉 floor，不删活栈、死亡线不与绿场默认并列。接线仍走 `obs`/`axum`；`init` 不引入 web/cli/obs 依赖。
- version-floor 补钉：tokio 1.53.1、tracing 0.1.44、tracing-subscriber 0.3.23、serde 1.0.229、serde_json 1.0.151、tower-http 0.6.11（不配 0.7）、reqwest 0.13.4。
- serde SE-11..15：禁 Value 当模型、密钥 skip、rename_all 统一、递归上限、入站禁 unwrap。
- AX-17 出站 HTTP 双超时 + 用户 URL 禁自动 redirect；craft 叠加。CL-13/ST-15 配置由 bin clap env 注入。
- 场景 71/72。

## 0.0.39 — 2026-08-22


- `obs` 接入 tracing 最佳实践：TR-11 库禁 init、TR-12 WorkerGuard 活到退出、TR-13 测试 `try_init`/`with_test_writer`、TR-14 span 名静态、TR-15/16 enabled! 与 Empty+record、TR-17 console-subscriber 仅 dev。
- 全局 OBS-05/06。`stack` ST-08 与 `cli` CL-10 指回 obs。场景 70。

## 0.0.38 — 2026-08-22


- 新命令 `stack`：分析仓库 + 口述产物，按层给出钉死版本的技术栈表；只读，不改 `Cargo.toml`。
- ST-01 先定产物；ST-02 能干活的栈默认留；ST-04..10 绿场默认 axum 0.8.9 / clap 4.6.6 / Tauri 2.11.5 / sqlx 或 sea-orm 二选一 / tracing；ST-11 禁 latest；ST-13 永不写码。
- 场景 69 + 磁盘 fixture（rocket 0.4 + async-std + structopt 绿场错配）。

## 0.0.37 — 2026-08-22


- 并发/并行/火焰山怎么测，以及 agent 测文件膨胀：新增 [testing.md](skills/rust/reference/testing.md)，TEST-13..16，CC-15/16。
- TEST-13 补测预算：先搜现有覆盖；一次改动 1–3 个测试；套套逻辑删；被新性质包含的旧测试合并。
- TEST-14 火焰山 = 偶发变红（真实时间 / 未 join / 进程级全局），禁 sleep、禁 CI retry、禁删测试变绿；先隔离再修根因。
- TEST-15 选层：顺序模型 → loom → shuttle → Miri → tokio pause → turmoil；hammer 不算证明。TEST-16 默认并行跑测试，共享全局才串行。
- CC-15/16 把正确性测法与加速比验收从选型里拆开。场景 68。

## 0.0.36 — 2026-08-22


- 蒸馏桌面跨平台手册（Tauri 2.11.5 路径解析 / IPC 线程 / 关窗 / worker / 打包）进技能，不带项目专有约定。owner 增 TA-40..46；SHIP 增 SH-13..15。
- TA-40 Windows `app_data_dir`（Roaming `%APPDATA%`）≠ `app_local_data_dir`（`%LOCALAPPDATA%`），混用即锁/库分裂。
- TA-41 同步 command 内联主线程（`rfd::FileDialog` 合法）；async command 禁阻塞 rfd；plugin-dialog `blocking_pick_file` 仍须 async（与 rfd 相反）。
- TA-42 无托盘时 macOS 关窗要 hide+`prevent_close`+`RunEvent::Reopen`；Windows 关主窗默认退出。
- TA-43 同 exe worker 优先 sidecar；超时 worker 禁回池；`Child::kill` 不杀孙进程。TA-44 `AddrInUse` 回退 `:0`。TA-45 同卷 rename + Windows 不能覆盖。TA-46/`SH-13..15`：DMG `CI=true`、cargo-xwin 未签名 NSIS、makensis UTF-8 locale、GUI 父进程 `CREATE_NO_WINDOW`。
- 场景 67 + 磁盘 fixture。

## 0.0.35 — 2026-08-22


- 全网对齐现行线后扩命令：新增 `cli`（clap 4.6.6 derive/env/补全/退出码，CL-01..12）与 `obs`（tracing 0.1 + subscriber 0.3 进程级接线，TR-01..10）。28 条命令。axum HTTP 观测仍走 `axum/observability.md`。
- sqlx 加深 SX-13..16：`sqlx.toml`（feature 默认关）、0.9 runtime/TLS 拆开、`&mut *txn` Executor、SQLite extension 非默认且 unsafe。seaorm 加深 SO-13..16：Entity Loader、`ExprTrait`、`execute` vs `execute_raw`、1.x→2.0 不自动升。
- modernize 补 1.95–1.96：`if let` guards、`cfg_select!`、`Vec::push_mut`、`core::range`、`assert_matches!`、`bool::try_from`。craft/engage/routing/harden 接到新命令。
- 场景 65/66 + 磁盘 fixture；version-floor 增加 clap 4.6.6。现行 stable rustc 1.98 不抬仓 MSRV（仍 ≥1.85）。

## 0.0.34 — 2026-08-22


- P2：每个命令至少一份磁盘 fixture。`tests/fixtures/scene-*/contract.json` 成为机械契约源；`eval-fixtures.py` 读目录而不再内嵌 CONTRACTS，并核对 26 条命令全覆盖。补场景 5/6/7/8/10/11/12/13/14/15/16/17/18/19/20/21/22/23/24/29/40/43/45/60/61/63/64。
- P2：`scripts/version-floor.json` + `scripts/check-floor.py` 钉死 edition 2024 / MSRV 1.85 与 axum 0.8.9、tauri 2.11.5、sqlx 0.9.0（MSRV 1.94）、sea-orm 2.0.2。默认离线；`--fetch` 才打 crates.io（同线新 patch 警告，换线失败）。
- `review.md` 点名 TEST-03 / API-02，与场景 6 fixture 对齐。doctor 库检清单加上 fixture eval 与 version floor。

## 0.0.33 — 2026-08-22


- Frontmatter：`description` 去引号、去掉冒号空格，补中英触发与负向触发（Skip non-Cargo / 纯概念问答）；`metadata.type=workflow`。版本 0.0.33。
- 命令表双语：`scripts/command-metadata.json` 为 26 条命令补 `triggers_en`；`gen-command-tables.py` 写入 SKILL 路由表「中/英」列。改造四条（`distill`/`slim`/`modernize`/`harden`）在 SKILL 路由节互斥。
- 规则按域拆分：`rules/meta.md` … `rules/d.md` 为源，`rules/rules-full.md` 由 `scripts/gen-rules-full.py` 合并。SKILL 增加「规则按域加载」表。`namespaces.txt` 指向分文件。DEP-08 写明依赖 MSRV 可高于仓基线（sqlx 0.9 / 1.94），禁止为「现行稳定线」抬全仓。
- Owner 减肥：`reference/axum.md` 与 `reference/tauri.md` 改为编号索引 + 深入表，AX-22..52 / TA-14..39 一句话指向子 playbook，不再在 owner 重复长文。sqlx/seaorm/axum/tauri 目的段补「不要读」。
- Grok 安装不依赖 symlink：`sync-providers.py` 对 `.grok/` 与包根 `SKILL.md`/`reference/`/`rules/` 落真实副本；其他 harness 优先 symlink，无 `/dev/fd` 的沙箱跳过而非复制 13 份。`check-root-compat.py` 接受内容等价的根副本。`check-consistency.sh` 改用临时文件，不再依赖 bash process substitution。

## 0.0.32 — 2026-08-22

- 灌注 Axum-Claude-Skill-Package（29 技能）与 tauri-skills（52 技能）的能力，**不新增命令**：深入材料落在 `reference/axum/`（12 篇）与 `reference/tauri/`（7 篇）子 playbook，由 owner `reference/axum.md` / `reference/tauri.md` 的「深入（按信号加载）」表按用户信号加载 1–2 个，不整目录读。
- owner 编号扩容：AX-18 → AX-52（路由/状态组合、中间件次序、实时、认证授权、上传静态、部署停机、测试迁移），TA-13 → TA-39（权限与 CSP、命令与状态、窗口托盘菜单、插件纪律、移动端、测试迁移）。AX-01..18 / TA-01..13 语义不变，AX-18 的 `{id}`/`:id` 字面量保留（eval 契约依赖）。
- 一致性脚本新增子目录契约：`reference/<命令>/` 必须有同名 owner、每个子文件以 `目的：` 开头且被 owner 以 `(<命令>/<name>.md)` 入链；局部编号扫描扩到子目录（`rglob`），子 playbook 只能行内引用、不得定义编号。
- 压力场景 58 → 64：新增 59（0.8 自定义 extractor 的 `#[async_trait]` 与 `Option<T>` 语义）、60（组合根顺序错致中间件静默丢失）、61（JWT 密钥字面量 + 无 `exp` + 上传收全量）、62（capability 裸通配 + 生产 CSP 为 null）、63（`async fn` 命令借用 + 事件当高频通道 + `invoke_handler` 双调）、64（single-instance 插件次序 + sidecar 缺 target triple + v1 `allowlist` 残留）。59/62 带磁盘 fixture，eval 契约 4 → 6。
- 路由与主动介入接线：`command-metadata.json` 给 axum/tauri 补触发词（鉴权/WebSocket/中间件/0.8 迁移；capabilities/插件/托盘/移动端/v1 迁移）；`routing.md`、`engage.md`、`craft.md` 按证据指向 owner 再指向子 playbook；`audit.md`（security 面）、`review.md`（facets 加权）、`harden.md`、`shape.md`、`ship.md` 交叉链到对应子 playbook。
- 所有子 playbook 与 owner 经对抗核验后修正（含 axum 0.8 `Option<Extractor>` 的 `Optional*` 实现清单、`method_not_allowed_fallback` 实为 0.7.8+、`reset_fallback` 为 0.8.4+、tauri `CommandScope<T>` 无生命周期参数、capability 漏配的真实症状是「自定义命令仍可调、插件/core 命令全拒」、`app.request_restart()` 与 `RESTART_EXIT_CODE`）。

## 0.0.31 — 2026-08-20

- Pack root is a one-level skill directory: `SKILL.md`, `reference/`, and `rules/` at the repo root link to `skills/rust/`. Harnesses that install the whole pack as `~/.dsh/skills/rust-skills` (DeepSeek Harness only scans one level) can load it; the catalog name is still `rust`. Skill body still lives only in `skills/rust/`.
- Scene 56 gets an on-disk fixture and joins `eval-fixtures.py` (unsafe fn without inner `unsafe {}`, `f()?;` never-type fallback).
- AX-18: axum 0.8 path params are `{id}` / `{*path}`, not 0.7 `:id` / `*path`. Scene 57 + fixture. Still no new commands.

## 0.0.30 — 2026-08-20

- Local/CI: install ripgrep (`rg` 15.2.0). Consistency still has a grep shim, but real rg is the expected path.
- Scene 54/55 get on-disk fixtures (`tests/fixtures/scene-54|55/hits.rs`) and a mechanical contract runner `scripts/eval-fixtures.py`, wired into `check-consistency.sh`. This is not an LLM session substitute.
- Framework floors from crates.io (2026-08): axum 0.8.9 current / 0.7 still in-scope / 0.6 `axum::Server` is debt; sqlx 0.8+0.9 (0.9.0, MSRV 1.94, optional `sqlx.toml`) / 0.7 still in-scope; SeaORM 2.0.2; Tauri 2.11.5 (`removeUnusedCommands` since 2.4). No new commands.
- Remaining 2024 agent-wrong semantics, no new verbs: UNSAFE-03 names `unsafe_op_in_unsafe_fn`; D-6 + triage cover never-type fallback (`!` must not flow into unsafe). Scene 56.

## 0.0.29 — 2026-08-20

- Absorb Edition Guide 2024 unsafe attributes / unsafe extern, `std::env::set_var` Safety, Rust 1.88 let chains, and 1.87 `std::io::pipe`: UNSAFE-10/11, FFI-10. `cargo fix --edition` is syntax only. Unix multithreaded `set_var` is not a SAFETY comment away from sound. Scene 54–55.
- SIMP-08: let chains flatten `if let` + bool nesting; they do not replace exhaustive `match`. Scene 48 updated.
- audit/modernize/process/craft catch up: scan `no_mangle`/`extern`/`set_var`; child env via `Command::env`; merged stdout/stderr prefer `io::pipe()`.
- Agent Skills spec: SKILL frontmatter `license: MIT`; description keywords add clippy, borrow-checker, axum/sqlx/tokio, unsafe/FFI.
- Graded rules 122 → 125. Fix stale audit ranges BUILD-01..08 / API-01..07.

## 0.0.28 — 2026-08-20

- Consistency checker no longer depends on the caller's locale: `LC_ALL=C` used to false-fail all 26 command-coverage checks because pressure titles use full-width parens. The `rg` grep shim now errors on missing files instead of returning empty matches, and warns when falling back from ripgrep.
- Enforce SKILL 写入边界 against references: review/audit/triage/doctor must stay read-only and must not authorize `--apply` to write code; shape/crate must forbid writing code. Scene 53: triage outputs the trace, craft writes.
- triage 目的句钉死只读；拼写/缺 import 在未获写入授权时只给补丁。

## 0.0.27 — 2026-08-20

- Absorb 2025 Compiler Performance Survey + Cargo 1.93 + Performance Book: BUILD-09 (RA vs cargo target lock), BUILD-10 (deps → debuginfo → linker → split). slim refuses 2021 lld rustflags and Feldera-1000-crates as defaults. PERF-03/04: clone_from, no collect-then-iterate. Scene 52.

## 0.0.26 — 2026-08-20

- README: copy-paste use cases for every user journey (document/init, craft, triage, review, distill, crate, harden/modernize, frameworks, ship). Human-language → command table. Generated command block unchanged.

## 0.0.25 — 2026-08-20

- `distill` is the old-code optimize entry: fifth pass is the WS-11 ladder; crate candidates only recommend `/crate`. No `/optimize` or `/split`. Scene 51.

## 0.0.24 — 2026-08-20

- Split ladder in WS-11 (fn → mod → crate), not a new `/split` command. Clippy 100-line is a function signal; two invariants split a file; crate only via existing `crate` + WS-12. Scene 50.

## 0.0.23 — 2026-08-20

- Learn from xai-org/grok-build (edition 2024, resolver 2, rust-toolchain.toml, thiserror in libs, clippy disallowed-methods): WS-05/DEP-08 no longer treat resolver 2 or missing rust-version as debt; PR-03 requires a supervisor outside worker Drop; XP-05 bans std canonicalize on Windows; gate may use clippy disallowed-methods. Scene 49.

## 0.0.22 — 2026-08-20

- SIMP-08: `match` is not a fancier `if`. Use `if` for bools, `match` for mutually exclusive shapes, `let-else`/`?` to continue on one variant. Scene 48.

## 0.0.21 — 2026-08-20

- ERR-08: anyhow/thiserror are not a prerequisite for lean Rust. Prefer `Result` + `?`; handwritten enums when few variants; never add both crates for looks; never leak anyhow from a library API. craft/shape/D-2 aligned. Scene 47.

## 0.0.20 — 2026-08-20

- Commands are accelerators, not switches. Add `reference/engage.md` (not a command): when the skill is loaded in a Cargo project, auto-run triage on rustc and craft on implement/fix. Waiting for `/review` or dumping the command menu is a failure (scene 46).

## 0.0.19 — 2026-08-20

- Absorb actionbook/rust-skills meta-cognition *direction*, not their 31-skill tree: triage now requires HOW→WHY→WHAT trace and an `&`/`Arc`/`clone` fit table before any clone recommendation. Design questions (shape) start at domain and walk down. No invented compliance rules when the user did not name a domain.

## 0.0.18 — 2026-08-20

- Add `crate <module>`: three-way adversarial review (split / keep / dep-direction) of whether a module should become a crate. Default is recommend-only (CK-06); user must reply 拆 before any workspace move.
- Register CK-01..06, routing when the user asks to extract a crate, pressure scenario 45, and a shape hand-off when crate-split is unclear.

## 0.0.17 — 2026-08-20

- Champion edition 2024 only: WS-05/DEP-08 require `edition = "2024"`, `resolver = "3"`, MSRV ≥ 1.85. edition 2018/2021 is migration debt, not a supported baseline.
- `init` no longer asks edition preference. `modernize` treats old editions as first-class hits (`cargo fix --edition`). `doctor` marks edition < 2024 as DRIFT.

## 0.0.16 — 2026-08-20

- Align contested wording with official sources, not folklore: C-DEREF (OWN-04), Edition Guide RPIT + if-let temporary scope (triage/modernize), sqlx Pool defaults + `AS "col: Decimal"` (SX-02/09), anyhow/eyre equivalence (ERR-02).
- craft.md now names the authority list so a disagreement falls back to API Guidelines / Edition Guide / crate docs instead of skill prose.

## 0.0.15 — 2026-08-20

- Adversarial review: ordinary implement/fix paths skipped ownership discipline. Add `reference/craft.md` as a default overlay (not a command): four gates (ownership / illegal states / errors / tests) before writing Rust.
- Add OWN-01..05 (no clone-to-compile, borrow params, mem::take, no Deref newtypes, interior mutability is last resort). Review loads OWN when clone/`&String`/`impl Deref` is in scope.
- Triage: edition 2024 RPIT capture and `if let` temporary drop. Modernize: `#[expect]`, `io::Error::other`, `LazyCell`, precise capturing.
- Harden checklist item 6 for secrets/log redaction. Pressure scenes 25 and 44 require craft/OWN instead of reflex clone.
- SKILL description front-loads ownership/borrow/clone triggers; ordinary tasks must not bounce users to a command menu.

## 0.0.14 — 2026-08-20

- Add `sqlx [target]` from starred practice sources (Bulletproof Rust Web database layer + sqlx compile-time checking): pool capacity, `query!` / offline `.sqlx/`, parameterized SQL, short transactions, row/domain/response split, `NUMERIC`≠`f64`, migration ownership, N+1.
- Register SX-01..12, routing recommendation when `sqlx` evidence exists, pressure scenario 43, and the read-only/apply output contract.
- Lift `API-08` (parse, don't validate; wire/row/domain/response types) from Bulletproof domain modeling + rust-unofficial/patterns newtype idiom.
- `shape` now asks for private newtypes, typestate-vs-enum, and refuses hexagon scaffolding for single-handler CRUD (SIMP-01).
- `axum` AX-14..17: thin handlers, auth extractors, two-layer validation, outbound timeout/retry + tracked background tasks.

## 0.0.13 — 2026-08-17

- Add `process [target]` for multi-process shape selection and orchestration: process-vs-thread boundary (isolation/fault domains, not raw throughput), Command lifecycle (array args, env whitelist, kill_on_drop, wait timeouts), fork safety limits (async-signal-safe, multi-threaded fork deadlock), pre-fork pools, process-group shutdown, IPC shape selection, pipe deadlock, async subprocess discipline, and cross-platform semantics.
- Register the PR-01..12 local namespace, process routing entry and menu recommendation, pressure scenario 42, and the read-only/apply output contract for the new domain.

## 0.0.12 — 2026-08-16

- User-facing P0: `scripts/command-metadata.json` is the single source of truth for command facts (category / one-line summary / argument hint / trigger phrases); `gen-command-tables.py` generates the SKILL.md router table and README quick reference; add `argument-hint` to the skill frontmatter.
- Unify write authorization into one rule: evaluate commands always read-only; transform / domain / deliver commands inspect or plan by default and write only with `--apply` or an explicit fix request; setup / govern commands write only their declared files. Align modernize with the inspect-first default.
- De-jargon the README (categorized command table, plain-language triggers, one write rule); move architecture and rule governance to docs/DESIGN.md.
- sync-providers.py regenerates command tables before syncing; check-consistency.sh verifies table drift.
- Split the mixed domain category into 语言语义 (concurrency/async/serde) and 框架 (axum/tauri/seaorm), mirroring the skill's own overlay order; category-grouped argument-hint generated from metadata.
- Add a shared output contract (SKILL.md 输出契约): one-line plain-language verdict, scope line, body tables, verification, confidence, copy-paste next step, and an explicit nothing-modified close; align all reference output sections to it.
- Unify the contract pointer wording across all 24 references into one canonical seven-step chain (field-tested in ozon-pod: menu/review/harden outputs read like a colleague's plain-language report).

## 0.0.11 — 2026-08-16

- Add `docs [target]` for evidence-driven docs-home, authority, lifecycle, supersession, and link governance; keep `document` scoped to RUST.md.
- Make docs governance read-only by default, with explicit frozen write sets for index updates, moves, archives, and repository-wide inbound-link repairs.
- Add read/write pressure scenarios that protect dirty documents, historical evidence, human index content, and idempotent moves.

## 0.0.10 — 2026-08-16

- Document is the single RUST.md projection flow; init reuses it after applying and validating the actual baseline delta.
- Split managed state into recomputed projection sections and stable-key ledgers; merge from the latest pre-write state and preserve other ledgers, unknown managed sections, and human content.
- Remove the hard-coded spec-version cache from init; read the current SKILL frontmatter version when projecting project state.
- Make Cargo discovery lock-safe, keep init out of source files, and make DEP-07 follow artifact needs and project policy instead of requiring every library lock.
- Strengthen init/document pressure scenarios and add cross-command, lock-policy, and marker-migration scenarios 37–39.

## 0.0.9 — 2026-08-16

- Review: four-way scope counts; upgrade-path checks for SQL/cache/metrics renames.
- Audit security: completion criteria, secrets scan columns, bcrypt coexistence, trusted-proxy topology gaps.
- Concurrency: Arc≠contention; AS shutdown side-notes do not veto CC.
- Xplat: service facet gating; Linux-only CI example; scene 36; XP-06 Windows-triggered.
- Bench: dirty tree / no-before stays read-only; reuse existing perf harnesses.
- From 5-way ai-gateway regression (review/audit security/concurrency/xplat/bench).

## 0.0.8 — 2026-08-16

- Slim/distill/gate: clarify read-only vs write paths; slim refuses work without timings and names BUILD-01 rejection in output.
- Doctor: explicit spec-version DRIFT row, empty-review STALE, ratchet N-A without baseline file, echo bypass crates; scene 35.
- Pin-root: cargo alias cannot use `--manifest-path`; prefer `cd` or `cargo run -p`.
- From 5-way ai-gateway regression (slim/doctor/gate/distill/serde).

## 0.0.7 — 2026-08-16

- Harden: default read-only checklist output; write only with explicit 修/改; inline AS-04 abort failure line.
- Ship (service): soften SH-01/05/06 dogmatism; no-target defaults to facets main artifact; add pressure scenario 34.
- Pin project root with `--manifest-path` / `cd` first; `cargo -C` only when supported.
- Scene 16 labeled desktop-only; scene 21 aligned with harden write gate.

## 0.0.6 — 2026-08-16

- Harden shutdown checklist accepts CancellationToken or proven equivalents (align with AS-04).
- ASYNC-06 names total timeout; AS-04 tells reviewers to search watch/TaskTracker before CT.
- Modernize: target forms are non-hits; bypass crates stay excluded even in the git change set; dead deps in unedited Cargo.toml stay unauthorized until expand is confirmed.
- Pressure scenarios 32–33 updated from 0.0.5 ai-gateway regression.

## 0.0.5 — 2026-08-16

- Align ASYNC-06 with AS-04/AX-06: unified cancel signal may be CancellationToken or a proven equivalent.
- Clarify AS-04: abort after cooperative shutdown is a fallback, not an automatic failure.
- Tighten modernize: “current changes” means the git change set; unauthorized full-repo peeks must be labeled; dead deps are a separate delete-dep row; echo excluded non-member crates.
- From 0.0.4 regression on ai-gateway: mixed-router TimeoutLayer guidance, serde adjacency hard example + passthrough SE-05 exception, and 主目标｜邻接证据 output columns.

## 0.0.4 — 2026-08-16

- Pin every cargo/git command to the user project root (`-C` / `--manifest-path`); never treat the skill repo as the target.
- Allow minimal adjacency evidence for overlays while keeping write scope frozen; mark adjacency explicitly.
- Accept equivalent shutdown signals for AS-04/AX-06; carve SSE/streaming exceptions out of whole-router TimeoutLayer (AX-04).
- Clarify modernize expansion asks, dead `once_cell` dependency cleanup, and non-member crate defaults.
- Add pressure scenarios for cross-repo roots, streaming timeouts, equivalent shutdown, and modernize ask-before-expand.

## 0.0.3 — 2026-08-16

- Unify `--record` as a managed-RUST.md flag for any reference that declares it.
- Align no-RUST.md routing to `document` for non-empty projects and `init` for empty/new ones.
- Make review load touched rule domains by default; full-spec load only on explicit request.
- Fix `slim` target scoping, doctor script availability, capture domain list, and audit FFI-07..09 coverage.
- Remove ghost “三件套” / protocol `0.7` wording; reorder SE/XP checklist IDs; add explicit distill pressure scenario.

## 0.0.2 — 2026-08-16

- Rebuild the entry skill as a thin action router with explicit read/write semantics and a shared completion contract.
- Require applicability and code evidence before citing a rule; stop treating project conventions as generic violations.
- Replace arbitrary layout, line-count, dependency-feature, tool, and xtask mandates with conditional guidance.
- Preserve existing workspace structure and gate tooling by default; migrate only for demonstrated benefit and explicit approval.
- Add adversarial scenarios for ordinary edits, established project conventions, default features, and conceptual questions.
- Strengthen consistency checks for reference purpose, pressure-scenario schema, and undefined routing operations.

## 0.0.1 — 2026-08-16

- Start plugin and spec versions together at 0.0.1.
- Ship one skill source to the supported harness set via `scripts/sync-providers.py`. Excludes Gemini, GitHub Copilot, Rovo Dev, and Mistral Vibe.
- Use stable namespaced commands and document `/rust-skills:review` without colliding with the built-in `/review`.
- Keep installed plugin packages read-only; capture lessons in a project-local outbox and require explicit maintainer promotion.
- Make review/audit/doctor read-only by default and define deterministic target resolution.
- Reject placeholder gates, preserve existing Git hooks, and avoid mutating user Git state or shared build caches.
- Correct CString pointer-lifetime, Windows file-sharing, Cargo profile override, Rust 2024 `static mut`, and Tauri async examples.
- Add isolated pressure coverage for every command and a repository consistency checker.
