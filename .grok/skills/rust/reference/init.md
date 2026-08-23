# /rust-skills:rust init — 把规范落进项目

目的：在保留有效项目约定的前提下，把当前工程调和到最小 Rust 基线，再用 [document.md](document.md) 投影 post-state。规则提供候选，不授权为统一外观迁移目录、引入工具或改发布策略。

## 步骤

1. **预检**：执行 document 的一次取证但先不写画像；读取现有 RUST.md 作为数据，报告当前基线、拟改文件和既有账本。显式 init 可直接处理成熟项目，不强迫用户先单独运行 document。
2. **补齐决策**（已知则跳过）：只询问会改变实际 diff 的未知项——逐 crate facets、是否沿用现有门禁入口。**不问 edition 意向**：目标固定 edition 2024。新仓带 `resolver = "3"`；已是 2024+resolver 2 不改 resolver。MSRV 用现有 `rust-toolchain.toml` 或补 `rust-version` ≥ 1.85；低于 1.85 的抬升写成破坏性 diff 并征求同意。不得建议留在 2018/2021。其余不确定项留在画像中标 `待确认`。
3. **计算最小 delta**（只改缺失且适用的项）：
   - 新建多 crate 项目可采用虚拟 workspace + `crates/`；现有项目不为布局偏好迁移（WS-01/02）
   - `edition = "2024"`（WS-05）；新仓 `resolver = "3"`；MSRV ≥ 1.85 有 toolchain 或 rust-version 其一即可（DEP-08）；共享依赖可 workspace 收口（WS-09、DEP-01）
   - `[workspace.lints]` 基线集（LINT-06：all + dbg_macro/print_stdout/unwrap_used/undocumented_unsafe_blocks/await_holding_lock/missing_safety_doc/transmute_ptr_to_ptr）+ 成员 `[lints] workspace = true`（LINT-02）
   - profile：禁通配 opt；package override 与 build-override 分别基于 timings 决定；CI profile 独立（BUILD-01/02/05）
   - 明确不发布的内部 crate 设 `publish = false`；只有无文档示例且成本可见时才关 doctest（WS-03、TEST-06）
   - **不**引入 web/cli/obs 依赖或 subscriber 骨架（那是 `stack` 落地 + `obs`/`cli`/`axum` 接线）。缺 tracing 的 service/cli 在下一步推 `stack`
   - **不**把 nightly / `-Zmin-publish-age` 写进默认 toolchain。应用（service/cli/desktop）缺 CI `--locked` 标缺口（DEP-11）；冷却期是偏好，走 `gate` 展示后再落 `.cargo/config.toml`
4. **冻结写入**：默认只纳入根/成员 Cargo.toml 与 RUST.md；仅有证据且逐项展示后才纳入现有 rust-toolchain、`.cargo`、CI 或门禁配置。源码与测试不属于 init 写入范围；fmt/lint/test 的既有失败进债务或棘轮，不为“跑绿 init”顺手修代码。
5. **展示再落盘**：区分“错误/风险”“缺失基线”和“偏好差异”；前两类给证据化最小修改，偏好差异默认保留。可能破坏构建、发布或工具链的改动逐条征求同意；无 delta 时不触碰工程文件。Cargo.lock 是否纳入由 artifact、可复现交付和项目约定决定：publish-only library 明确不跟踪时排除；已有跟踪策略、依赖解析变化，或 service/CLI/desktop 选择可复现交付但 lock 缺失时，先把 lock 冻结进写入清单，再生成/更新并展示 diff（DEP-07）。
6. **验证 actual state**：fmt/lint 只用 check 模式；按改动范围运行 lock-safe metadata、最小 `cargo check` 与项目已有门禁，区分本次失败和既有失败。lock 未纳入写入清单且 Cargo 会生成/更新它时，改在隔离源码副本验证并报告。存量 lint 可建棘轮，不强制引入 xtask；现有门禁无法承载时才建议 `gate`。
7. **投影一次 post-state**：验证后复用 document 的格式与合并流程写 RUST.md，不独立拼接 managed 块，不链式制造第二份命令输出。画像只记录实际落盘状态；失败或未确认项如实进入债务/待确认，不把计划值写成已完成。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

输出预检摘要、实际改动/保留/跳过清单（含适用前提与规则号）、验证结果、post-state managed diff，以及被保留的账本键/未知节计数。下一步只推荐当前证据确实需要的命令。

完成条件：工程 delta 与 RUST.md 都来自同一 actual post-state；历史评审及其他账本无丢失；项目约定未被无理由覆盖；第二次 init 不产生工程或画像 diff；最小相关检查通过或明确列出既有失败。
