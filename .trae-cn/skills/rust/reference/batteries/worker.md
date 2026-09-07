# Worker kit

目的：给产物 `worker` 一份最小 crate 工具箱。先读 [batteries.md](../batteries.md)；本文件只填 kit。版本只取 floor。

```
id: worker/min
product_types: worker
required_facets: 用户词含队列/后台/定时/worker
optional_facets: 观测 · 持久化
exclude_facets: 为 worker 加 HTTP 框架 · 桌面壳
required_layers: 运行时 ·（点名观测才）日志
recommended_crates: tokio
optional_crates: tracing（观测）· sqlx 或 sea-orm（用户说了持久化，三选一，ST-05）
crate_roles:
  tokio — 异步运行时（ST-03）；已有则留
  tracing — 诊断；未点名不上
  sqlx / sea-orm — 有持久化才选一层；已有则本层空
floor_keys: tokio · tracing · sqlx
conflict_rules: 不加 axum/actix「顺便提供健康检查」；不双开 ORM；不双开运行时
rationale: worker 能跑任务 +（可选）写库。消息队列/Redis/HTTP 管理面未点名不上（BAT-06）
apply_actions: 现状=无才加 tokio@floor；HTTP 层 N-A
```

用户没说 worker / 队列 / 后台时不要打开本文件。
