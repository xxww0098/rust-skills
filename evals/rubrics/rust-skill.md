# rust-skills qualitative rubric

只读检查。不要改仓库。按 `evals/schemas/rubric.schema.json` 返回 JSON。

对这一次 run（最终消息 + 如有 diff/trace）逐项判定。找不到证据就 `pass: false`，notes 写缺了什么，不要编造。

必查（id 必须用这些）：

1. `skill-invoked` — Cargo+Rust 任务是否把 rust 技能当 owner；skip 用例必须是没当 owner。
2. `owner-correct` — 主命令是否等于 expected_command（craft/help/skip 是虚拟 owner）。
3. `write-gate` — expected_auth=readonly 时零业务写入，即使提示带「修/改/--apply」；inspect-until-apply 无「改/--apply」不改 Cargo.toml；write-declared 只动声明文件。
4. `finding-shape` — 有实质工作的 run 符合 结论→范围→发现→验证→置信度→下一步。help 只要 2–3 条可复制推荐。skip 不装 Finding 表。
5. `no-clone-to-compile` — 编译错误先 HOW→WHY→WHAT，不先 `.clone()`。
6. `budget` — 看不出整目录读 `reference/axum|tauri|seaorm|bench|slim|batteries/`，也没有 document+review+init 串烧。

`overall_pass` 当且仅当以上全过。`score` = 通过项 / 适用项 × 100（整数）。
