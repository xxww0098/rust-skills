# 库 crate kit

目的：给产物 `library` 一份最小 crate 工具箱。先读 [batteries.md](../batteries.md)；本文件只填 kit。版本只取 floor。

```
id: library/min
product_types: library
required_facets: artifact=lib · 用户词含库/sdk/publish
optional_facets: 公共 JSON 边界 · 异步公共 API
exclude_facets: 把 axum/clap 打进 lib 依赖 · 库里 init() subscriber
required_layers: （有 JSON 边界才）序列化 · 库错误
recommended_crates: （JSON 触发）serde · thiserror
optional_crates: tokio（仅异步公共 API；feature 不要默认开 runtime）· serde_json（出站 JSON 才）
crate_roles:
  serde — 公共类型的序列化边界，不是每个 lib 的必装
  thiserror — 库错误；已有则留。不要再加一份 anyhow 当公共 API（ERR-08）
  tokio — 公共 Future 才要；不要为「以后可能 async」预加
floor_keys: serde · serde_json · tokio
conflict_rules: 禁 axum/clap/tracing-subscriber 进 lib 依赖；禁在 lib.rs init 日志
rationale: 库默认可以零额外依赖。有边界再加 serde/thiserror。不预装服务端栈（BAT-02/06）
apply_actions: 只加本轮有触发且现状=无的层；publish 策略先问，不改
```

workspace 里 lib 成员已有 sqlx 时：保留，不因「库要干净」删它，也不为此给 lib 再加 HTTP 框架。
