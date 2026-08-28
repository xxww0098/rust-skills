# /rust-skills:rust axum [target] — axum 服务优化

目的：在冻结范围内审查或优化 axum 服务。现行稳定线 **0.8.x**（crates.io 0.8.9，2026-04）；0.7 仍按本清单审（差异处注释 `// axum 0.7`），0.6 及更早的 `axum::Server` 是迁移债务（改 `axum::serve(listener, app)`）。本清单是 ASYNC/OBS/PERF/SIMP/ERR/TEST 域的特化；`review`/`audit`/`harden` 有 axum 证据时加载相关节，再按文末「深入」表叠加 1–2 个子 playbook。组合根/超时/停机证据常在邻接 crate（如 `*-server`）：可读并标「邻接证据」，写入仍限冻结 target。
不要读：Cargo.toml 与当前改动都没有 `axum` 证据时停，不要凭「这是 web」加载。

## AX 检查单（体检输出：位置｜编号｜问题｜修复）

本文件是 owner：编号定义在这里。细节、代码与反例只在命中的 1–2 个子 playbook 里读，不要把 `reference/axum/` 整目录读进来。

**状态与共享（门）**

- AX-01 状态走 `State<Arc<AppState>>`，子状态用 `FromRef` 派生收窄；核心状态禁走 `Extension`（无编译期检查）。
- AX-02 池类型本身廉价 clone（sqlx `Pool`、`reqwest::Client` 内部已是 Arc）——禁止 `Arc<Pool>`/`Arc<Mutex<Pool>>` 双重包裹（SIMP-02）；Client 构建一次进 state，**严禁每请求 `Client::new()`**。
- AX-03 handler 内共享可变状态遵守 ASYNC-01/02：guard 不跨 await；热点计数用原子/分片，不用全局大锁。

```rust
// ✗ AX-02 每请求新建：TLS 握手 + 连接池全废
async fn fetch() -> Result<String, Error> {
    reqwest::Client::new().get(URL).send().await?.text().await
}

// ✓ AX-17 构建一次进 state；双超时
fn http_client() -> reqwest::Client {
    reqwest::Client::builder()
        .connect_timeout(std::time::Duration::from_secs(3))
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .expect("Client::builder 只在无效 TLS 配置失败")
}
```

**边界防护（门）**

- AX-04 超时分层：上游 → HTTP 边界 → LB。非流式可用 `TimeoutLayer`；**SSE/长流式禁止整请求 TimeoutLayer 一刀切**。混部 Router 不要给整棵树加短超时。
- AX-05 请求体上限显式（`DefaultBodyLimit::max`）；并发上限/负载卸除按容量实测。仅依赖业务限流、路由层零声明时标缺口。
- AX-06 优雅停机：`axum::serve(..).with_graceful_shutdown(signal)` + drain 超时；后台任务要有统一取消与可等待归宿（见 AS-04）。

**吞吐、可观测、extractor（门）**

- AX-07 大响应流式：`Body::from_stream` / SSE，不在内存拼完整 `Vec`；上传下载同理走流。
- AX-08 阻塞与重 CPU 出 runtime：`spawn_blocking`（ASYNC-03）；巨型 JSON 序列化也算重 CPU。
- AX-09 `CompressionLayer` 只对文本类可压缩响应开，已压缩内容与流式跳过。
- AX-10 数据层有 `sqlx` 证据时叠加 [sqlx.md](sqlx.md)；有 `sea-orm` 证据时叠加 [seaorm.md](seaorm.md)。
- AX-11 `TraceLayer` + request-id 贯通全链；错误一次原则——handler 与统一 `IntoResponse` 层二选一记录（OBS-03）。
- AX-12 具名错误 enum 实现 `IntoResponse` 集中映射状态码；对外不泄内部细节，5xx 附 request-id。
- AX-13 消费 body 的 extractor（`Json`/`Form`/`Bytes`）只能有一个且必须是**最后一个参数**；其余用 `FromRequestParts`。
- AX-14 handler 保持薄：解析 → 领域/服务 → 映射响应。SQL 直接写在 handler 仅当该端点就是 1–2 条查询且无第二入口。
- AX-15 鉴权走 `FromRequestParts` extractor（缺/过期 token → 401）。第一方浏览器优先 session cookie；S2S 用 JWT 并显式校验 `alg`/`iss`/`aud`/`exp`。
- AX-16 入站校验与领域 parse 分两层：API 层查形状；领域层 `Type::parse` 收不变式（API-08）。
- AX-17 出站 HTTP：进程级共用 `reqwest::Client`（AX-02，现行 **0.13.x / 0.13.4**，0.12 builder 同形）且同时设 **connect timeout + 请求 timeout**；含重试时另有总 deadline（AS-11）。用户可控 URL：`redirect(Policy::none())` + host 白名单，否则 SSRF。禁每请求 `Client::new()`，禁无超时的 `.send().await`。
- AX-18 **axum 0.8 路径语法**：动态段是 `{id}` / `{*path}`，不是 0.7 的 `:id` / `*path`。`"/users/:id"` 在 0.8 是字面路径。通配改 `/{*rest}`。
- AX-19 axum 0.8 的 `Option<Extractor>` 是「缺席 → `None`，在场但坏 → rejection」，且要求 `OptionalFromRequest(Parts)`。元组 `Path<(A, B)>` 元数必须等于路由 `{}` 个数。
- AX-20 rejection enum 全是 `#[non_exhaustive]`：映射复用 `rej.status()/body_text()` 并留兜底臂，禁止一律硬编码 400。
- AX-21 自定义 extractor：0.8 禁 `#[async_trait]`；同一具体类型禁止同时实现 `FromRequest` 与 `FromRequestParts`；消费 body 必须委托 `Json`/`Form`/`Bytes`。

**组合根 / 路由 / 中间件 — 一句话 + 子 playbook**

- AX-22 `with_state` 只在组合根、全部 route/nest/merge/layer 之后调用一次；子工厂返回 `Router<AppState>` 且内部不调 `with_state`。详见 [axum/scaffold.md](axum/scaffold.md) 与 [axum/routing.md](axum/routing.md)。
- AX-23 注册顺序不影响匹配（静态 > `{x}` > `{*rest}`）；顺序只决定 `layer`/`route_layer`/`method_not_allowed_fallback` 覆盖哪些已注册路由。详见 [axum/routing.md](axum/routing.md)。
- AX-24 路径命中但方法未注册返回 405，永不进 `Router::fallback`；定制 405 用 `method_not_allowed_fallback`（`// axum 0.7.8+`）。详见 [axum/routing.md](axum/routing.md) 与 [axum/handlers.md](axum/handlers.md)。
- AX-25 `nest` 禁止根前缀与通配前缀；fallback 只在组合根设一次；路由冲突在构造期 panic，必须有构造完整 `Router` 的单测。详见 [axum/routing.md](axum/routing.md)。
- AX-26 `Handler is not satisfied` 禁止猜：开 `macros` 加 `#[axum::debug_handler]`。详见 [axum/handlers.md](axum/handlers.md)。
- AX-27 响应元组 `StatusCode` 第一、`IntoResponseParts` 居中、body 最后且唯一；`CookieJar::add/remove` 必须放进返回元组。详见 [axum/handlers.md](axum/handlers.md)。
- AX-28 鉴权/授权门必须 `route_layer` 且先于全局 `.layer()` 挂。详见 [axum/middleware.md](axum/middleware.md) 与 [axum/auth.md](axum/auth.md)。
- AX-29 ≥2 个全局中间件一律一个 `ServiceBuilder` 一次 `.layer()`（先加的在外层）。详见 [axum/middleware.md](axum/middleware.md)。
- AX-30 `DefaultBodyLimit` 只限走 `Bytes` 的 extractor；handler 直接读 `Request`/`Body` 不受限，兜底必须 `RequestBodyLimitLayer`。详见 [axum/middleware.md](axum/middleware.md) 与 [axum/data.md](axum/data.md)。
- AX-31 tower-http `TimeoutLayer` 自回 408、只计到响应头；流式 body 用 idle 超时层。详见 [axum/middleware.md](axum/middleware.md)。
- AX-32 有浏览器调用就必须显式 origin allowlist；`CorsLayer::permissive()` 禁入生产。详见 [axum/middleware.md](axum/middleware.md)。
- AX-33 `TraceLayer` 默认 DEBUG 级；span 名/metric 标签用 `MatchedPath` 禁止 `request.uri()`。详见 [axum/observability.md](axum/observability.md)。

**实时 / 鉴权 / 数据 / 部署 / 测试 — 一句话 + 子 playbook**

- AX-34 错误只记一次：`impl IntoResponse for AppError` 是唯一记录点。详见 [axum/observability.md](axum/observability.md)。
- AX-35 OpenAPI 一律 `OpenApiRouter` + `routes!` 单次注册，禁止双写。详见 [axum/observability.md](axum/observability.md)。
- AX-36 WS 鉴权必须在 upgrade 前由 `FromRequestParts` 完成；Cookie 鉴权的 WS 必须校验 `Origin`。详见 [axum/realtime.md](axum/realtime.md) 与 [axum/auth.md](axum/auth.md)。
- AX-37 WS 主动推送用 `loop + select!`；`broadcast` 的 `RecvError::Lagged` 既不是断线也不能静默跳过。详见 [axum/realtime.md](axum/realtime.md)。
- AX-38 SSE 必挂 `.keep_alive(KeepAlive)` 且间隔短于代理 idle。详见 [axum/realtime.md](axum/realtime.md)。
- AX-39 jsonwebtoken ≥10 必须显式选后端 feature；`Validation::new(alg)` + iss/aud；access token 5–15 分钟。详见 [axum/auth.md](axum/auth.md)。
- AX-40 Session 与密码：登录成功先 `session.cycle_id()`；argon2 校验进 `spawn_blocking`。详见 [axum/auth.md](axum/auth.md)。
- AX-41 OAuth2 回调先比对一次性 `state`；token 交换的 Client 必须 `redirect(Policy::none())`。详见 [axum/auth.md](axum/auth.md)。
- AX-42 认证失败 401、授权失败 403 分层；权限写 `resource:action`。详见 [axum/auth.md](axum/auth.md)。
- AX-43 上传逐 chunk 写临时文件 → fsync → 原子 `rename`；禁 `field.bytes()` 收整个文件。详见 [axum/data.md](axum/data.md)。
- AX-44 `sqlx::Error` 在一处 `From` 映射：唯一键冲突 → 409、`PoolTimedOut` → 503。详见 [axum/data.md](axum/data.md) 与 [sqlx.md](sqlx.md)。
- AX-45 `ServeDir`/`ServeFile` 只能 `nest_service`/`fallback_service`/`route_service` 挂载。详见 [axum/data.md](axum/data.md)。
- AX-46 `with_graceful_shutdown` 只停 accept、等在途请求；WS/spawn 任务要自己收。详见 [axum/deploy.md](axum/deploy.md)。
- AX-47 `axum::serve(..)` 必须是 main 最后一个被 `.await` 的表达式；停机信号同时等 `ctrl_c` 与 SIGTERM。详见 [axum/deploy.md](axum/deploy.md) 与 [axum/scaffold.md](axum/scaffold.md)。
- AX-48 `ConnectInfo<SocketAddr>` 必须由 `into_make_service_with_connect_info` 供给；LB 后客户端 IP 按可信代理 CIDR 取。详见 [axum/deploy.md](axum/deploy.md)。
- AX-49 axum 0.8 默认 feature 不含 `http2`/`macros`/`ws`/`multipart`；升 0.8 必须对齐 tower 0.5 / tower-http **0.6.x / 0.6.11**（crates.io；axum 0.8.9 要 ^0.6.8，**不要** 0.7）/ axum-extra 0.10。详见 [axum/migrate.md](axum/migrate.md)。
- AX-50 所有测试经同一个 `pub fn app(state) -> Router` 驱动；oneshot 发 JSON 必须带 `content-type`。详见 [axum/testing.md](axum/testing.md)。
- AX-51 测试默认不起端口；SSE/WS 禁止 `to_bytes` 全量收。详见 [axum/testing.md](axum/testing.md)。
- AX-52 0.7→0.8 完成判据不是 `cargo build`：`rg '"[^"]*/[:*][A-Za-z_]'` 零命中 + 构造完整 `Router` 的测试通过，禁止 `without_v07_checks()` 止血。详见 [axum/migrate.md](axum/migrate.md)。

## 深入（按信号加载）

一次只加载 1–2 个；`review`/`audit`/普通实现命中 axum 证据时按同表叠加，不整目录读。

| 用户信号 / 代码证据 | 加载 |
|---|---|
| 「新建服务 / 搭骨架 / 整理 main.rs」；`Router::new()` 组合根、`AppState`、`with_state`、进程秒退 | [axum/scaffold.md](axum/scaffold.md) |
| `nest`/`merge`/`fallback`/`nest_service`；启动 panic（`Overlapping`/`Nesting at the root`）；404 与 405 混淆；按领域拆路由 | [axum/routing.md](axum/routing.md) |
| `Path`/`Query`/`Json`/`Option<Extractor>`、`impl FromRequest(Parts)`、`*Rejection`、`validator`/`garde` | [axum/extractors.md](axum/extractors.md) |
| 贴出 `Handler<_, _> is not satisfied`；`impl IntoResponse for`、`HandleErrorLayer`；「同时返回状态码/header/cookie」 | [axum/handlers.md](axum/handlers.md) |
| `middleware::from_fn`/`route_layer`/`ServiceBuilder`/`tower_http::*`；「中间件顺序 / CORS / 限流怎么挂」 | [axum/middleware.md](axum/middleware.md) |
| `WebSocketUpgrade`/`Sse`/`broadcast::channel`；聊天、通知、进度条、LLM token 流 | [axum/realtime.md](axum/realtime.md) |
| `jsonwebtoken`/`tower-sessions`/`axum-login`/`oauth2`、`Authorization: Bearer`；「保护路由 / 加登录 / 做权限」 | [axum/auth.md](axum/auth.md) |
| handler 里 `PgPool`/`begin()`、`Multipart`、`ServeDir`/`ServeFile`/`rust-embed` | [axum/data.md](axum/data.md) |
| `tracing_subscriber`/`TraceLayer`/`#[instrument]`/`utoipa`；「request-id 串不起来 / 接 OTel / 生成 Swagger」 | [axum/observability.md](axum/observability.md) |
| `#[tokio::test]` + `tower::ServiceExt`/`axum-test`；「给 handler 补测试」「review 这个 axum 服务」 | [axum/testing.md](axum/testing.md) |
| `Dockerfile`/`[profile.release]`/`with_graceful_shutdown`/`ConnectInfo`/`worker_threads`；「滚动发布丢请求 / 被 SIGKILL / 并发一上就卡」 | [axum/deploy.md](axum/deploy.md) |
| `axum = "0.7"` 要升 `"0.8"`；升后启动 panic 或成片编译错；判断示例针对哪条版本线 | [axum/migrate.md](axum/migrate.md) |

## 验证（PERF-01）

release 构建 + oha/wrk 同机压测，前后对比 p50/p99/RPS；单元/契约测试用 `tower::ServiceExt::oneshot` 免起服务器（TEST-10）。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表 + 按收益排序的候选（AX 编号 + 关联全局规则号）+ 验证方案。`--apply` 或明确“修/改/实现”时：再给实际改动与压测前后数据。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
