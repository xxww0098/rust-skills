# kernel/swarm — 命令级只读编排

本文件**不是命令**。有并行只读 agent 时，按下面「开」表扇出；没有就串行。机械 crate 图只跑一次 `inspect_project.py`。子 agent **只读**：不改文件、不 `cargo update`、不 sudo。写入只在主会话、扇出合并之后，按 [write.md](write.md)。

两份 crate 图 = 本轮失败。已有本轮 ProjectSnapshot → 不再为同一范围重开 A 车道。

## 总闸

同时满足才开：

1. 本命令在「开」表。
2. 范围不是单文件（目录 / crate / 无 target 的 git 改动 / workspace）。
3. 宿主有并行只读 agent。

永远禁止：`craft` `triage` `shape` `capture` `init`；单文件 `review`；贴 rustc；火焰图「改一帧→同命令复测」（必须串行）。

## 开（命令 → 车道）

主会话先 inspect 一次，再按行开 **2–4** 条；缺证据的车道不开。子结果是证据条（path / kind / provenance / confidence），合并进同一份快照。

| 命令 | 车道（只读） | 不要 |
|---|---|---|
| `document` | 测试布局与孤儿 · 风险 signals · 依赖/lock | 手绘 crate 图；投影节手写 |
| `review` | 调用方/`#[cfg]`/生成入口 · 触达域规则 · CI/清单邻接 | 扩到未冻结文件；`--apply` |
| `doctor` | 技能仓一致性脚本 · 快照 vs RUST.md · toolchain/edition | 修 DRIFT |
| `crate` | 赞成（边界/复用） · 反对（过早拆） · 依赖方向 | 改 workspace |
| `stack` | 产物/Facets · 活栈 · 死亡线 | `cargo add` |
| `audit` | 按域：unsafe 清单 · deps/deny · tests 孤儿 · async 锁 | 多域混成一张表先扇出再分域输出 |
| `harden` | 错误路径 · 入站边界 · 观测/停机 | 扩到旁路 crate |
| `slim` | `slim/cargo` 指纹 · `slim/test` 证明集 · `slim/tooling` owner · `slim/hygiene` 四层 | 各跑一遍 metadata；清共享 target；把死码当文件删 |
| `distill` | 死码/未用 · 仪式/`clone` · 结构梯子 | 改 Cargo.toml |
| `gate` | CI 现状 · clippy 基线 · deny/hooks | 覆盖用户 hook；G4 塞进每次 push |
| `modernize` | edition/MSRV · 过时 API 清单 | 无授权升 edition |
| `concurrency` | 锁跨 await · spawn 无归宿 · rayon/tokio 桥 | 先加 loom 全家桶 |
| `process` | `Command` 站点 · 信号/停机 · IPC/管道 | `wait_with_output` 收大输出 |
| `async` | spawn/JoinHandle · `select!` 取消 · 阻塞 IO | 把不该 async 的改成 async |
| `serde` | `Value`/入站 unwrap · enum 表示 · 版本字段 | 把领域类型直接上线 |
| `obs` | `init()` 站点 · span 名/字段基数 · 测试 subscriber | 库里再装一层 |
| `name` | 转换前缀 · getter/`get_` · 包名/`-rs`/workspace 成员 | 改行为；公开 API 或已发布包名未授权就改 |
| `axum` | 路由/错误所有权 · 中间件次序 · 测试 `app()` | 整目录读 `axum/` |
| `tauri` | capabilities · IPC/命令 · 窗口/托盘 | 整目录读 `tauri/` |
| `seaorm` | Loader/N+1/过取杠杆 · ActiveValue/嵌套save/upsert · 池/迁移/schema-sync | 顺手再加 sqlx |
| `sqlx` | `query!`/离线 · 池/事务 · row vs 领域 | 与 sea-orm 双栈 |
| `cli` | `Parser` 仅 bin · 退出码 · 补全 | 库里 `process::exit` |
| `ship` | 容器产线 · 签名/公证 · 交叉矩阵 | 把 xwin NSIS 当正式 Windows 包 |
| `xplat` | `cfg` 边界 · CI 矩阵 · 差异账本 | 未声明平台误杀 |
| `docs` | 首页/权威源 · 断链 · 生命周期 | 默认为写 |
| `bench` | 仅盘点：已有装置 · profiling profile 是否在 | 采集后的改帧循环（串行） |

`audit <domain>` 只开该域车道。`slim` 的 `/cargo` `/test` `/cargo tools` `/cargo hygiene` 是四条车道的 pin，不是新命令。

## 合并

`cargo-metadata` / inspect JSON 压过 `model`。冲突标 `provenance=model`，不得改 graphs。合并后再出 Finding / 体检表。

## 宿主

Grok Build：并行 `task`（`explore`，只读）→ `get_task_output`。提示词带：命令名、项目根、冻结 scope、inspect 摘要、本车道「不要」。Claude Task 等同。没有并行工具 → 跳过本文件。
