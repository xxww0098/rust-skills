## LINT 风格
- LINT-01[M] 使用项目 rustfmt 配置并在现有门禁执行 `fmt --check`；是否使用 pre-commit 由项目决定，不覆盖本地 hooks。
- LINT-02[M] lint 统一 [workspace.lints]；每成员显式 [lints] workspace=true。
- LINT-03[M] 禁源码 #![deny(warnings)]；严格度放 CI RUSTFLAGS=-Dwarnings。
- LINT-04[M] 存量违规用棘轮：基线入库，只降不升。
- LINT-05[S] 每个 #[allow] 必须带 reason。
- LINT-06[S] 基线集：clippy::all + dbg_macro/print_stdout/unwrap_used/undocumented_unsafe_blocks/await_holding_lock/missing_safety_doc/transmute_ptr_to_ptr；棘轮推进，不一次拉满 pedantic。
- LINT-07[S] 静态分析按层叠加，禁止同层重复工具。rustc=类型；rustfmt=G1；clippy=G2；cargo-deny=G3（advisories+license+bans）。deny 已开 advisories 则不再跑 cargo-audit。G4 按证据：有 unsafe→Miri；发布 lib→semver-checks；可选 feature→cargo-hack；项目已用 Kani 才保留。rust-analyzer / cargo-geiger / Rudra / MIRAI / Prusti / Sonar 不是默认 CI。
- LINT-08[S] clippy/rustfmt 与 rustc **同工具链**：`rust-toolchain.toml` `components = ["clippy","rustfmt"]`。调用 `cargo clippy --all-targets`（有 lock 加 `--locked`）。`--all-features` 仅当 feature 可组合；互斥 feature 走 GATE-05。CI 用 `RUSTFLAGS=-Dwarnings` 或 `CARGO_BUILD_WARNINGS=deny`，禁止源码 `#![deny(warnings)]`（LINT-03）。项目策略进 `clippy.toml`（`msrv`、`disallowed-methods`），不靠一长串 `#[allow]`。

