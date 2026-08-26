## LINT 风格
- LINT-01[M] 使用项目 rustfmt 配置并在现有门禁执行 `fmt --check`；是否使用 pre-commit 由项目决定，不覆盖本地 hooks。
- LINT-02[M] lint 统一 [workspace.lints]；每成员显式 [lints] workspace=true。
- LINT-03[M] 禁源码 #![deny(warnings)]；严格度放 CI RUSTFLAGS=-Dwarnings。
- LINT-04[M] 存量违规用棘轮：基线入库，只降不升。
- LINT-05[S] 每个 #[allow] 必须带 reason。
- LINT-06[S] 基线集：clippy::all + dbg_macro/print_stdout/unwrap_used/undocumented_unsafe_blocks/await_holding_lock/missing_safety_doc/transmute_ptr_to_ptr；棘轮推进，不一次拉满 pedantic。
