## GATE 门禁
- GATE-01[S] 本地与 CI 应复用同一组检查入口；沿用项目已有脚本/任务系统，只有复杂度值得时才新增 `cargo xtask gate`。
- GATE-02[M] 门禁覆盖不得静默减弱；删除过时检查或放宽阈值须显式记录理由、影响与补偿证据。
- GATE-03[S] 棘轮基线文件入库，变更走评审。
- 阶梯：G1 pre-commit ≤6s（fmt+文件系统检查）→ G2 pre-push ≤3min（xtask 全量+clippy+单测）→ G3 CI 阻塞（+deny+MSRV+doc）→ G4 每夜非阻塞（Miri/loom/powerset/semver-checks/bench）。
- 候选门禁集：no_orphan_modules（第一优先）、no_raw_path_deps、no_wildcard_opt_level、tests_layout、crate/module_direction、internal_doctest_off、internal_publish_false、no_test_code_in_lib、no_silent_test_skip、lints_inherited、lint_ratchet。只有实现、失败 fixture 与实跑证据齐全的检查才可注册。
