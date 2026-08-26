# axum/handlers — Handler 与响应：签名规则、IntoResponse、错误模型与 Handler trait 报错分诊

目的：用户贴出 `the trait bound … Handler<_, _> is not satisfied`、问「handler 怎么同时返回状态码/header/cookie」、或代码里出现 `impl IntoResponse for`、`Result<_, AppError>`、`HandleErrorLayer` 时加载。只展开 [../axum.md](../axum.md) 的 AX-12/AX-13/AX-14，不复述清单：状态与 `FromRef` 见 AX-01，鉴权 extractor 见 [auth.md](auth.md)，超时与流式见 AX-04/AX-07，锁跨 await 的原理见 [../async.md](../async.md)。

## Handler 资格：blanket impl 的全部条件

函数不靠宏注册，靠满足 `Handler<T, S>` 唯一的 blanket impl；缺任何一条，rustc 只报「整条 impl 不满足」，不说是哪条。0.7 与 0.8 条件相同。

1. 写成 `async fn`。trait 本身只要求 `FnOnce(..) -> Fut` 且 `Fut: Future + Send`，同步 fn 返回 `Send` future 也能过（`#[debug_handler]` 同样只检查返回值 `Future + Send`，不额外拒绝）——仍统一 `async fn`，同步重活在体内 `spawn_blocking`（AX-08）。
2. 参数 ≤ 16 个且全是 extractor：前面的全部实现 `FromRequestParts<S>`，只有**最后一个**可以是消费 body 的 `FromRequest<S>`（`Json`/`Form`/`Bytes`/`String`/`Multipart`/`Request`）（AX-13）。`bool`/`i32`/领域 struct/配置对象都不是 extractor；不是请求数据的值进 `State`（AX-01）。
3. 返回类型实现 `IntoResponse`；`Result<T, E>` 要 `T`、`E` 都实现。`anyhow::Error`/`std::io::Error`/`Box<dyn Error>` 都不实现，孤儿规则也不让你补——必须包进自有类型（见「错误模型」）。
4. 返回的 future `Send + 'static`：`std::sync::MutexGuard`/`Rc`/`RefCell` borrow 跨 `.await` 即 `!Send`（ASYNC-02）。
5. 闭包 handler 额外要 `Clone + Send + 'static`（axum 每请求 clone 一次 handler）：捕获局部借用或 `Rc` 直接失败。闭包只适合一行 demo；要共享状态用 `State`，不要 `move || { let pool = pool.clone(); async move { … } }` 套娃。
6. 超过 16 个参数没有 impl：`#[derive(FromRequestParts)]` 把相关 extractor 打包成一个 struct（每个字段都是 extractor，0.7/0.8 都免写 `#[async_trait]`）。逼近上限本身说明 handler 太厚（AX-14）。

```rust
// ✗ 一次踩四条：非 extractor 参数、body extractor 不在末尾、返回裸 struct、guard 跨 await
async fn create(flag: bool, Json(p): Json<NewUser>, Path(team): Path<u64>,
                State(stats): State<Arc<Mutex<Stats>>>) -> User {
    let mut g = stats.lock().unwrap();
    let u = insert(team, p).await;          // g 仍活着 → future !Send
    g.created += 1;
    u
}

// ✓ parts extractor 在前，唯一 body extractor 在末尾；两臂都实现 IntoResponse
async fn create(State(app): State<Arc<App>>, Path(team): Path<u64>,
                Json(p): Json<NewUser>) -> Result<(StatusCode, Json<User>), AppError> {
    let u = app.repo.insert(team, p).await?;
    app.stats.lock().unwrap().created += 1;  // guard 在语句末 drop，不跨 await（AX-03）
    Ok((StatusCode::CREATED, Json(u)))
}
```

## 『Handler is not satisfied』分诊（AX-26）

第一步永远是 `#[debug_handler]`（`axum = { version = "0.8", features = ["macros"] }`，`use axum::debug_handler`）：宏为每个条件生成独立检查项，把失败钉到具体参数或返回类型的 span；release profile 下是空操作，留着无成本。错误块里 `help: the following other types implement trait Handler` 列出的 `MethodRouter`/`Layered` 与故障无关，错误 span 落在 `.route()`/`get()` 也不是路由写错——故障永远在 handler 形状。`middleware::from_fn` 的函数同理用 `#[debug_middleware]`（0.8 新增）。

| 编译器原文片段（加宏后） | 根因 | 修法 |
|---|---|---|
| `the trait FromRequestParts<S> is not implemented for bool`，span 指向某个参数 | 非 extractor 参数 | 从请求读：`Query`/`Path`/`Json`/自定义 extractor；非请求数据进 `State` |
| 内置 body 类型（`Json`/`Form`/`Bytes`/`String`/`Multipart`/`Request`）报 `` `Json<_>` consumes the request body and thus must be the last argument to the handler function ``；两个则 `Can't have two extractors that consume the request body.`；自定义 `FromRequest` 类型宏认不出，只报 `FromRequestParts<S> is not implemented for X` | body extractor 不在末尾，或有两个 body extractor | 移到末尾、只留一个；要两种解析就收 `Bytes`/`Request` 自己解析（AX-13） |
| `the trait IntoResponse is not implemented for User` / `… for anyhow::Error`，span 指向返回类型 | 返回类型或 `Result` 的 `E` 不实现 `IntoResponse` | 包 `Json(..)`；错误用自有 `AppError` + `impl IntoResponse` |
| `future cannot be sent between threads safely` + `note: … MutexGuard … held across an await` | `!Send` future | 缩小 guard 作用域让它在 await 前 drop；真要跨 await 才换 `tokio::sync::Mutex`（D-3） |
| 不加宏时原文是 `Handler<_, Arc<AppState>> is not satisfied`（第二个泛型参数已是具体类型） | handler 的 `State<T>` 与 `Router<S>` 的 `S` 不一致：要的是 `T: FromRef<S>`，而 `#[derive(FromRef)]` 只生成 `FromRef<AppState>` | `S` 是 `Router` 的状态类型：`Router<Arc<AppState>>` 下手写 `impl FromRef<Arc<AppState>> for T`（AX-22），或统一成 `Router<AppState>`/`State<Arc<AppState>>`；用 `#[debug_handler(state = Arc<AppState>)]` 让宏按真实 `S` 检查（宏默认从 `State<T>` 参数推断） |
| `FromRequestParts<S> is not implemented for Option<MyExtractor>` | axum 0.8 的 `Option<T>` 改走 `OptionalFromRequestParts`/`OptionalFromRequest` | 给自定义 extractor 补 `OptionalFromRequestParts`，或参数改 `Result<T, T::Rejection>` |
| ``Handlers must be `async fn`s``（同步 `fn` 且无返回类型；0.7 的 axum-macros 0.4 是 `handlers must be async functions`），或 `` `&str` is not a future``（同步 `fn` 返回值不是 future） | 非 `async fn` | 改 `async fn`（返回 `impl Future + Send` 的同步 fn 宏与 blanket impl 都收，但不要靠这个） |
| 宏报参数超过 16 个 | 参数太多 | `#[derive(FromRequestParts)]` 打包 |
| `error[E0425]: cannot find function __axum_macros_check_handler_0_from_request_check` | 宏放在 `impl` 块里无 `self` 的关联函数上 | 宏的限制，不是 handler 错误：抽成自由函数 |

## 响应：IntoResponse 与元组规则（AX-27）

| 返回 | 结果 |
|---|---|
| `()` / `StatusCode` / `NoContent` | 空体 200 / 该状态空体 / 204 |
| `&'static str`、`String`、`Cow<'static, str>` | 200，`text/plain; charset=utf-8` |
| `Vec<u8>`、`Bytes`、`&'static [u8]` | 200，`application/octet-stream`；要别的类型前置 `[(CONTENT_TYPE, "application/pdf")]` |
| `Json<T: Serialize>` / `Html<T: Into<Body>>` / `Form<T: Serialize>` | 200 + 对应 content-type；`Json` 序列化失败自动 500 |
| `Redirect::to` / `::temporary` / `::permanent` | **303 / 307 / 308**。没有 301/302 构造器（二者允许客户端把 POST 改写成 GET）；测试断言 302 必失败 |
| `(StatusCode, parts…, body)` | `StatusCode` 必须第一；中间每个元素实现 `IntoResponseParts`（`HeaderMap`、`[(HeaderName, V); N]`、`AppendHeaders`、`Extension`、`CookieJar`）；body 最后且只有一个 |
| `Result<T, E>` | 两臂各自 `into_response`，状态由臂决定 |
| `Response` | 完全手工；0.8 的 body 类型只能是 `axum::body::Body`（`hyper::Body` 不再导出） |

1. `impl IntoResponse` 返回位置只能是一种具体类型：分支分别返回 `Json(..)` 与 `Html(..)` 报 mismatched types。改返回 `Response`，每个分支 `.into_response()`。
2. header 数组与 `HeaderMap` 对同名 header 是 **insert 覆盖**；多条 `Set-Cookie` 必须 `AppendHeaders`。
3. `Response::builder()…body(Body::from(..))` 返回 `Result`，只有全静态 header 才允许 `expect("invariant: static headers")`（ERR-03）；默认用元组，builder 留给要改 `version`/extensions 的场合。
4. 大响应 `Body::from_stream(s)`（`s: TryStream + Send + 'static`，`Ok: Into<Bytes>`，`Error: Into<BoxError>`）或 `Sse`，文件走 `tokio_util::io::ReaderStream`；不在内存拼完整 `Vec`（AX-07）。
5. axum 核心没有 cookie API；`axum-extra` feature `cookie` / `cookie-signed` / `cookie-private`。`CookieJar::add/remove` **消费 self 返回新 jar**，不把 jar 放进返回元组就没有 `Set-Cookie`——编译不报错。session id 用 `PrivateCookieJar`（`Key` 放 state 经 `FromRef` 取），明文 `CookieJar` 只放主题/语言这类非敏感值（AX-15）。

```rust
// ✗ 三个 bug：body 不在末尾（不编译）；jar 改了没返回；两条 Set-Cookie 用数组只剩一条
async fn login(jar: CookieJar) -> (Json<Value>, StatusCode) {
    jar.add(Cookie::new("session", "abc"));
    ([(SET_COOKIE, "a=1"), (SET_COOKIE, "b=2")], Json(json!({})), StatusCode::OK)
}

// ✓ 状态第一、parts 居中、body 最后；jar 回流
async fn login(jar: CookieJar) -> (StatusCode, CookieJar, Json<Value>) {
    let jar = jar.add(Cookie::build(("session", "abc")).http_only(true).secure(true)
        .same_site(SameSite::Lax).path("/").build());
    (StatusCode::CREATED, jar, Json(json!({ "ok": true })))
}

// ✓ 分支类型不同 → 返回 Response
async fn show(Path(id): Path<u64>, State(app): State<Arc<App>>) -> Result<Response, AppError> {
    let u = app.repo.get(id).await?;
    Ok(if app.wants_html { Html(render(&u)).into_response() } else { Json(u).into_response() })
}
```

## 不可失败 handler 与错误模型

axum 的 service 错误类型是 `Infallible`：handler 永远产出响应，失败只以「实现了 `IntoResponse` 的值」存在——extractor 的 `Rejection`、`Result` 的 `E` 都受 `: IntoResponse` 约束。这就是 `?` 能用的原因。

1. 形状：`Result<T, AppError>` + `impl IntoResponse for AppError` + `From<Source> for AppError`（thiserror `#[from]` 或手写），handler 里只写 `?`；状态码映射集中在 `into_response` 一处（AX-12），禁止各 handler 自行 `map_err(|_| StatusCode::X)` 把信息丢光。
2. 两种 `AppError`（ERR-08：项目已有 anyhow 或 thiserror 哪个就沿用，不为它同时引两个）：

| 形状 | 适用 | 代价 |
|---|---|---|
| `struct AppError(anyhow::Error)` + `impl<E: Into<anyhow::Error>> From<E> for AppError` | 原型、内部工具、所有失败都是 500 | 分不出 404/409/422；客户端只见 500 |
| 具名 enum：`NotFound`、`Conflict`、`Validation(..)`、`Internal(#[from] anyhow::Error)`（无 anyhow 则 `Box<dyn Error + Send + Sync>`） | 对外 API、客户端按错误分支 | 每个 source 一条 `From`；`#[non_exhaustive]`（ERR-06） |

3. 对外不泄内部：5xx 响应体固定为通用文案 + 稳定错误码，真实 `Display`/source 链只进 `tracing::error!`，且只记一次（OBS-03：这里记了 handler 就别记，AX-11）；request-id 由 `SetRequestIdLayer` + `PropagateRequestIdLayer` 写回响应 header，客户端拿它报障。4xx 可带面向用户的 message，但禁止 `format!("{err:?}")` 把 SQL、路径、内部类型名吐出去。
4. 错误体形状全 API 一致（`{"error": {"code": "…", "message": "…"}}` 或 RFC 7807 `application/problem+json`），并与 extractor rejection 的体一致，否则客户端要解析两套。

```rust
// ✗ 内部错误原文直出；每个 handler 自己猜状态码
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        (StatusCode::INTERNAL_SERVER_ERROR, format!("error: {:?}", self.0)).into_response()
    }
}

// ✓ 集中映射；5xx 只记日志不回显；体形状统一
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum AppError {
    #[error("not found")]  NotFound,
    #[error("{0}")]        Validation(String),
    #[error(transparent)]  Db(#[from] sqlx::Error),
    #[error(transparent)]  Internal(#[from] anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, code, msg) = match &self {
            Self::NotFound | Self::Db(sqlx::Error::RowNotFound) =>
                (StatusCode::NOT_FOUND, "not_found", "not found".to_owned()),
            Self::Validation(m) => (StatusCode::UNPROCESSABLE_ENTITY, "validation", m.clone()),
            Self::Db(_) | Self::Internal(_) => {
                tracing::error!(error = ?self, "request failed");   // 唯一记录点（OBS-03）
                (StatusCode::INTERNAL_SERVER_ERROR, "internal", "internal error".to_owned())
            }
        };
        (status, Json(json!({ "error": { "code": code, "message": msg } }))).into_response()
    }
}
```

5. extractor 失败默认是纯文本 + 各自正确的状态（415/400/422/413，AX-20），与上面的错误体形状不一致时客户端要解析两套：按 [extractors.md](extractors.md) 的同名 newtype / `WithRejection` 方案把 rejection 收进 `AppError`，并按 AX-19 审 0.8 的 `Option<Extractor>`——机制此处不重复。
6. `HandleErrorLayer` 只给**会失败的 tower service**（AX-31）：`Router::layer` 要求 service 错误为 `Infallible`，`tower::timeout`/`load_shed`/`buffer`/限流这类返回 `BoxError` 的 layer 必须被 `HandleErrorLayer` 包住，且在 `ServiceBuilder` 里写在被包 layer **之前**（外层）。tower-http 的 `TimeoutLayer`（AX-04 用的那个）自己回 408、是 infallible 的，不需要；handler 错误与 extractor 失败也不走它——那是 `IntoResponse` 的事。

```rust
// ✓ HandleErrorLayer 在外层，只翻译 fallible layer 的 BoxError
.layer(ServiceBuilder::new()
    .layer(HandleErrorLayer::new(|e: BoxError| async move {
        if e.is::<tower::load_shed::error::Overloaded>() { StatusCode::SERVICE_UNAVAILABLE }
        else { StatusCode::INTERNAL_SERVER_ERROR }
    }))
    .load_shed()
    .concurrency_limit(1024))
```

## 验证

- 编译层：报错先 `#[debug_handler]`；修完可留（release 无成本），或 `#[cfg_attr(debug_assertions, axum::debug_handler)]`。
- 契约测试用 `tower::ServiceExt::oneshot` 免起服务器（TEST-10）：每个 `AppError` 变体一条用例断言 status + 体内 `code`；5xx 用例断言体内**不含**内部错误文本（`assert!(!body.contains("sqlx"))`）；`Redirect` 断言 303/307/308；cookie 用例断言 `Set-Cookie` 条数与 `HttpOnly; Secure` 属性；`Json` 发 `text/plain` 断言 415 而不是 400。
- 错误体形状用 insta 快照锁定（TEST-11），改动走 diff 人审。
