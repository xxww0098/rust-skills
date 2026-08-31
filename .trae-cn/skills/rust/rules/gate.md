## GATE 门禁
- GATE-01[S] 本地与 CI 应复用同一组检查入口；沿用项目已有脚本/任务系统，只有复杂度值得时才新增 `cargo xtask gate`。
- GATE-02[M] 门禁覆盖不得静默减弱；删除过时检查或放宽阈值须显式记录理由、影响与补偿证据。
- GATE-03[S] 棘轮基线文件入库，变更走评审。
- GATE-04[S] 已跟踪 lock 的应用：G3 CI 必须 `--locked`；禁流水线里的 `cargo update`（DEP-11）。yank 警告不触发 CI/Agent 的 update。G4 可选 `cargo +nightly -Zmin-publish-age` 验证解析冷却（DEP-13），**不**把 nightly 当默认构建工具链。CI/Agent 环境不得常驻 `CARGO_RESOLVER_INCOMPATIBLE_PUBLISH_AGE=allow`。
- GATE-05[S] G4 feature 矩阵用 `cargo hack check --feature-powerset --no-dev-deps`（[taiki-e/cargo-hack](https://github.com/taiki-e/cargo-hack)）；库有可选 feature 才加，不默认引入。`--each-feature` 不够（漏组合）。未采用不强迫。
- GATE-06[S] 静态分析阶梯不可把 G4 工具塞进每次 push。Miri 只跑有 `unsafe` 的 crate；Kani/形式化验证仅已采用才留；clippy pedantic 不当 `-D`。同层不双跑（LINT-07）。

- 阶梯：G1 pre-commit ≤6s（fmt+文件系统检查）→ G2 pre-push ≤3min（xtask 全量+clippy+单测）→ G3 CI 阻塞（+deny+MSRV+doc+`--locked`）→ G4 每夜非阻塞（Miri/loom/cargo-hack powerset/semver-checks/bench/可选 min-publish-age）。
- 候选门禁集：no_orphan_modules（第一优先）、no_raw_path_deps、no_wildcard_opt_level、tests_layout、crate/module_direction、internal_doctest_off、internal_publish_false、no_test_code_in_lib、no_silent_test_skip、lints_inherited、lint_ratchet。只有实现、失败 fixture 与实跑证据齐全的检查才可注册。
