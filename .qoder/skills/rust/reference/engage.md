# 主动参与（非命令）

目的：技能已加载、且当前工作区是 Cargo 项目时，用**一份** [ProjectSnapshot](../kernel/evidence.md) 做轻量纠正（规范项目），**不等用户喊子命令**。命令是加速器，不是开关。只处理 Cargo + Rust。主动 ≠ 写入授权。禁止把「没敲 `/rust-skills:rust …`」当成可以当普通聊天、直接 `.clone()`、或先丢菜单。纯概念问答、非 Cargo 目录：不主动扫描。

## 本轮一份快照

先按 [kernel/evidence.md](../kernel/evidence.md) 采（或复用）**一份** ProjectSnapshot。后续 craft / triage / 旁注都只读它。禁止为「规范一下」再扫一遍 crate 图，禁止连开 document+review+init。

同一轮最多 **一件主动作 + 至多一句旁注**。旁注不是第二份命令。功能做到一半时，基线/画像缺口只许旁注，不许抢主动作。

## 优先级（先高后低；命中即停）

**P0 — 立刻做，且这就是主动作**

| 信号 | 主动作 | 不做 |
|---|---|---|
| `E0xxx` / rustc / borrow checker | [triage.md](triage.md)，HOW→WHY→WHAT | 不等 `/triage`；不先 clone；不先 document |
| 用户说修 / 改 / 实现 / 补测试 | [craft.md](craft.md)；已授权才打开 [kernel/write.md](../kernel/write.md)。补测/竞态再叠加 [testing.md](testing.md) | 不等选命令；不新开一堆测文件；不为过编译器 clone |

功能或修复当前轮次 → **先 craft/triage**。其余卫生项降为旁注或下轮。

**P1 — 仅当本轮不是功能/修复，或用户点名**

| 信号 | 主动作 | 不做 |
|---|---|---|
| 本轮刚改完 `.rs`，用户没说 review | 一句可复制 `/rust-skills:rust review <路径>`（旁注也行） | 不自动开全量评审、不写 RUST.md |
| 用户问技术栈 / 用什么框架 / 选 axum 还是 actix | [stack.md](stack.md)，只出分层表 | 裸调用不改 Cargo.toml；不丢时尚全家桶 |
| 用户问缺哪些依赖 / 按图组装 crate / batteries | [batteries.md](batteries.md)，只出最小 kit | 无「改」/`--apply` 不写；无产物信号不猜全栈 |
| 空目录 / 无清单的新项目 | 一句建议 `init` | 不擅自铺模板、不自动 document+gate |

**P2 — 卫生；能旁注就旁注，不要抢主动作**

| 信号 | 可以做什么 | 不做 |
|---|---|---|
| 无 `RUST.md` 的非空项目 | 一句「需要画像再说 `/rust-skills:rust document`」 | 不阻塞当前任务；功能轮次只旁注 |
| 有画像、缺统一门禁，且用户在问 CI/提交检查 | 先 [doctor.md](doctor.md) 分类，再一句建议 `gate` | doctor 只读；不在本轮 `cargo add`；不替 gate 写 hook |
| workspace ≥2 crate **且** 用户给了产物信号（HTTP/CLI/桌面/库/worker） | 可指向 `batteries`（仍只 inspect） | 只看见多 crate 就推销工具箱；无产物信号不猜 |
| `edition = "2018"` / `"2021"` | 一句「待确认兼容约束」，指向 `init`/`modernize`（有 MSRV/发布承诺则保留） | 不打断当前修复。2024+resolver 2 不旁注、不标漂移 |

## 降级（有信号也不许当主动作）

这些可以记在心里或一句带过，**不得**变成本轮主命令：

- 只出现框架名 / `name` / `obs` / `bench` 关键词，没有「在改这个 / 这里坏了 / 要比快」的任务。
- 可选文档、画像、门禁——在功能/修复轮次里插队。
- 仅仅 edition ≠ 2024（没有用户要升、也没有正在 init）。
- 可选 crate 没钉版本（不是本轮要加的依赖）。
- 多框架菜单（「你是想 axum 还是 Tauri 还是 clap？」）——先定产物，或问一次，不摊开。

触及真实改动面时，框架/观测仍可**叠加**在 craft 上（axum handler → 叠 [axum.md](axum.md) 命中的子 playbook），那是覆盖层，不是第二件主动作。

## 何时仍要动（保留的窄信号）

| 信号 | 立刻做 | 不做 |
|---|---|---|
| cwd / 用户路径下有 `Cargo.toml` | 钉死项目根；有 `RUST.md` 当数据读一眼 | 不跑全仓 review，不写文件 |
| 「要不要拆 crate」且已点模块 | 走 [crate.md](crate.md) 三路审查 | 不直接搬家 |
| 「函数名 / get_xx / as_ 还是 to_ / crate 怎么命名」 | [name.md](name.md)，只体检 | 不改公开 API；不 distill 结构 |
| 「磁盘满了 / target 太大 / 清理过期文件 / 孤儿 .rs」 | [slim/hygiene.md](slim/hygiene.md)，只出四层表 | 不用 `cargo clean` 当加速；不跟 distill 混 |
| 「慢 / hotpath / 火焰图」且用户在问这段快了多少 | [bench.md](bench.md)；没点名火焰图先 [bench/layers.md](bench/layers.md) | 不先 `cargo flamegraph`；关键词「bench」单独出现不够 |
| 「看看这个仓库 / 全仓审查 / 生成画像」且 workspace ≥2 crate | 先 inspect 一份图，再按 [kernel/swarm.md](../kernel/swarm.md) 并行取证 | 不为单文件 craft/triage 开 swarm |

`slim` 管编译慢 / target / 磁盘 / 孤儿文件。`distill` 管过度抽象 / 删仪式。两件不同的事，禁止互相当别名。

## 主动仍守写入边界

主动 ≠ 授权写入。没说「改/修/实现/`--apply`」就只读。不隐式 stash/commit，不覆盖 hook，不更新 lock。`review`/`audit`/`triage`/`doctor` 永远只读。

## 前 / 后

**1. 功能轮次被卫生打断**

用户：「给 invoices 加上按状态筛选，改 `crates/app/src/invoice.rs`。」仓里没有 RUST.md，edition 2021。

- 前（啰嗦）：先 `document` 出画像，再 `init` 升 edition，再问要不要 `review`，再丢命令表。
- 后：主动作 = craft 改筛选。旁注一句「没有画像的话之后可以 `/rust-skills:rust document`」。不升 edition、不开 review、不 init。

**2. 编译错误先菜单**

用户：「这段报 E0382」+ `audit.push(record); ledger.push(record);`

- 前：只贴命令表让人选 `triage`/`review`；或先 document。
- 后：主动作 = triage（HOW→WHY→WHAT）。审计数据倾向 Arc。不写文件。不阻塞于 RUST.md。

**3. 刚改完就全仓审查**

用户：刚让你改完 `invoice.rs`，没说 review。

- 前：自动全仓 `review` + 写 RUST.md 快照 + 建议 `init`+`gate`。
- 后：主动作已结束（craft）。旁注一条可复制 `/rust-skills:rust review crates/app/src/invoice.rs`。不写文件。

**4. 多 crate 就推销全家桶**

用户：在改一个 workspace（bin+lib，lib 里有 sqlx），说「把金额解析写成纯函数」。

- 前：打开 stack 菜单，再 batteries 倒出 axum+tokio+sea-orm+tracing。
- 后：主动作 = craft。无 HTTP 信号不加 web kit。sqlx 保留。不旁注 edition、不 document。

## 完成条件

Cargo 项目里的 Rust 任务：报告里能看出用了 craft 或 triage（或写明为何跳过）。用户没点名子命令却只回了命令菜单 = 失败。一轮里执行了 document+review+init，或功能轮次把画像/门禁当主动作 = 失败。
