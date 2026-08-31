# axum/observability — tracing 接线与 OpenAPI 生成

目的：代码里出现 `tracing_subscriber`/`TraceLayer`/`#[instrument]`/`utoipa` 证据，或用户问「日志乱序、span 嵌套错、request-id 串不起来、接 OTel、生成 Swagger」时加载。只深化 [../axum.md](../axum.md) 的 AX-11/AX-12 与全局 OBS-01..OBS-06、TR-01..18；超时/停机/错误 enum 的形状仍以 owner 清单为准，数据层字段见 [../sqlx.md](../sqlx.md)。tracing 侧 API 对 axum 0.7/0.8 相同；utoipa-axum 版本与 axum 主版本绑定（见下）。

## subscriber：进程只装一次

1. `registry().with(filter).with(fmt).init()` 只在 `main` 调一次、早于 `axum::serve`；第二次 `init()` panic。`.with()`/`.init()` 来自 `prelude::*`（`SubscriberExt`/`SubscriberInitExt`），不导入不编译。
2. `EnvFilter` 用 `try_from_default_env()` 带回退：`from_default_env()` 是 lossy 的，写错的指令被静默忽略、`RUST_LOG` 未设时只剩 ERROR 级——症状是「什么都不打」而不是 panic。开发回退必须含 `axum::rejection=trace`（否则 extractor 拒绝只剩一个裸 4xx）和 `tower_http=debug`（`TraceLayer` 默认钩子在 DEBUG，不开等于没装）；生产回退是 `info`。
3. 同一 writer 一层 fmt：开发 `.pretty()`，生产 `.json()`（feature `json`，默认已带当前 span 与 span 列表字段，要把事件字段拍平到顶层才加 `.flatten_event(true)`）；stdout 上两分支用 `.boxed()` 统一类型。控制台+文件是 **Registry 上两个 writer**（TR-20），不是两个 fmt 打同一 stdout。

```rust
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

fn init_tracing(json: bool) {
    let filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| {
        format!("info,{}=debug,tower_http=debug,axum::rejection=trace", env!("CARGO_CRATE_NAME")).into()
    });
    let fmt_layer = if json { fmt::layer().json().boxed() } else { fmt::layer().pretty().boxed() };
    tracing_subscriber::registry().with(filter).with(fmt_layer).init(); // 进程唯一一次
}
```

## TraceLayer 与 request-id（AX-33）

1. `make_span_with` 以 `MatchedPath`（路由模板 `/users/{id}`）做聚合键；拿 `request.uri()` 当 span 名或 metric 标签 = 基数无界，后端要么丢数据要么按量计费。`MatchedPath` 只在 `Router::layer` 挂的中间件里可见，从外面 `ServiceBuilder::service(router)` 包一层读不到。健康检查/metrics 路由不挂 `TraceLayer`：`Router::new().route("/healthz", ..).merge(api.layer(http))`，别在 `make_span_with` 里判路径。
2. 要在 `on_response` 里填的字段必须在 `info_span!` 中以 `tracing::field::Empty` 预声明；对未声明字段 `span.record` 静默丢弃，无编译错误也无运行错误。
3. 顺序（`ServiceBuilder` 自上而下 = 外到内）：`SetRequestIdLayer` → `TraceLayer` → `PropagateRequestIdLayer` → `CatchPanicLayer` → 业务。id 生成在 TraceLayer 外侧 span 才读得到；传播在内侧 `on_response` 才看到响应头；panic 捕获在最内侧 500 才会记到 span 的 `status`。
4. `SetRequestIdLayer` 对**已带** `x-request-id` 的请求不覆盖。入口直面公网且无 LB 时要么先剥掉该头，要么校验长度/字符，否则客户端能往日志里注入任意字符串；有 LB 时沿用 LB 生成的 id 与 LB 日志对齐。

```rust
use axum::{extract::MatchedPath, http::Request, response::Response};
use tower_http::{catch_panic::CatchPanicLayer, trace::TraceLayer,
    request_id::{MakeRequestUuid, PropagateRequestIdLayer, SetRequestIdLayer}};
use tracing::{field::Empty, info_span, Span};

let http = tower::ServiceBuilder::new()
    .layer(SetRequestIdLayer::x_request_id(MakeRequestUuid))
    .layer(TraceLayer::new_for_http()
        .make_span_with(|req: &Request<_>| {
            let matched = req.extensions().get::<MatchedPath>().map(MatchedPath::as_str);
            let request_id = req.headers().get("x-request-id").and_then(|v| v.to_str().ok()).unwrap_or("-");
            info_span!("http", request_id, method = %req.method(), matched_path = matched,
                path = req.uri().path(), status = Empty, latency_ms = Empty, user_id = Empty)
        })
        .on_response(|res: &Response, latency: std::time::Duration, span: &Span| {
            span.record("status", res.status().as_u16());
            span.record("latency_ms", latency.as_millis() as u64);
            tracing::info!("response"); // 访问行：每请求恰一条
        })
        .on_failure(()))                 // 关默认 on_failure：5xx 详情由 IntoResponse 层记一次
    .layer(PropagateRequestIdLayer::x_request_id())
    .layer(CatchPanicLayer::new());      // panic → 500，连接不再被 hyper 直接掐断
let app = Router::new().merge(api).layer(http); // TimeoutLayer/DefaultBodyLimit 在它内侧（AX-04/05）
```

## 字段规范

| 字段 | 来源 | 记录点 / 级别 |
|---|---|---|
| `request_id` | `x-request-id`（`SetRequestIdLayer` 生成或 LB 下发） | span 创建时；5xx 响应头靠 `PropagateRequestIdLayer` 带回（AX-12） |
| `method` | `req.method()`（`%`） | span 创建时 |
| `matched_path` | `MatchedPath` extension，路由模板 | span 创建时；聚合键、metric 标签 |
| `path` | `req.uri().path()`，**不含 query**（query 里常有 token） | span 创建时 |
| `status` / `latency_ms` | `on_response` 的 `Response`/`Duration` | `Empty` 预声明，`span.record` 回填；访问行 INFO |
| `user_id` | 鉴权 extractor（AX-15）成功后 `Span::current().record("user_id", id)` | `Empty` 预声明；匿名路由留空 |
| `error` | `IntoResponse` 层 `error = ?self`（含 source 链） | 5xx → ERROR 恰一次；4xx → DEBUG 或不记（OBS-04） |
| 领域字段（`order_id` 等） | handler 事件 `info!(order_id = %id, "…")` 或 `#[instrument(fields(..))]` | INFO=业务里程碑，DEBUG=开发期 |
| `trace_id` | 只随导出到 OTel 后端的 span 带，fmt/json 日志行**不会**自动出现 | 要日志↔链路关联：`Empty` 预声明，`set_parent` 后 `span.record("trace_id", span.context().span().span_context().trace_id().to_string())`（`OpenTelemetrySpanExt` + `opentelemetry::trace::TraceContextExt`） |

字段必须是 `key = value`（`%` 走 Display、`?` 走 Debug），`info!("user {id} fetched")` 把字段揉进句子后不可过滤、不可聚合（OBS-02）。事件消息是常量描述，变量进字段。

## 错误一次与级别语义（AX-34）

1. 同一个错误只允许一处落日志（OBS-03/AX-11）：handler 用 `?` 原样传播并把上下文放进错误（ERR-02），`impl IntoResponse for AppError` 是唯一记录点——它既看得到内部细节，又是对外脱敏的出口（AX-12）。`TraceLayer` 默认 `on_failure` 会对 5xx 再记一条 ERROR，要么 `.on_failure(())` 关掉，要么 `IntoResponse` 不记。
2. `#[instrument(err)]` 也是一处记录：handler 已经走 `IntoResponse` 集中记录时禁止再加 `err`；服务层内部函数可用 `err(level = "debug")` 留线索而不抬级别。
3. 4xx 不是 ERROR：客户端错误按 DEBUG 或不记，否则 bot 扫描把告警打穿；5xx 是 ERROR=需人介入（OBS-04）。

```rust
// ✗ 三层各记一遍，查一条事故看到三条 ERROR
let user = repo.find(id).await.map_err(|e| { tracing::error!(?e, "find failed"); e })?;
// ✓ handler 只传播；IntoResponse 是唯一记录点
let user = repo.find(id).await?;
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code) = self.status_and_code();                                               // 具名 enum 集中映射（AX-12）
        if status.is_server_error() { tracing::error!(error = ?self, code, "request failed"); } // 唯一一处；?self 带 source 链
        (status, Json(ErrorBody { code, message: self.public_message() })).into_response()
    }
}
```

## span 传播与 spawn（AX-34）

1. `Span::enter()` 的 guard 禁止跨 `.await`：future 让出后同线程的其他任务被记进这个 span，时序和父子关系全错。async 代码只用 `#[instrument]` 或 `future.instrument(span)`；`enter()` 只在无 `.await` 的同步块合法。
2. `tokio::spawn` 的任务不继承当前 span：不 `.instrument()` 的后台任务日志里没有 `request_id`。`spawn_blocking` 闭包是同步代码，把 `Span::current()` move 进去再 `enter()`。后台任务仍受 AS-05 管束（进 `TaskTracker`/`JoinSet`），span 只解决归属，不解决生命周期。

```rust
use tracing::{Instrument, Span};
tokio::spawn(async move { mailer.send(job).await }
    .instrument(tracing::info_span!("send_email", job_id = %job_id)));   // 子 span 挂在请求 span 下
let span = Span::current();
tokio::task::spawn_blocking(move || { let _g = span.enter(); argon2_verify(&hash, &pw) });
```

## 脱敏与 panic（AX-34）

1. `#[instrument]` 一律显式写 `skip_all`，再用 `fields(user_id = %id)` 挑要记的（宏本身的默认是把全部参数按 Debug 记进 span）——`State`、`Json<Body>`、带密码/token 的结构一律不进 span（OBS-02）。秘密类型的 `Debug` 必须脱敏（API-05）：`secrecy::SecretString` 或手写 `impl Debug` 输出 `[REDACTED]`；只靠「别打它」守不住 `?self`。
2. header：`SetSensitiveRequestHeadersLayer::new([AUTHORIZATION, COOKIE])` 放最外侧（feature `sensitive-headers`），之后任何 Debug 输出都是 `Sensitive`；`DefaultMakeSpan::include_headers(true)` 与 `on_body_chunk` 只开在开发环境。`path` 字段不带 query string。
3. `CatchPanicLayer` 是崩溃→500 的安全网，不是控制流（ERR-04）；默认 panic hook 已把 panic 信息打到 stderr，要带 `request_id` 用 `CatchPanicLayer::custom(handler)` 在 handler 里 `tracing::error!` 一次。`spawn_blocking` 里的 panic 以 `JoinError` 回到 handler，按 AS-05 检查 `is_panic()`。

## OpenTelemetry 最小接线

```rust
// opentelemetry_sdk 0.30+ / tracing-opentelemetry 0.31+：类型名随版本漂移，以 docs.rs 为准
use opentelemetry::{global, trace::TracerProvider};
use opentelemetry_sdk::{propagation::TraceContextPropagator, trace::{Sampler, SdkTracerProvider}, Resource};
let provider = SdkTracerProvider::builder()
    .with_batch_exporter(opentelemetry_otlp::SpanExporter::builder().with_tonic().build()?) // 需 feature grpc-tonic，默认是 http-proto
    .with_sampler(Sampler::ParentBased(Box::new(Sampler::TraceIdRatioBased(0.05)))) // 按量定比例
    .with_resource(Resource::builder().with_service_name("svc").build())
    .build();
global::set_text_map_propagator(TraceContextPropagator::new());
let otel = tracing_opentelemetry::layer().with_tracer(provider.tracer("svc"));
tracing_subscriber::registry().with(filter).with(fmt_layer).with(otel).init();
// AX-06/AX-46 停机分支里 provider.shutdown()?：不调用则 batch 队列里的 span 全丢
```

1. 采样 `ParentBased(TraceIdRatioBased(r))`：尊重上游决定，本服务起点按比例；生产 `AlwaysOn` 必须附流量估算。`.with(EnvFilter)` 是全局滤网，会同时滤掉发往 OTel 的 span；要「控制台只看 info、OTel 收 debug」改用逐层 `fmt_layer.with_filter(EnvFilter::new(..))`。
2. 接上游 `traceparent`：在 `make_span_with` 末尾 `span.set_parent(global::get_text_map_propagator(|p| p.extract(&HeaderExtractor(req.headers()))))`（`opentelemetry-http` + `tracing_opentelemetry::OpenTelemetrySpanExt`）；不想手写就用 `axum-tracing-opentelemetry` 的 `OtelAxumLayer` 替代自定义 `TraceLayer`，二者不要同时挂（每请求两个 span）。出站 `reqwest` 要注入 `traceparent`（`reqwest-tracing` 或手动 `inject_context`），否则链路在本服务断掉。

## OpenAPI：utoipa 5 + utoipa-axum（AX-35）

```toml
utoipa = { version = "5", features = ["axum_extras"] }
utoipa-axum = "0.2"                                                    # 0.2 ↔ axum 0.8；0.1 ↔ axum 0.7
utoipa-swagger-ui = { version = "9", features = ["axum", "vendored"] } # 三者独立发版，各自钉
```

1. 三个 crate 版本号互不对应，`utoipa-axum` 仍是 0.x，升级后对照 docs.rs 复核 `routes!`/`split_for_parts`。`utoipa-swagger-ui` 默认在 build 时从 GitHub 下载 UI 包：离线 CI 必须开 `vendored`；`utoipa-scalar`/`utoipa-redoc` 页面从 CDN 拉 JS，内网环境只能用 vendored swagger-ui。
2. 新服务一律 `OpenApiRouter` + `routes!`：handler 注册一次，路由与文档同源。`#[derive(OpenApi)] + #[openapi(paths(..))]` 要在 `Router::route` 和 `paths(..)` 各写一遍，漏一边就是「有路由无文档」或「有文档返回 404」，且没有任何检查。
3. `#[utoipa::path]` 的 HTTP 方法必须是**第一个**参数；`path` 永远是 OpenAPI 花括号 `"/users/{id}"`——0.8 与路由串逐字相同（AX-18），0.7 仓路由串仍写 `:id` 而注解保持 `{id}`。`routes!` 里多个 handler 必须同一 `path`（GET/PUT 同一资源）；不同 path 分开 `.routes()`。通配 `/{*rest}` 不进 OpenAPI，用 `OpenApiRouter::route` 挂普通路由。
4. `ToSchema` 只挂 wire DTO（响应体/请求体/`ErrorBody`），不挂 `FromRow` 行类型（API-08/SX-08）；serde 属性（`rename_all`、`skip`）优先于 `#[schema]`，外部类型用 `#[schema(value_type = String)]` 或开 `chrono`/`uuid` feature。查询参数 struct 派生 `IntoParams`，`axum_extras` 让 `Query<T>` 自动推断 `parameter_in`。
5. 安全方案：`#[openapi(modifiers(&SecurityAddon))]` 里用 `Modify` 注册 `SecurityScheme::Http(bearer)`，受保护端点写 `security(("bearer" = []))`；鉴权仍由 extractor 执行（AX-15），注解只是文档。

```rust
use axum::{extract::{Path, State}, Json, Router};
use utoipa::{OpenApi, ToSchema};
use utoipa_axum::{router::OpenApiRouter, routes};
use utoipa_swagger_ui::SwaggerUi;
#[derive(serde::Serialize, ToSchema)]
struct User { id: u64, email: String }
#[derive(OpenApi)]
#[openapi(info(title = "svc", version = "1.0.0"), components(schemas(User, ErrorBody)))]
struct ApiDoc;
#[utoipa::path(get, path = "/users/{id}", tag = "users",
    params(("id" = u64, Path, description = "用户 id")),
    responses((status = 200, body = User), (status = 404, body = ErrorBody)))]
async fn get_user(State(s): State<Arc<App>>, Path(id): Path<u64>) -> Result<Json<User>, AppError> {
    s.users.find(id).await.map(Json)
}
fn api_router() -> OpenApiRouter<Arc<App>> {
    OpenApiRouter::with_openapi(ApiDoc::openapi()).routes(routes!(get_user)) // 一次注册 = 路由 + 文档
}
fn app(state: Arc<App>, expose_docs: bool) -> Router {
    let (router, api) = api_router().split_for_parts(); // OpenApiRouter 不是 axum::Router，必须拆
    let docs = SwaggerUi::new("/docs").url("/api-docs/openapi.json", api);
    (if expose_docs { router.merge(docs) } else { router }).with_state(state)
}
```

## 文档端点与漂移检查（AX-35）

1. 文档端点是否上生产是配置项，不是 `cfg!(debug_assertions)`：内部服务默认开（客户端生成依赖 `/api-docs/openapi.json`），公网服务默认关或放在鉴权后面；`servers(..)` 不写内网地址。
2. `OpenApiRouter` 消除了路由与文档的漂移，消除不了**契约**漂移（字段改名、状态码增删）。测试里 `insta::assert_json_snapshot!(api_router().into_openapi())`（TEST-11）：契约变更必须伴随快照 diff 被人审；DTO 动了而快照没动 = 忘了 `ToSchema`。客户端从仓库提交的快照生成，不从运行中的服务拉；CI 快照红 = 先更新快照再合并。

## 验证

- tracing：`oneshot` 一个 5xx 请求，断言响应头带 `x-request-id`、输出里恰一条 ERROR 且含同一 `request_id`（`fmt().with_test_writer()` 或 `tracing-test` 捕获）；压测后查后端 span 名/metric 标签数等于路由数而不是请求数。
- OTel：本地起 otel-collector 的 debug exporter，确认上游 `traceparent` 与本服务 span 同一 `trace_id`，停机后队列无丢失。
- OpenAPI：`oneshot` GET `/api-docs/openapi.json` 200 且能被 `serde_json` 解析；`expose_docs=false` 时 404；快照测试入 CI。
