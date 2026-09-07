# CLI kit

目的：给产物 `cli` 一份最小 crate 工具箱。先读 [batteries.md](../batteries.md)；本文件只填 kit。版本只取 floor。

```
id: cli/min
product_types: cli
required_facets: artifact=cli · 用户词含命令行/clap/子命令
optional_facets: 诊断日志 · 出站 HTTP
exclude_facets: 把库 crate 改成 CLI · 桌面壳
required_layers: 参数解析 · 应用错误
recommended_crates: clap（derive）· anyhow
optional_crates: tracing（用户要诊断日志，不是给人看的 stdout）· ureq（同步出站且无 tokio）· reqwest（已有 tokio 的异步 CLI）
crate_roles:
  clap — 只在 bin parse（ST-06 / CL）
  anyhow — 应用侧错误；已有 eyre 则留
  tracing — 诊断，不替代用户可见进度/帮助
  ureq / reqwest — 点名出站 HTTP 才加；不同时双开（ST-17）
floor_keys: clap · reqwest
conflict_rules: 已有 clap 3 标升级、不加第二套；structopt 先迁再加 clap；库成员禁 process::exit
rationale: 能 parse 参数并回报错。TUI/补全/配置全家桶未点名不上（BAT-06）
apply_actions: 现状=无才 cargo add clap@floor --features derive；不写 main.rs
```

用户说 CLI 时不要打开 http-service / desktop。
