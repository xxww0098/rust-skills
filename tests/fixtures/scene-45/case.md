# Scene 45: crate review of src/billing — single caller, ~400 lines.

Anti-pattern: create crates/billing and edit workspace because of line count.
Required: three-way table 赞成/反对/依赖方向, CK-04 keep-in-module, no Cargo.toml writes.
