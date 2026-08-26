# axum/testing — 测试 axum 服务与 API 评审清单

目的：target 出现 `#[tokio::test]` 搭配 `tower::ServiceExt`/`axum-test`/`tests/` 下的 HTTP 测试，或用户说「给 handler 补测试」「review 这个 axum 服务」时加载。只讲怎样驱动 `Router` 与评审顺序；AX 规则本体见 [../axum.md](../axum.md)，TEST 规则见全局清单，鉴权缺陷表见 [auth.md](auth.md)，本文不重复。以 axum 0.8.x 为准，0.7 差异处注明。

## 共享 `app()` 构造函数（一切测试的前提，AX-50）

1. `pub fn app(state: AppState) -> Router` 放 `src/lib.rs`，`main.rs` 与所有测试都调它。测试里临时 `Router::new().route(..)` 是测假货：少了 layer/fallback/state，生产里拦截请求的鉴权层在测试里根本不存在，测试绿与上线无关。
2. `tests/` 下每个文件是独立 crate，只看得到 lib 的 pub 面——`app()` 私有或只在 `main.rs` 里 = `unresolved import`。`app()` 是生产入口所以 pub 合理；`test_state()`/`test_pool()` 之类夹具走 test-util crate 或 `tests/it/common.rs`（TEST-03/05），不进 lib pub 面。
3. 状态经参数注入，`app()` 内不读环境变量、不连库——否则每个测试都得伪造环境，最后演变成静默跳过（TEST-07 的反面）。

## oneshot：不起端口，零新增依赖（AX-50）

- dev-deps：`tower = { version = "0.5", features = ["util"] }`、`http-body-util = "0.1"`。`Router` 实现 `Service<Request<Body>>`，`app.oneshot(req).await` 直接得 `Response`。
- `oneshot(self)` 消费 Router，第二次调用是 `use of moved value`：要么 `app.clone()`（Router 内部 Arc，clone 廉价，官方 testing 示例同样接受），要么 `let mut svc = app.into_service();` 后 `ServiceExt::<Request<Body>>::ready(&mut svc).await?.call(req)` 复用同一实例——`RouterIntoService<B>` 的 `B` 未定，裸 `svc.ready()` 报 type annotations needed。
- 读 body：`axum::body::to_bytes(res.into_body(), 1 << 20).await?`（limit 必填，用与生产 `DefaultBodyLimit` 同量级的数，别习惯性 `usize::MAX`）或 `BodyExt::collect().await?.to_bytes()`。body 是流，没有 `.bytes()`。
- JSON 请求必须带 `content-type: application/json`；缺了 `Json<T>` 直接 415（`MissingJsonContentType`），handler 没跑过。断言 200 失败先看这条。
- 扩展 trait 要进作用域：`use tower::ServiceExt`（`oneshot`/`ready`）、`use tower::Service`（`call`）、`use http_body_util::BodyExt`（`collect`）；缺 `util` feature 时 `oneshot` 根本不存在。
- `ConnectInfo<SocketAddr>` handler 在 oneshot 下没有对端地址：测试里 `.layer(MockConnectInfo(SocketAddr::from(([127, 0, 0, 1], 0))))`（`axum::extract::connect_info::MockConnectInfo`）。

```rust
// ✗ 没 content-type → 415；断言 200 失败还以为 handler 坏了
let res = app(test_state())
    .oneshot(Request::post("/users").body(Body::from(r#"{"name":"a"}"#)).unwrap())
    .await.unwrap();

// ✓ 完整形状：header + serde_json::to_vec + 限长读 body
use axum::{body::{to_bytes, Body}, http::{header, Request, StatusCode}};
use tower::ServiceExt;

#[tokio::test]
async fn create_user_returns_201() {
    let app = app(test_state());
    let req = Request::post("/users")
        .header(header::CONTENT_TYPE, "application/json")
        .body(Body::from(serde_json::to_vec(&json!({"name": "a"})).unwrap()))
        .unwrap();
    let res = app.clone().oneshot(req).await.unwrap(); // clone：同一 app 还能再发
    assert_eq!(res.status(), StatusCode::CREATED);
    let bytes = to_bytes(res.into_body(), 1 << 20).await.unwrap();
    let body: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(body["name"], "a"); // 期望手写，不 dump 响应当期望（TEST-08）
}
```

## axum-test `TestServer`：契约测试的默认工具

- 版本配对（AX-49）：axum-test 21.x 依赖 axum ^0.8；0.7 仓必须钉旧版 axum-test，否则 cargo 拉进两套 axum、两种 `Router` 类型 trait 对不上。oneshot 路线无此耦合。
- `TestServer::new(app)` 默认 mock transport（进程内、无 socket）；`server.get("/x").await` 直接 await `TestRequest` 得 `TestResponse`；`.json(&v)` 自动设 content-type；断言链 `assert_status_ok().assert_json(&json!({..}))`；取值 `json::<T>()`/`text()`。
- `TestServer::builder().expect_success_by_default()`：任何非 2xx 立刻 panic——契约测试默认开，预期失败的用例单独 `.expect_failure()`。
- cookie 会话：`.save_cookies()` 才会把 `Set-Cookie` 回放到后续请求；oneshot 没有 cookie jar，两次 oneshot 之间登录态不存在。
- 真实 HTTP：`.http_transport()`（随机端口），`server_address()` 此时返回 `Some(Url)`；WebSocket 握手必须真 socket。等价配置走 `TestServerConfig { transport, save_cookies, expect_success_by_default, .. }` + `TestServer::new_with_config`，新代码用 builder。

```rust
// ✓ 登录 → 带 cookie 访问受保护路由（AX-15 session 路径）
let server = TestServer::builder().save_cookies().expect_success_by_default().build(app(test_state()));
server.post("/login").json(&json!({"email": "a@x.io", "password": "pw"})).await;
let me: Me = server.get("/me").await.json::<Me>();
server.get("/admin").expect_failure().await.assert_status(StatusCode::FORBIDDEN);
```

## 真实 listener：只为停机、WebSocket、代理头（AX-51）

```rust
// ✓ 127.0.0.1:0 取端口；serve 进 spawn；停机信号可控、有上限
let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
let addr = listener.local_addr().unwrap();
let (tx, rx) = tokio::sync::oneshot::channel::<()>();
let server = tokio::spawn(async move {
    axum::serve(listener, app(test_state()))
        .with_graceful_shutdown(async { rx.await.ok(); })
        .await
});
let res = reqwest::get(format!("http://{addr}/healthz")).await.unwrap();
assert_eq!(res.status(), 200);
tx.send(()).unwrap();
tokio::time::timeout(Duration::from_secs(5), server) // 停机必须在上限内收口（AX-06）
    .await.expect("server did not drain in 5s").unwrap().unwrap();
```

- 固定端口 = 并行测试互相踩；`:0` 后读 `local_addr()`。`axum::serve(..)` 是 `IntoFuture` 不是 `Future`，`tokio::spawn` 要包 `async move { .. .await }`。
- server 的 `JoinHandle` 必须 await 或 abort，不让 server 活过测试（ASYNC-04）。0.6 的 `axum::Server::bind` 仍在测试里出现 = 迁移债务。

## 状态注入：假实现还是真库（AX-50）

| 被测对象 | 做法 | 不要 |
|---|---|---|
| handler 编排 / 错误映射 | `AppState` 字段是 `Arc<dyn UserRepo>` 等 I/O 端口，测试塞内存假实现 | 为测试把每个纯函数都 trait 化（SIMP-01；mock 只打 I/O 端口） |
| SQL 正确性 | `#[sqlx::test(migrations = "./migrations")] async fn t(pool: PgPool)` → `app(AppState::new(pool))`，每个测试独立库（SX-12） | 单测里 mock `PgPool`（mock 不了，也测不到 SQL） |
| 领域 parse / 不变式 | 普通 `#[test]` 直接调 `Email::parse`（API-08） | 经 HTTP 绕一圈测纯函数 |
| 出站 HTTP（AX-17） | state 里的 `reqwest::Client` 指向 wiremock/httpmock 起的本地地址 | 生产代码里 `#[cfg(test)]` 分支换实现 |

缺 `DATABASE_URL` 时 `#[sqlx::test]` 自然 panic，这就是 fail-loud（TEST-07）；禁止 `if env::var(..).is_err() { return }` 变绿。

## WebSocket / SSE（AX-51）

- SSE 用 oneshot 就能测：响应 body 是无限流，禁止 `to_bytes`/`collect` 全量收（永不结束 = 测试挂死）。`BodyExt::into_data_stream()` 取前 N 帧，每次 `next()` 包 `tokio::time::timeout`；断言 `content-type: text/event-stream` 与首帧 `data:` 格式。
- WebSocket：axum-test 开 `ws` feature + `.http_transport()`，`server.get_websocket("/ws").await.into_websocket().await` 得 `TestWebSocket`（`send_text`/`receive_json::<T>`/`assert_receive_text`/`close`）；或真 listener + `tokio-tungstenite`。每个 `receive_*` 包 timeout，否则对端不回就是无限挂。
- 这两类测试顺带验证 AX-04：SSE/WS 路由不被整树 `TimeoutLayer` 掐断，而普通 JSON 路由越过超时应得 408。

## tokio 运行时与时间（TEST-09、AX-51）

- `#[tokio::test]` 默认 current_thread：handler 里 `std::thread::sleep`/同步 IO 会让整个测试卡死——这是优点，顺手暴露 AX-08/ASYNC-03 违规；禁止为了「跑通」改 `flavor = "multi_thread"` 把问题盖住。
- 超时/重试/限流用 `#[tokio::test(start_paused = true)]`（tokio `test-util` feature）+ `tokio::time::advance`，禁止真 sleep。paused 时钟只在 current_thread 可用，且 runtime 一空闲就自动推进，真 socket 等待会让超时提前触发——真 listener 测试不开 paused。
- 等事件不等时间：停机测试 await JoinHandle 并包 timeout，不 `sleep(100ms)` 赌任务结束。

```rust
// ✓ 不花 30s 验证 TimeoutLayer（AX-04）
#[tokio::test(start_paused = true)]
async fn slow_route_times_out() {
    let res = app(test_state()) // /slow 内部 tokio::time::sleep(30s)
        .oneshot(Request::get("/slow").body(Body::empty()).unwrap())
        .await.unwrap();
    assert_eq!(res.status(), StatusCode::REQUEST_TIMEOUT); // 虚拟时钟自动推进
}
```

## 布局与配比（AX-50）

- handler 单测靠近 handler：`#[cfg(test)] mod tests` 或同模块 `tests.rs`（TEST-01）；HTTP 契约测试合并进一个二进制 `tests/it/main.rs` + 子模块，每多一个 `tests/*.rs` 多一次链接（TEST-02）；共享夹具 `tests/it/common.rs` 或 test-util crate，禁 `tests/common.rs`（TEST-03）。
- 配比（TEST-10）：领域 parse/服务方法 = 大量纯单测，不碰 HTTP；每条路由至少一条 oneshot/TestServer 契约测试（状态码 + body 形状 + 错误映射）；`#[sqlx::test]` 适量；真 listener 仅停机/WS。
- 每个 `AppError` 变体一条测试：状态码、对外 body 不含内部细节、5xx 带 request-id（AX-12）；缺/过期 token → 401，角色不够 → 403（AX-15）；超过 `DefaultBodyLimit` → 413（AX-05）；0.8 路由 `{id}` 与 `Path<T>` 对得上（AX-18）。
- insta 快照响应 JSON 要人审 diff（TEST-11）；id/时间戳先 redact，否则每次都红。

## API 评审清单（只读；`/rust-skills:rust review` 与 `audit security` 有 axum 证据时叠加）

先从 `Cargo.toml` 定 axum 线（0.8 / 0.7 / 未钉），再按顺序过；每条发现给位置 + 代码证据 + 可观察后果，映射到规则号。级别沿用 M/S/Y：编译不过、启动 panic、已证实安全洞一律 M；拿不准取更高级别。

| 顺序 | 看什么 | 典型缺陷（症状） | 规则 |
|---|---|---|---|
| 1 路由 | 路径语法对版本；`.route()` 全在 `.layer()` 之前；`.merge()` 不出现双 fallback | 0.8 仓 `/users/:id` → Router 构建时 panic；`.layer()` 之后再 `.route()` 的路由不被包裹；两个 fallback → 构建 panic | AX-18；见 middleware.md |
| 2 extractor | 消费 body 的 extractor 唯一且最后；`Option<Path<T>>` 按 0.8 语义（不再吞错） | `Json<T>` 放第一个参数 → `Handler` bound 不满足；指望 `Option<Path>` 兜底，0.8 直接拒绝 | AX-13 |
| 3 handler | 返回 `IntoResponse`；future `Send`（无 `Rc`/`RefCell`/std guard 跨 await）；≤16 参数 | `-> i32`；`MutexGuard` 跨 await 报错巨长——`#[debug_handler]` 定位 | AX-26、AX-03、ASYNC-02 |
| 4 中间件 | 多次 `.layer()` 自下而上包裹，`ServiceBuilder` 自上而下；鉴权用 `route_layer`；`from_fn` 的 `Next` 是最后参数 | 鉴权挂 `.layer()` → 404 变 401 泄露路由存在；顺序反了 trace 看不到 auth 拒绝 | AX-15；见 middleware.md |
| 5 状态 | `State` + `FromRef` 收窄；廉价 clone；跨 await 可变先重构再 tokio Mutex | `Extension<Config>` 缺了运行时 500；`Arc<Pool>` 双包 | AX-01、AX-02、ASYNC-02 |
| 6 错误 | handler 无 `unwrap`/`expect`；具名错误 enum + `IntoResponse`；`From` 接 `?`；默认 rejection 不泄内部 | `.unwrap()` 把可恢复错误变成 panic 的请求任务；散落的裸 `StatusCode` 返回 | AX-12、ERR-01、ERR-03 |
| 7 鉴权 | secret 来自环境；`Claims` 有 `exp`；`FromRequestParts` extractor；授权按权限非角色串；CORS 精确白名单 | 源码字面 secret；永不过期 token；`CorsLayer::permissive()` 上线 | AX-15、SH-05；细表见 [auth.md](auth.md) |
| 8 数据层 | 池在 main 建一次；`acquire_timeout`/`max_connections` 显式；事务 drop 回滚或显式 commit | handler 里 `PgPool::connect` 每请求建池 | AX-02、SX-02、SX-07 |
| 9 性能 | handler/WS 任务无阻塞、无重 CPU；body 上限有硬顶 | `std::thread::sleep`、同步文件 IO；`DefaultBodyLimit::disable()` 却没有 `RequestBodyLimitLayer` | AX-05、AX-08、ASYNC-03 |
| 10 部署 | `with_graceful_shutdown` 且信号含 SIGTERM；停机关池、flush tracing；容器绑 `0.0.0.0`；配置来自环境；`Span::enter` guard 不跨 await | 只 `ctrl_c()` → 滚动更新丢请求；绑 `127.0.0.1` 容器外不可达 | AX-06、AX-34、SH-03、SH-04、SH-05 |

评审产出只检测与路由到规则，不在发现里重写修法；零发现也要写「已过 10 项，目标版本 X，未发现」。

## 验证

- `cargo test -p <crate>`：契约测试全绿且无静默跳过；需要真库的用例带 `#[ignore = "needs DATABASE_URL"]`，在有库的 CI job 单独 `cargo test -- --ignored`。
- 改了超时/限流/停机：对应的 `start_paused` 测试或真 listener 停机测试必须存在并见过红（TEST-08）。
- 性能类改动仍走 [../axum.md](../axum.md) 的 oha/wrk 同机对比（PERF-01）；单测不是压测。
