# axum/middleware — 中间件与 tower 栈：from_fn、次序、tower-http 常用层

目的：代码里出现 `middleware::from_fn`/`Router::layer`/`route_layer`/`ServiceBuilder`/`tower_http::*`，或用户问「中间件顺序、鉴权门、CORS、超时、限流怎么挂」时加载。只讲机制与次序；超时分层、body 上限、压缩范围、trace 贯通的阈值与取舍归 owner [../axum.md](../axum.md)（AX-04/AX-05/AX-09/AX-11），鉴权 extractor 本身见 [auth.md](auth.md)。0.7 与 0.8 的 `axum::middleware` API 相同；tower 0.5、tower-http 0.6。

## 选型：map_* → from_fn → 手写 Service

| 需求 | 用 | 备注 |
|---|---|---|
| 只改请求（加头、改 Accept） | `map_request` | 可返回 `Result<Request, impl IntoResponse>` 拒绝 |
| 只改响应 | `map_response` | 静态安全头直接用 tower-http `SetResponseHeaderLayer::if_not_present`，别手写 |
| 前后都跑或可短路（鉴权、限流、计时） | `from_fn` / `from_fn_with_state` | 也接 `move` 闭包（参数要标类型），捕获 `Arc` 配置比走 state 少一层仪式 |
| 已有 `FromRequestParts` 鉴权 extractor，想当整组路由的门 | `route_layer(from_extractor::<AuthUser>())` | 不必再写 from_fn（AX-15） |
| 要 `poll_ready` 背压、builder 配置、跨 Router 复用或发布 crate | 手写 `Layer` + `Service` | 见末节 |

1. `from_fn` 参数次序由编译器强制：`[零或多个 FromRequestParts], 唯一的 FromRequest, Next`。`Request` 必须紧邻 `Next`；`HeaderMap`/`State`/`Method` 放前面；两个消费 body 的参数（`String` + `Request`）不编译。错位报的是一坨 `Handler<_, _> is not satisfied`——0.8 给函数加 `#[axum::debug_middleware]`（feature `macros`，同 `debug_handler`）让报错指到具体参数。
2. 0.7/0.8 的 `Next` 与 `axum::extract::Request` 都没有泛型；还在写 `Next<B>`、`Request<Body>` 是 0.6 残留，签名用 `http::Request<B>` 泛型同样撞 trait bound。
3. 中间件里要 `State<S>` 必须用 `from_fn_with_state(state.clone(), f)`；它的 state 与 `Router::with_state` 互不相干，要同一份数据就传同一个 `Arc` 的 clone（AX-01）。
4. 不调 `next.run` 就是短路：没有编译错、没有运行时错，handler 静默不跑。返回 `Result<Response, StatusCode>` 让 `?` 做短路，比 `if … { return … }` 清楚。
5. 给 handler 传数据走请求 extensions（`Clone + Send + Sync + 'static`）；handler 缺 `Extension<T>` 是 500「Missing request extension」，只在 `route_layer` 保证注入的路由上直接用，对外要 401 语义就自定义 `FromRequestParts` 读 `parts.extensions`。核心状态不走 Extension（AX-01），请求级数据才走。

```rust
// axum 0.7 / 0.8
use axum::{body::Body, extract::{Request, State}, http::{header, StatusCode}, middleware::Next, response::Response};

#[derive(Clone)]
struct CurrentUser { id: i64 }

async fn require_user(
    State(app): State<Arc<AppState>>,   // FromRequestParts 在前
    mut request: Request,               // 唯一的 FromRequest，倒数第二
    next: Next,                         // 最后
) -> Result<Response, StatusCode> {
    let token = request.headers().get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok()).and_then(|v| v.strip_prefix("Bearer "))
        .ok_or(StatusCode::UNAUTHORIZED)?;
    let user = app.sessions.verify(token).await.map_err(|_| StatusCode::UNAUTHORIZED)?;
    request.extensions_mut().insert(CurrentUser { id: user.id });
    Ok(next.run(request).await)
}

// 要看 body（签名校验）：不能再加第二个 FromRequest，读完自己装回去。会缓冲整个 body，只用于小而有上限的请求（AX-07）
async fn verify_hmac(request: Request, next: Next) -> Result<Response, StatusCode> {
    let (parts, body) = request.into_parts();
    let bytes = axum::body::to_bytes(body, 1 << 20).await.map_err(|_| StatusCode::PAYLOAD_TOO_LARGE)?;
    hmac_ok(&parts.headers, &bytes).then_some(()).ok_or(StatusCode::UNAUTHORIZED)?;
    Ok(next.run(Request::from_parts(parts, Body::from(bytes))).await)
}
```

## 次序：请求从外到内，响应原路返回（AX-28、AX-29）

```text
client ──请求→                                                         ←响应── client
┌ NormalizePathLayer             Router 外：layer.layer(router) + into_make_service；改 URI 必须先于路由匹配
│ ┌ Router::layer(ServiceBuilder)    包全部已注册路由 + fallback(404)；ServiceBuilder 自上而下 = 外到内
│ │  SetSensitiveRequestHeadersLayer 进 trace 前把 Authorization/Cookie 标敏感
│ │  SetRequestIdLayer               没有 x-request-id 才生成，网关传来的沿用
│ │  TraceLayer                      span 读 request-id + MatchedPath；下面产生的 408/503/401 全在 span 内
│ │  PropagateRequestIdLayer · SetSensitiveResponseHeadersLayer（响应侧脱敏必须在 trace 内层）
│ │  HandleErrorLayer → load_shed → GlobalConcurrencyLimitLayer   tower 层的 BoxError 在此收口成 503
│ │  TimeoutLayer (tower-http)        直接 408；只计到响应头返回为止
│ │  CorsLayer                       预检不带凭据，必须在鉴权之外，否则 OPTIONS 被 401
│ │  CompressionLayer · RequestBodyLimitLayer · DefaultBodyLimit
│ │  ┌ Router::route_layer           只包已匹配路由，404 不经过；要先于上面的 .layer() 调用
│ │  │  from_fn(require_user)        短路 401/403，extensions 放 CurrentUser
│ │  │  ┌ handler                    extractors → 领域调用 → IntoResponse
```

1. 链式 `.layer()` 后加的在外层（先见请求）；`ServiceBuilder` 里先加的在外层。两个模型相反，≥2 个全局层一律一个 `ServiceBuilder` 一次 `.layer()`，读法与洋葱一致。
2. 层只包调用时已存在的路由（AX-23）：所有 `.route()`/`.fallback()`/`.nest()`/`.merge()` 在前，`.layer()`/`.route_layer()` 在后；之后再加的路由不被包，且无任何告警。空 Router 上 `route_layer` 直接 panic。
3. `layer` 包 fallback，`route_layer` 不包：鉴权门用 `layer` 会把 `GET /不存在` 变 401（泄露路由存在性）；用 `route_layer` 才是 404。反过来 trace/CORS/压缩/超时/request-id 必须 `layer`，404 也要被记录和跨域放行。
4. `route_layer(auth)` 先挂、全局栈后挂，auth 才在栈内层；颠倒后 auth 跑在 CORS/trace 外面——预检被 401、401 响应没 span。
5. 作用范围跟着 Router 走：`nest("/api", api.layer(x))` 只包 `/api` 子树（含子树自己的 fallback）；`nest("/api", api).layer(x)` 包全树。`merge` 不去重：子 Router 和根都挂 `TraceLayer` 就双 span。单路由放大 body 上限写在 `MethodRouter` 上：`post(upload).layer(DefaultBodyLimit::max(50 << 20))`。
6. `Router::layer` 里的中间件在路由匹配之后运行，改 URI 不会重新匹配：`NormalizePathLayer`、去前缀的 `map_request` 必须包在 Router 外。

```rust
// ✗ 作者以为 auth 先跑；实际 trace 在外、auth 在内，且 auth 用 layer 会把 404 变 401
Router::new().route("/me", get(me))
    .layer(middleware::from_fn(auth))
    .layer(TraceLayer::new_for_http());

// ✓ route_layer 先挂；全局栈一个 ServiceBuilder，自上而下读
Router::new().route("/me", get(me))
    .route_layer(middleware::from_fn(auth))
    .layer(ServiceBuilder::new()
        .layer(TraceLayer::new_for_http())                  // 最外：408 也进 span
        .layer(TimeoutLayer::new(Duration::from_secs(10)))
        .layer(CompressionLayer::new()));

// ✓ 改 URI 的层包在 Router 外；axum::serve 需要 ServiceExt::into_make_service
use axum::{extract::Request, ServiceExt};
use tower::Layer;
let app = NormalizePathLayer::trim_trailing_slash().layer(router);
axum::serve(listener, ServiceExt::<Request>::into_make_service(app)).await?;
```

## tower-http 与 tower 常用层（AX-30..AX-33）

每个层一个 Cargo feature，缺 feature 报 `could not find trace in tower_http`；用 `cargo tree -e features -i tower-http` 核对，不要图省事开 `full`。

| 层 | feature | 要点 |
|---|---|---|
| `TraceLayer` | `trace` | 级别/span 字段规则见 AX-33，接线见 [observability.md](observability.md)；本文只补：默认分类器 `ServerErrorsAsFailures` 只把 5xx 算 failure，4xx 要自己记；`merge` 不去重，全树只挂一次 |
| `SetRequestIdLayer` / `PropagateRequestIdLayer` | `request-id` | Set 在 trace 外、Propagate 在 trace 内；`MakeRequestUuid`；已有 header 不覆盖，extension 里是 `RequestId` |
| `SetSensitiveRequestHeadersLayer` / `SetSensitiveResponseHeadersLayer` | `sensitive-headers` | 只影响 `Debug` 输出（打印 `Sensitive`），不删头；请求侧在 trace 外，响应侧在 trace 内，合体版 `SetSensitiveHeadersLayer` 放外层只对请求有效 |
| `TimeoutLayer` | `timeout` | 规则见 AX-31，阈值分层见 AX-04；本文只补：`RequestBodyTimeoutLayer`/`ResponseBodyTimeoutLayer` 是逐帧 idle（每收到一帧就重置），不是整条流的总时长，别拿它当 SSE 的全局上限 |
| `CorsLayer` | `cors` | 见下方代码；必须在鉴权外层 |
| `CompressionLayer` | `compression-gzip`/`-br`/`-zstd`/`compression-full` | 默认谓词已跳过 <32 字节、`text/event-stream`、grpc、图片；其余按 AX-09；响应含 secret 且回显用户输入时关压缩（BREACH），用 `.compress_when()` |
| `RequestBodyLimitLayer` / `DefaultBodyLimit` | `limit` / axum 内建 | 规则见 AX-30（AX-05）；本文只补：两者并存取小者，抬限写在 `MethodRouter` 上（见次序节第 5 条），`RequestBodyLimitLayer` 超限直接 413 |
| `SetResponseHeaderLayer` / `CatchPanicLayer` | `set-header` / `catch-panic` | 静态安全头；handler panic → 500 而不是连接被掐——这是兜底，不是 ERR-04 的许可 |
| `tower::limit` / `load_shed` / `buffer` / `timeout` | tower `limit`/`load-shed`/`buffer`/`timeout` | `BoxError` 收口与「每路由一份状态」规则见 AX-31；本文只补：`RateLimitLayer` 产出的 `RateLimit<S>` 只 derive `Debug`、不是 `Clone`，撞 `Router::layer` 的 `L::Service: Clone` 界，报错指在 `.layer()` 上而非限流本身（修法见下方代码）；`Buffer` 构造时 `tokio::spawn` worker（必须在 runtime 内），且把内层背压转成排队——它不是限流 |
| `tower_governor` | 三方 crate | 按 IP/key 令牌桶，状态在 `Arc` 配置里跨路由共享；默认 `PeerIpKeyExtractor` 需要 `app.into_make_service_with_connect_info::<SocketAddr>()`，可信反代后改 `SmartIpKeyExtractor`；按 README 起后台任务 `retain_recent()` 否则 key 表只增不减；构造形态随版本变，以 docs.rs 为准 |

```rust
// ✓ 生产 CORS（AX-32）：显式 origin allowlist；带凭据 + Any 的组合在 layer() 时 panic
let cors = CorsLayer::new()
    .allow_origin([HeaderValue::from_static("https://app.example.com")])   // 多域：AllowOrigin::list / ::predicate
    .allow_methods([Method::GET, Method::POST, Method::PATCH])
    .allow_headers([header::CONTENT_TYPE, header::AUTHORIZATION])
    .expose_headers([HeaderName::from_static("x-request-id")])            // 否则前端 JS 读不到
    .allow_credentials(true)
    .max_age(Duration::from_secs(600));                                   // 不设 = 每个请求都预检
// permissive()（`*`、不带凭据）/ very_permissive()（回显 origin + 凭据）只准本地开发
```

request-id + trace 栈的完整写法（`make_span_with`、`field::Empty` 预声明、`on_failure`）见 [observability.md](observability.md)（AX-33）；四个层的相对位置见上方次序图。

```rust
// ✓ 负载卸除（AX-31）：tower 层的 BoxError 由 HandleErrorLayer 收口；内层不 ready 时立即 503 而不是排队
let guard = ServiceBuilder::new()
    .layer(HandleErrorLayer::new(|err: BoxError| async move {
        if err.is::<tower::load_shed::error::Overloaded>() { StatusCode::SERVICE_UNAVAILABLE }
        else { StatusCode::INTERNAL_SERVER_ERROR }
    }))
    .load_shed()
    .layer(GlobalConcurrencyLimitLayer::new(512));   // 非 Global 版在 Router::layer 下变成「每路由 512」

// ✗ RateLimit<Route> 不是 Clone，编译错报在 .layer() 这行
router.layer(RateLimitLayer::new(100, Duration::from_secs(1)));

// ✓ Buffer 用内部 mpsc 把它变回 Clone；Buffer 的 Error 是 BoxError，仍要 HandleErrorLayer 收口才满足 Into<Infallible>
use tower::{buffer::BufferLayer, limit::RateLimitLayer};   // tower feature buffer + limit
router.layer(ServiceBuilder::new()
    .layer(HandleErrorLayer::new(|_: BoxError| async { StatusCode::TOO_MANY_REQUESTS }))
    .layer(BufferLayer::new(1024))
    .layer(RateLimitLayer::new(100, Duration::from_secs(1))));
// 这是全局速率、不分 IP，且 Router::layer 每路由各调一次 layer()（各一个 worker、各一份配额，AX-31）；按 IP 限流走 tower_governor
```

## 何时手写 tower::Service

只在需要 `poll_ready` 背压、builder 式配置、跨 Router/跨 tower 栈复用或发布 crate 时；否则 `from_fn`（SIMP-01）。`Router::layer` 要求产出的 Service `Clone + Send + Sync + 'static` 且 Future `Send`，所以 Future 通常 `Pin<Box<dyn Future + Send>>`。调用方不得跳过 `poll_ready` 直接 `call`（tower 允许实现 panic）；测试用 `tower::ServiceExt::oneshot`/`ready`，它们替你做 readiness。

```rust
#[derive(Clone)] struct TimingLayer;
impl<S> Layer<S> for TimingLayer { type Service = Timing<S>; fn layer(&self, inner: S) -> Timing<S> { Timing { inner } } }

#[derive(Clone)] struct Timing<S> { inner: S }
impl<S> Service<Request> for Timing<S>
where S: Service<Request, Response = Response> + Clone + Send + 'static, S::Future: Send + 'static,
{
    type Response = Response;
    type Error = S::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Response, S::Error>> + Send>>;
    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), S::Error>> { self.inner.poll_ready(cx) }
    fn call(&mut self, req: Request) -> Self::Future {
        // tower 约定：谁 poll_ready 过谁 call。拿走已 ready 的 inner，留下一个未 ready 的 clone
        let clone = self.inner.clone();
        let mut inner = std::mem::replace(&mut self.inner, clone);
        Box::pin(async move { let t = Instant::now(); let res = inner.call(req).await; tracing::debug!(ms = t.elapsed().as_millis()); res })
    }
}
```

## 验证

1. `tower::ServiceExt::oneshot` 免起服务器（TEST-10）：未匹配路径断言 404 而非 401；带 `Origin` + `Access-Control-Request-Method` 的 `OPTIONS` 不带 token 也过；超时路由用 `#[tokio::test(start_paused = true)]` + `tokio::time::advance` 断言 408（TEST-09）。
2. 次序：测试专用 `from_fn` 往 `Arc<Mutex<Vec<&'static str>>>` 里 push 名字，断言 `["trace", "auth", "handler"]`；改了 `ServiceBuilder` 就重跑。并发上限压测走 owner 的 PERF-01 流程，且要多路由同时打满，证明上限是全局而非每路由。
