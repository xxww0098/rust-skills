# HTTP 服务 kit

目的：给产物 `http-service` 一份最小 crate 工具箱。先读 [batteries.md](../batteries.md) 的 BAT-01..06；本文件只填 kit，不重开选型。版本只取 `scripts/version-floor.json`。

```
id: http-service/min
product_types: http-service
required_facets: artifact=service · 用户词含 HTTP/API/REST
optional_facets: 观测/日志 · 中间件/CORS/trace · SQL/Postgres
exclude_facets: 桌面 · 纯库 publish · 无 HTTP 的 worker
required_layers: 运行时 · HTTP · 序列化；（用户说了 SQL 才）数据
recommended_crates: tokio · axum · serde · serde_json ·（SQL 触发）sqlx
optional_crates: tower-http（中间件/trace）· tracing（观测）
crate_roles:
  tokio — 异步运行时（ST-03）
  axum — HTTP 框架（ST-04）；已有 actix-web 4 则保留，不并列
  serde / serde_json — 入出站 JSON
  sqlx — 手写 SQL / query!（ST-05）；已有 sqlx 或 sea-orm 则本层空
  tower-http — 跟踪/CORS 等中间件，未点名不上
  tracing — 诊断日志，未点名不上（接线走 obs）
floor_keys: tokio · axum · serde · serde_json · sqlx · tower-http · tracing
conflict_rules: 不双开 HTTP 框架；不双开 ORM；不双开运行时；死亡线 rocket 0.4 先迁再加 axum
rationale: 能起一个 JSON API +（可选）Postgres。鉴权/OpenAPI/Redis/容器不是最小 kit（BAT-06）
apply_actions: 仅现状=无的必装层 cargo add @floor；可选未触发跳过
```

无 HTTP 信号的 workspace 即使有 bin+lib，也不打开本文件、不加 axum。
