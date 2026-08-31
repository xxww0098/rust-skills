# kernel/scope — 只决定看什么

本文件是范围协议。命令不得另写一套「默认扫全仓」规则。

## 钉根

- 用户给出路径则以该路径为准，否则 invocation cwd。
- 所有 `cargo`/`git`/`rg` 钉在该根：`--manifest-path <根>/Cargo.toml`、`git -C <根>`，或先 `cd`。`cargo -C` 仅在 toolchain 支持时用。
- `.cargo` alias（如 `cargo xtask`）不能被 `--manifest-path` 驱动：须 `cd` 到根再调 alias，或 `cargo run -p <包> --manifest-path <根>/Cargo.toml -- …`。
- 禁止扫到技能安装仓或其他邻居仓库后假装成功。输出回显解析出的项目根。

## 冻结

显式 target 优先；否则按下表。主目标内的修改/结论必须落在冻结清单。为理解边界可读最小邻接（组合根、上游 DTO、共享 infra），输出分栏 **主目标｜邻接证据｜已排除**。邻接默认不可写。歧义会改变结果时问一次。

| 命令 | 无 target | 有 target |
|---|---|---|
| `review` | 已跟踪差异（暂存+未暂存）+ 未跟踪 | 该路径完整清单；全仓仅用户显式要求 |
| `harden` `modernize` `distill` `slim` `concurrency` `process` `async` 与框架命令 | 优先当前改动；要扩全仓先问（用户已说全仓除外） | 写入限于该路径 |
| `ship` `xplat` | RUST.md facets 指向的主产物及相关 CI/Dockerfile/conf；旁路 crate 默认排除 | 该路径 |
| `init` `document` `gate` `doctor` | Cargo workspace 根 | 根 |
| `stack` | 同根 + 用户口述产物 | 该 crate 的 manifest/facets |
| `bench` `crate` | 必须有明确 target | 该模块/crate |
| `docs` | 项目根 `docs/` | 该 docs 路径；入口文档与入链只作邻接 |

## 邻接与排除

- 相关时纳入：Cargo.toml / Cargo.lock、build.rs、rust-toolchain*、`.cargo`、CI、迁移、框架配置。不能只过滤 `.rs`。
- 旁路 crate（未列入 workspace members 的 scripts/tools）默认不进范围——即使出现在 git 改动集——除非用户点名。输出须回显已排除路径。
- facets 按 **当前 crate**：`artifact=lib|service|cli|desktop`，`maturity=prototype|production`。禁止用仓库级标签覆盖所有成员。
