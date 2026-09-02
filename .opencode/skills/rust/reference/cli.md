# /rust-skills:rust cli [target] — clap CLI 边界

目的：在有 `clap` 依赖、`artifact=cli`、或用户问「子命令 / 补全 / 环境变量 / 退出码」时审查或实现命令行入口。现行稳定线 **clap 4.6.x**（crates.io 4.6.6，2026-08）。3.x builder 是迁移债务。本清单是 API/ERR/OBS/SIMP 的 CLI 特化；库代码走 [craft.md](craft.md)，日志走 [obs.md](obs.md)。裸调用只体检。选型（clap vs structopt/argh）走 [stack.md](stack.md) ST-06；本文件只管接线。
不要读：Cargo.toml 与当前改动都没有 clap/`fn main` CLI 证据、且用户没问命令行时停。

编排：多文件时按 [kernel/swarm.md](../kernel/swarm.md) — Parser 仅 bin · 退出码 · 补全。 单文件或已有快照则跳过。

## CL 检查单（体检输出：位置｜编号｜问题｜修复）

**入口形状**

- CL-01 新 CLI 用 `#[derive(Parser)]`，不要手写 `Command::new` 长链。解析只发生在 binary crate；库 crate 禁依赖 clap、禁 `std::process::exit`（ERR-01：库返回 `Result`，bin 映射退出码）。
- CL-02 features 显式：`derive` 必开；读环境加 `env`；版本来自 Cargo.toml 加 `cargo`；补全另加 `clap_complete`，不要手写 bash/zsh/fish 脚本。
- CL-03 `#[command(name, version, about, arg_required_else_help = true)]`。裸调用无参数应打印帮助而非静默成功。

```rust
#[derive(Parser)]
#[command(name = "tool", version, about, arg_required_else_help = true)]
struct Cli {
    #[command(subcommand)]
    cmd: Commands,
}
```

**类型即契约**

- CL-04 `T` 是必填；`Option<T>` 是可缺；`default_value` / `default_value_t` 会强制 `required(false)`。禁止 `Option<T>` 再加 `default_value_t`（永远不是 `None`）。`Vec<T>` 用 `default_values_t`；「出现过但没值」才用 `Option<Option<T>>` + `num_args(0..=1)`。
- CL-05 封闭集合 `#[derive(ValueEnum)]`，不要 `String` 再手写 match。路径用 `PathBuf` + 默认 `value_parser`，不要 `String` 当路径。
- CL-06 子命令是 enum + `#[derive(Subcommand)]`。字段类型 `T` = 必选子命令（隐含 `subcommand_required` + `arg_required_else_help`）；`Option<T>` = 可缺。共享选项抽 `#[derive(Args)]` 再 `#[command(flatten)]`，不要复制粘贴。
- CL-07 `#[arg(env)]` 要 `env` feature；默认环境变量名是字段的 `SCREAMING_SNAKE_CASE`。`rename_all_env` 与 `rename_all`（默认 kebab-case）分开设。密钥可以 `env`，禁止 `default_value` 写进帮助文本。

**互斥、颜色、测试**

- CL-08 互斥用 `conflicts_with` / `required_unless_present`，不要事后 `if` 报错。全局选项 `global = true`，子命令里读 `from_global`。
- CL-09 颜色默认 Auto；CI/`NO_COLOR` 必须能关掉。不要无条件 `color = Always`。
- CL-10 退出码：成功 0，用户错（参数/缺文件）2 或 clap 默认，业务失败 1。`main` 返回 `ExitCode` 或 `anyhow::Result` 在 bin 里转；`println!` 是用户接口（OBS-01），诊断走 stderr / tracing，且 **只在 bin `main` 装一次 subscriber**（TR-01/11）。成功路径不要打 INFO 刷屏。
- CL-11 补全：`clap_complete` 生成到 `completions/` 并在 CI 核对漂移，或提供 `complete` 子命令运行时吐。手写补全脚本是债务。
- CL-12 测试用 `trycmd` 或 `clap` 的 `Command::debug_assert()` + `try_parse_from`。改帮助文本/默认值必须有快照或断言；不要只 `cargo run -- --help` 人工看。
- CL-13 生产配置走 clap `#[arg(env)]`（要 `env` feature），由 bin 注入到构造函数。库 crate 禁 `std::env::var("DATABASE_URL")` 当公共 API。`dotenv`/`dotenvy` 只许 dev；生产读编排注入的环境。密钥可以 `env`，禁止 `default_value` 写进帮助（同 CL-07）。

**Tauri 例外**：桌面 app 几个开关可用 `tauri-plugin-cli`；子命令/复杂校验仍在 `main` 里用 clap 解析完再进 `tauri::Builder`（见 [tauri/plugins.md](tauri/plugins.md)）。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表 + 按收益排序候选（CL 编号 + 全局规则号）。`--apply` 或明确“修/改/实现”时：再给实际改动。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
