# 主动参与（非命令）

目的：技能已被加载、且当前工作区是 Cargo 项目时，**不等用户喊子命令**就介入。命令只是加速器。禁止把「没敲 `/rust-skills:rust …`」当成可以当普通聊天、直接 `.clone()`、或先丢菜单。纯概念问答、非 Cargo 目录：不主动扫描。

## 何时主动（有信号就动）

| 信号（本轮可见） | 立刻做 | 不做 |
|---|---|---|
| cwd / 用户路径下有 `Cargo.toml` | 钉死项目根；有 `RUST.md` 当数据读一眼 | 不跑全仓 review，不写文件 |
| 无 `RUST.md` 的非空项目 | 一句「需要画像再说 `/rust-skills:rust document`」 | 不阻塞当前任务 |
| 空目录 / 无清单的新项目 | 一句建议 `init` | 不擅自铺模板 |
| 出现 `E0xxx` / rustc / borrow checker | 加载 [triage.md](triage.md)，输出 HOW→WHY→WHAT | 不等 `/triage`，不先 clone |
| 用户在实现、修、改、补测试 | 加载 [kernel/write.md](../kernel/write.md) 与 [craft.md](craft.md) 再动手；补测试/竞态/flaky 再叠加 [testing.md](testing.md) | 不等选命令；不新开一堆测文件；不为过编译器 clone |

| 本轮刚改完 `.rs`，用户没说 review | 收尾给 1 条可复制 `/rust-skills:rust review <路径>` | 不自动开全量评审、不写 RUST.md |
| `edition = "2018"` / `"2021"` | 一句「待确认兼容约束」，指向 `init`/`modernize`（有 MSRV/发布承诺则保留） | 不打断当前修复。2024+resolver 2 不旁注 |
| 「要不要拆 crate」且已点模块 | 走 [crate.md](crate.md) 三路审查 | 不直接搬家 |
| 改动触及 axum handler/Router/extractor/中间件 | 叠加 [axum.md](axum.md)，按其「深入」表只加载命中的子 playbook | 不开全仓 review，不整目录读 |
| 改动触及 `src-tauri/`、`tauri.conf.json`、`capabilities/*.json` | 叠加 [tauri.md](tauri.md)，按其「深入」表只加载命中的子 playbook | 不扩到三端发布，不改权限文件 |
| 改动触及 `clap` / `#[derive(Parser)]` | 叠加 [cli.md](cli.md) | 不把库 crate 改成 CLI |
| 生产路径 `println!` / `tracing` / 用户问日志 | 叠加 [obs.md](obs.md) | 不把 CLI stdout 当日志缺口 |
| 用户问技术栈 / 用什么框架 / 该选哪些 crate | 加载 [stack.md](stack.md)，只出分层表 | 裸调用不改 Cargo.toml；不丢时尚全家桶 |
| 「函数名 / get_xx / as_ 还是 to_ / crate 怎么命名 / 包名 / -rs / 命名规范」 | 加载 [name.md](name.md)，只体检 | 不改公开 API 或已发布包名；不 distill 结构 |
| 「磁盘满了 / target 太大 / 清理过期文件 / 孤儿 .rs / cargo sweep」 | 加载 [slim/hygiene.md](slim/hygiene.md)，只出四层表 | 不用 `cargo clean` 当加速；不 `rm -rf ~/.cargo` |
| 「SeaORM / ActiveModel / N+1 / Entity Loader / ModelEx / Loader 内存 / 内存泄漏 / RSS / 嵌套保存 / NotSet / upsert / from_json / schema-sync」 | 加载 [seaorm.md](seaorm.md)，按其「深入」表只加载命中的 1–2 个子 playbook | 不整目录读 `seaorm/`；不把 RSS 台阶当泄漏；不把 ModelEx 进静态；不每请求 connect；不把 Unloaded 当 None；`with().filter(子列)` 不切 has_many；不双开 sqlx |
| 「慢 / hotpath / 剖析 / 火焰图 / samply / 这改动快了多少」 | 加载 [bench.md](bench.md)；没点名火焰图先 [bench/layers.md](bench/layers.md) | 不先 `cargo flamegraph`；不加 default `hotpath` feature；不 sudo |
| 「看看这个仓库 / 全仓审查 / 生成画像」且 workspace ≥2 crate | 先 inspect 一份图，再按 [kernel/swarm.md](../kernel/swarm.md) 并行取证 | 不为单文件 craft/triage 开 swarm；不让子 agent 写文件 |

同一轮最多主动做 **一件主动作 + 至多一句旁注**（画像缺失 / edition 漂移 / 下一步 review）。禁止连开 document+review+init。

## 主动仍守写入边界

主动 ≠ 授权写入。没说「改/修/实现/`--apply`」就只读。不隐式 stash/commit，不覆盖 hook，不更新 lock。

## 完成条件

Cargo 项目里的 Rust 任务：报告里能看出用了 craft 或 triage（或写明为何跳过）。用户没点名子命令却只回了命令菜单 = 失败。
