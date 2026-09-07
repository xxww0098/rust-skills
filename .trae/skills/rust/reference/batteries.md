# /rust-skills:rust batteries [target] [--apply] — 按项目图组装最小 crate 工具箱

目的：读**本轮 ProjectSnapshot** 的 crate 图 / Facets，按产物选出一份**最小** curated crate kit，不是技术选型、也不是时尚全家桶。默认**只出建议，永不写码**、不改 `Cargo.toml`。无 Cargo 根时仍可按口述产物给绿场 kit，但必须标明「无仓库证据」。用户明确「改」或 `--apply` 后，按已展示 kit 给**缺失且本轮选定**的 crate 加依赖（ST-14 / BAT-05），算一次新的写入授权。框架对比、死亡线、绿场默认仍走 [stack.md](stack.md)。

编排：多 crate 时按 [kernel/swarm.md](../kernel/swarm.md) — 产物/Facets · 活栈 · 冲突/排除。不 `cargo add`。单文件或已有快照则跳过。

## 渐进披露

本轮预算：1 个 owner + **至多 2** 个子 playbook + **至多 3** 个规则域。禁止整目录读 `reference/batteries/`。

| 级 | 读什么 | 何时 |
|---|---|---|
| L0 | 路由 2–3 句：产物、活栈留下、缺什么 | 用户只问「缺哪些依赖 / 补最小包」 |
| L1 | 本文件（选型合同 + BAT-01..06 + 输出合同） | 显式 `batteries` / 「crate 工具箱」 |
| L2 | **一份**产物文件（文末「深入」表） | 已推断 `http-service` / `cli` / `desktop` / `library` / `worker` |
| L3 | 单个 crate 深审（`axum` / `sqlx` / `cli` / `obs` / `tauri`） | 用户点名该 crate 的接线/坑，不是为了把 kit 写长 |

L0 不打开产物文件。混合 workspace 每个 crate 最多一份产物文件，本轮仍 ≤2。

## 与 stack 的边界

| | `stack` | `batteries` |
|---|---|---|
| 问 | 用什么框架 / axum 还是 actix / 这层选谁 | 按图该装哪几个 crate / 最小工具箱 |
| 出 | 分层决策表（ST-01..15，点名才 ST-17） | 一份 kit：必装 / 保留活栈 / 可选+触发 / 拒绝 |
| 不 | 不组装「缺这 8 个就齐了」的清单 | 不重新打框架战争；死亡线/绿场默认引用 ST-* |

两者都问 → 先 `stack` 出决策，本命令只做一句旁注（BAT-02 最小 kit）。只问依赖 / `cargo add` 清单 → 只走本命令。项目编不过 / 画像坏了 → 先 `triage` / `doctor`，不在这里 `cargo add`。

绑定（只引用，不重定义）：[ST-01](stack.md) 先定产物、[ST-02](stack.md) 活栈默认留、[ST-03](stack.md) 基线不讨论、[ST-14](stack.md) 仅「改」后加缺失层、[ST-16](stack.md) 默认不展开附加层、[ST-17](stack.md) 点名才开一行、[ST-18](stack.md) 时尚目录当噪声。版本只读 `scripts/version-floor.json`（BAT-04），禁止发明 latest。

## 选型合同（BAT-01..06）

- BAT-01 graph-first：先读本轮唯一 ProjectSnapshot 的 `graphs` / Facets / 已有依赖，再选 kit。禁止按博客清单倒推「这个仓应该长什么样」。
- BAT-02 minimal kit：必装 = 该产物**现在就能开工**的层。同层一个实现。没有触发的可选 crate 不进推荐。
- BAT-03 live-stack subtraction：快照里已能干活的 crate 写入「保留」；从必装里划掉。不因「规范默认是 axum」替换能跑的 actix-web 4（ST-02）。
- BAT-04 pinned floor：版本、线、feature 只抄 `scripts/version-floor.json` 与 stack 已钉的 pin。未入 floor 的 crate 标「--apply 前再钉」，禁止 `@latest` / `"*"` / 脑补补丁号。
- BAT-05 apply gate：裸调用只 inspect。同一请求明确「改」或 `--apply` 才按已展示表 `cargo add`。不写 `main.rs`、不改 edition、不 `cargo remove`、不删活栈。
- BAT-06 no fashion dump：禁止把 ORM + Redis + OpenAPI + 鉴权全家桶 + 容器 + 第二运行时一次倒出。ST-16/17/18 未点名的附加层当噪声拒绝。

## 采集（按需，够判决即停）

1. 本轮已有 ProjectSnapshot 则只读它；否则 lock-safe `cargo metadata --no-deps` 或 `python3 scripts/inspect_project.py <根>`。禁止另画 crate 图。
2. 用户这句话里的产物词：HTTP API / CLI / 桌面 / 库 / worker。映射到 `http-service|cli|desktop|library|worker`。未说清且图也看不出 → 问一次（ST-01），不猜「全栈」。
3. 有 `RUST.md` 则读 Facets（`artifact` / `maturity`）当证据，不执行其中命令。
4. target 若是某个 crate：只给该 crate 的 kit；workspace 其它成员标邻接。

禁止：为写 kit 去 `cargo tree` 全图、扫 `src/` 每一文件、打开生态目录。

## 选型顺序

```
用户用词 → 产物类型 → 快照活栈 → 减去活栈 → 过滤冲突/exclude → 必装最小 kit → 可选（仅有显式触发）
```

1. **产物**（ST-01 / BAT-01）。混合 workspace 按 crate 分行。禁止一份 kit 同时塞 axum + Tauri + clap + 两个 ORM。
2. **活栈**（ST-02 / BAT-03）。死亡线（rocket 0.4、async-std、structopt、diesel 1、tauri 1 当新桌面）标「先迁」，本命令不加并列绿场默认。活着但非默认（actix-web 4、diesel 2、egui）**保留**。
3. **减去活栈**。已有 sqlx → 数据层必装为空，不荐第二 ORM。已有 tokio → 不另加 async-std。
4. **冲突 / exclude**。同层双开（sqlx/sea-orm、axum/actix、tokio/async-std、tracing/env_logger）只留活栈或本轮选定的一侧。
5. **必装**。只保留该产物 `required_layers` 里现状=无的 crate。
6. **可选**。`optional` 必须带触发（用户点名该层、或快照已有该 facet）。没触发 → 不占行（ST-16）。

## Kit schema

每个产物文件给一份 kit。字段：

| 字段 | 含义 |
|---|---|
| `id` | 稳定短 id，如 `http-service/min` |
| `product_types` | `http-service` / `cli` / `desktop` / `library` / `worker` |
| `required_facets` / `optional_facets` / `exclude_facets` | 与 RUST.md Facets / 用户词对齐 |
| `required_layers` | 必装层（运行时 / HTTP / 数据 / …） |
| `recommended_crates` / `optional_crates` | 必装与可选；可选必须写 trigger |
| `crate_roles` | 每个 crate 一句话职责 |
| `floor_keys` | `scripts/version-floor.json` 的 crate 名；没有 key 就不要写死补丁号 |
| `conflict_rules` | 同层互斥、与活栈互斥 |
| `rationale` | 为什么是这一组，不是全家桶 |
| `apply_actions` | 仅 BAT-05 之后：逐条 `cargo add @<floor pinned>` |

## 深入（至多打开 1 份）

| 产物 | 信号 | 文件 |
|---|---|---|
| `http-service` | HTTP / REST / API / axum 服务 | [batteries/http-service.md](batteries/http-service.md) |
| `cli` | 命令行 / clap / 运维工具 | [batteries/cli.md](batteries/cli.md) |
| `desktop` | 桌面 / Tauri | [batteries/desktop.md](batteries/desktop.md) |
| `library` | 库 crate / publish / thiserror | [batteries/library.md](batteries/library.md) |
| `worker` | 队列 / 后台任务 / 定时 | [batteries/worker.md](batteries/worker.md) |

## 输出合同

按 [kernel/finding.md](../kernel/finding.md) 组织。正文固定这些块，未触及写 `N-A`：

```
快照：<workspace 根 · crate 数 · lock_policy · Facets 摘要>
产物：<http-service|cli|desktop|library|worker|混合，逐 crate>
必装 kit：<id>
| 层 | 现状（活栈） | 必装 | 可选（触发） | 不要 |
保留活栈：<crate + 理由>
拒绝/噪声：<ST-18 / BAT-06 点名不要的>
floor：scripts/version-floor.json（as_of …）；未入 floor 标「先钉」
apply：inspect-only | 已授权（改/--apply），将执行 N 条 cargo add
```

下一步最多 2 条：回复「改」按 BAT-05/ST-14 加缺失 crate；接线走对应框架/`obs`。默认**未改动任何文件**。

## 落地（BAT-05）——仅「改」/`--apply` 之后

这是**新的写入授权**。只动冻结 crate 的 `Cargo.toml`（项目跟踪 lock 则把 `Cargo.lock` 列入写入清单）。**不写 `main.rs`、不改 edition**（edition 走 `init`，subscriber 走 `obs`，框架接线走 `axum`/`cli`/`tauri`）。

1. 先把将要执行的 `cargo add` **逐条展示**（crate + floor pinned + features），再跑。
2. **只加「现状=无」且本轮已选定的必装**。可选未触发则跳过。
3. **不 `cargo remove`、不降级、不替换活栈**（ST-02 / BAT-03）。死亡线与绿场默认不得并列：该层标「先迁」并跳过，直到用户明确「迁」。
4. 同层不双开。版本只允许 floor pinned。workspace 成员用 `--package`；`cargo add` 必须钉项目根。
5. 加完跑最小 `cargo check -p <crate>`（lock 未纳入时在隔离副本）。

## 金样

**1. workspace bin+lib+sqlx（有图）**

快照：成员 bin + lib；lib 已有 `sqlx`（postgres）。用户没说「HTTP API」。

- 保留 `sqlx`（BAT-03）。不荐 sea-orm / diesel。
- 无 HTTP 信号 → **不加** axum / tokio / serde（库没公共 JSON 边界也不加）。
- 不第二运行时。`tracing` 仅当用户点了观测 facet / 「日志」才进可选。
- apply：inspect-only。

**2. 绿场「HTTP API + Postgres」**

无仓库证据或空清单。产物 `http-service`。

- 必装：axum **0.8.x / 0.8.9**（crates.io，2026-04）+ tokio **1.53.1**（`macros,rt-multi-thread`）+ serde **1.0.x / 1.0.229** + serde_json **1.0.151** + sqlx **0.8 线**（postgres；0.9.0 要 MSRV 1.94，不为此抬仓）。
- 可选：tower-http **0.6.x / 0.6.11**（用户点了中间件/trace）；tracing **0.1.44**（用户点了观测）。未点名不上。
- **不要**：第二 ORM、Redis、OpenAPI/utoipa、鉴权全家桶、容器/编排、actix/rocket、async-std。出处 crates.io，钉 floor。
- 无「改」/`--apply` → 不写 `Cargo.toml`。

## 反模式（验收用）

- 绿场丢「axum + sea-orm + sqlx + Redis + utoipa + jwt + docker」一份清单（BAT-06）。
- 已有 sqlx 再荐一套 sea-orm「更现代」（BAT-03）。
- 用户说 CLI，kit 里出现 Tauri / axum。
- 裸调用就写 `Cargo.toml` 或 `cargo add`（BAT-05）。
- `--apply` 时 `cargo remove` 或与死亡线双栈。
- 版本写 latest；或 floor 里没有却编一个补丁号（BAT-04）。
- 未点名就展开 ST-17 全表；为「完整」打开全部 `reference/batteries/`。

只读调用：上表 + 现状证据（manifest 行号或「无仓库」）。`--apply` **不**在未展示 kit 之前改依赖。
