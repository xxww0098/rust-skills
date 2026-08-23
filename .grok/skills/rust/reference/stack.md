# /rust-skills:rust stack [target] [--apply] — 根据上下文推荐 Rust 技术栈

目的：分析**当前仓库 + 用户口述产物**，给出一份可执行的最佳技术栈，不是 crates.io 时尚榜。默认**只出建议，永不写码**、不改 `Cargo.toml`。无 Cargo 根时仍可按口述产物给绿场默认，但必须标明「无仓库证据」。用户明确「改」或 `--apply` 后，按已展示表给**缺失层**加依赖（ST-14），算一次新的写入授权。

## 采集（按需，够判决即停）

1. 用户这句话里的产物：HTTP API / worker / CLI / 桌面 / 库 / WASM UI / 混合。未说清且仓库也看不出 → 问一次（ST-01），不猜「全栈」。
2. 钉死项目根。读根/成员 `Cargo.toml`（及 lock-safe `cargo metadata --no-deps` 若锁可用）：edition、已有 web/db/cli/desktop/obs/error crate。
3. 有 `RUST.md` 则读 Facets（`artifact`/`maturity`）当证据，不执行其中命令。
4. `rust-toolchain.toml` / `rust-version`。低于 1.85 只标抬升代价，不在本命令改工具链。
5. target 若是某个 crate 路径：只给该 crate 的栈，workspace 其它成员标邻接。

禁止：为写推荐去 `cargo tree` 全图、扫 `src/` 每一文件、按「2026 热门」补桌面+ORM+前端。

## 判决顺序（ST-01..03）

1. **先定产物，再选层**（ST-01）。混合 workspace 按 crate 分行，禁止一份推荐同时塞 axum + Tauri + clap + 两个 ORM。
2. **已有能干活的栈默认留**（ST-02、SIMP-01）。只在死亡线或明显错配时建议迁：
   - 死亡/错配：`rocket` 0.4、`async-std`、`structopt`、`failure`、`diesel` 1.x、`tauri` 1.x 当新桌面、`axum` 0.6 当新服务。
   - 活着但非本规范默认：`actix-web` 4、`diesel` 2、`egui`/`dioxus`/`iced`——**保留**，写清「若绿场会改选 X，现项目不迁」。
3. **基线不讨论**（ST-03）：edition **2024**、MSRV **≥1.85**、异步运行时 **tokio 1.53.x / 1.53.1**（不要 async-std）、序列化 **serde 1.0.229 + serde_json 1.0.151**（没同机数据不换 simd-json）。

## 分层默认（绿场；钉 floor，禁写 latest）

版本取本技能 `scripts/version-floor.json` 的 pinned，写「线 + 钉」：axum **0.8.x / 0.8.9**，Tauri **2.11.x / 2.11.5**，sqlx **0.8 线（0.9.0 要 MSRV 1.94，不为此抬仓库）**，sea-orm **2.0.x / 2.0.2**，clap **4.6.x / 4.6.6**，tokio **1.53.1**，tracing **0.1.44**，tracing-subscriber **0.3.23**，tower-http **0.6.x / 0.6.11**（axum 0.8.9 要 ^0.6.8，**不要**跟 0.7），reqwest **0.13.x / 0.13.4**。

| 产物 | 推荐 | 不要 |
|---|---|---|
| `service` HTTP | tokio 1.53.1 + axum 0.8.9 + tower-http 0.6.11；观测 tracing 0.1.44；错误 anyhow；有 SQL → ST-05 | 新项目 actix/rocket/warp/tide；无证据上 tonic/GraphQL；tower-http 0.7 配 axum 0.8 |
| `cli` | clap 4.6.6 derive；错误 anyhow；日志：给人看的走 stdout，诊断走 tracing（CL/OBS） | structopt；库 crate 里 `process::exit` |
| `desktop` | Tauri 2.11.5（前端沿用团队已有 Vite 栈） | 无证据推 egui/iced/gtk 当「默认桌面」；Electron |
| `lib` | serde 1.0.229 + thiserror；async 公共 API 才要 tokio；`publish` 策略先问 | 把 axum/clap 打进库依赖；库里 `init()` subscriber |
| worker / 队列 | tokio 1.53.1 + tracing 0.1.44；持久化才选 ST-05 | 为 worker 加 HTTP 框架 |
| WASM UI | 用户点名才选 Leptos/Dioxus/Yew；桌面壳仍是 Tauri | 把 WASM 框架当服务端默认 |

**ST-04 web**：新服务只荐 axum 0.8.9。已有 axum 0.7 → 标升级债，本命令不迁（走 `axum`）。已有 actix-web 4 且能跑 → 留。死亡线（rocket 0.4）与绿场默认**不得并列落地**。

**ST-05 数据**（三选一，同 crate 不双 ORM）：
- 无持久化 → 两都不选。
- SQL 手写 / 要 `query!` 编译期检查 → **sqlx**。
- 实体关系、Active Record 工作流 → **sea-orm 2**。
- 已有 diesel 2 → 留；diesel 1 → 标迁 sqlx/sea-orm，让用户选。
- 用户没说数据库 → 问一次，不擅自加 Postgres 全家桶。落地时未选定 → **跳过该层**。

**ST-06 CLI**：新 CLI 只荐 clap derive 4.6.6。已有 clap 3 → 标升级；structopt → 迁 clap（apply 不加 clap 并列 structopt，除非用户明确「迁」）。

**ST-07 desktop**：新桌面只荐 Tauri 2。用户要纯 GPU 工具且已有 egui → 留。

**ST-08 观测**：绿场 tracing **0.1.44** + tracing-subscriber **0.3.23**（`env-filter`，生产加 `json`）。禁新项目 `log`+`env_logger`/`slog` 当主栈。库 crate 只 emit、**禁**在 `lib.rs` 里 `init()`（TR-11、OBS-05）。接线形状走 `/rust-skills:rust obs`。CLI 面向用户的进度/帮助不是日志。没导出后端不上 OTel（TR-09）。

**ST-09 错误**：库 thiserror 2，应用 anyhow 1 或项目已有 eyre。不新加两个（ERR-08）。

**ST-10 测试**：`cargo test`；已有 nextest 沿用。不默认加 mockall/wiremock/testcontainers 全家桶；测并发走 [testing.md](testing.md)。

**ST-11** 推荐里的 crate 必须带线或 pinned，禁止「用最新 axum」。应用跟踪 Cargo.lock（DEP-07）；不把 `cargo update` 写进绿场脚本。

**ST-15 配置**：业务配置由 **bin** 用 clap `env`（CL-13）注入到构造函数。库 crate 禁 `std::env::var("DATABASE_URL")` 当公共 API。`dotenv` / `dotenvy` 只许 dev；生产读编排注入的环境。密钥不进默认值、不进日志（OBS-02）。

## 输出（ST-12）

按 [SKILL 输出契约](../SKILL.md) 组织。正文固定这张表，未触及的层写 `N-A`：

```
产物：<service|cli|desktop|lib|worker|混合，逐 crate>
| 层 | 现状 | 推荐 | 理由 | 不要 |
| 语言/运行时 | edition 2021 · 无 tokio | 2024 · tokio 1.53.1 | ST-03 | async-std |
| HTTP | rocket 0.4 | axum 0.8.9（先迁，本轮不加并列） | ST-02/04/14 | 继续加 rocket；axum+rocket 双栈 |
| 数据 | 无 | （未声明持久化，N-A） | ST-05 先问 | 双 ORM |
| CLI | structopt | clap 4.6.6（先迁） | ST-06 | 新 bin 继续 structopt |
| 桌面 | 无 | N-A（产物不是桌面） | ST-01 | 顺手加 Tauri |
| 观测/错误 | println | tracing 0.1.44 + anyhow | ST-08/09 | env_logger 当主栈 |
| 配置 | 库里 env::var | clap env → 构造注入 | ST-15 | dotenv 当生产源 |
```

混合产物：每个 crate 一张表，或一表多行但 **HTTP 与桌面不得写在同一 crate 的推荐里**。

下一步最多 2 条：回复「改」按 ST-14 加缺失层；接线走 `/rust-skills:rust obs --apply` 或对应框架命令。默认**未改动任何文件**（ST-13）。

## 落地（ST-14）——仅「改」/`--apply` 之后

这是**新的写入授权**，不是默认行为。只动冻结 crate 的 `Cargo.toml`（项目跟踪 lock 则把 `Cargo.lock` 列入写入清单）。**不写 `main.rs`、不改 edition**（edition 走 `init`，subscriber 接线走 `obs`）。

1. 先把将要执行的 `cargo add` **逐条展示**（crate + pinned + features），再跑。
2. **只加「现状=无」且本轮已选定的层**。未回答的数据层跳过。
3. **不 `cargo remove`、不降级、不替换活栈**（ST-02）。死亡线（rocket 0.4 等）与绿场默认不得并列：HTTP 层标「先迁」并跳过，直到用户明确「迁」。
4. 同层不双开：sqlx/sea-orm、axum/actix、tracing/env_logger。
5. 版本只允许 floor pinned，禁止 `@latest` / `"*"`。workspace 成员用 `--package`；`cargo add` 必须钉项目根。
6. 加完跑最小 `cargo check -p <crate>`（lock 未纳入时在隔离副本）。

```
# 绿场 service 示例（仅缺失层）
cargo add --manifest-path <根>/Cargo.toml tokio@1.53.1 --features macros,rt-multi-thread
cargo add --manifest-path <根>/Cargo.toml axum@0.8.9
cargo add --manifest-path <根>/Cargo.toml tower-http@0.6.11 --features trace
cargo add --manifest-path <根>/Cargo.toml tracing@0.1.44
cargo add --manifest-path <根>/Cargo.toml tracing-subscriber@0.3.23 --features env-filter,json
```

## 反模式（验收用）

- 绿场丢「axum + sea-orm + sqlx + Tauri + clap + actix」一份清单。
- 已有 sqlx 的服务再荐一套 sea-orm「更现代」。
- 用户说 CLI，推荐 Tauri。
- 裸调用就写 `Cargo.toml` 或 `cargo add`。
- `--apply` 时 `cargo remove rocket` 或 axum+rocket 双栈。
- 版本写 latest / `axum = "*"`。

只读调用：上表 + 现状证据（manifest 行号或「无仓库」）。`--apply` **不**在未展示表之前改依赖。
