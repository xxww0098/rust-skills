# axum/routing — 路由组合与匹配语义

目的：代码里出现 `nest`/`merge`/`fallback`/`route_service`/`nest_service`、`Router<S>` 泛型报错（`Handler<_, ()>`）、启动即 panic（`Overlapping method route` / `Invalid route` / `Cannot merge` / `Nesting at the root`）、404 与 405 混淆、或要按领域拆路由模块时加载。只讲 `Router` 的组合与匹配；0.7→0.8 路径语法见 AX-18，state 设计见 AX-01，`layer`/`route_layer` 次序与 `NormalizePathLayer` 见 [middleware.md](middleware.md)，`MatchedPath` 做 span 标签见 [observability.md](observability.md)，oneshot 写法见 [testing.md](testing.md)。

## 组合原语与匹配优先级

| 需求 | 用 | 要点 |
|---|---|---|
| 一条路径 → handler | `.route(p, get(a).post(b))` | 同路径再次 `.route` 会合并 MethodRouter；同路径同方法两次 → panic |
| 一条路径 → 裸 `tower::Service` | `.route_service(p, svc)` | 传 `Router` 进去 panic，改 `nest` |
| 子 Router 挂前缀（前缀被剥掉） | `.nest(prefix, router)` | 子路径写相对路径；两边 `S` 相同 |
| `tower::Service` 挂前缀 | `.nest_service(prefix, svc)` | `ServeDir` 等；实际注册 `prefix`、`prefix/`、`prefix/{*rest}` 三条 |
| 同级平铺、不加前缀 | `.merge(other)` | 两边 `S` 相同；想「挂在根」就用它，`nest("/")` 是 panic |
| 无路由命中 | `.fallback(h)` / `.fallback_service(svc)` | 真 404；SPA 用 `fallback_service(ServeDir::new(dir).not_found_service(ServeFile::new(index)))` |
| 路径命中、方法不对 | `.method_not_allowed_fallback(h)` `// axum 0.7.8+` | 0.7.8 之前只能逐路径 `get(h).fallback(h405)` |

1. 注册顺序对匹配**无影响**（matchit 基数树，AX-23）：静态段 > `{x}` > `{*rest}`。`/users/me` 与 `/users/{id}` 共存且前者胜，不存在「把通配放最后」这回事。顺序只影响 `layer`/`route_layer`/`method_not_allowed_fallback`——它们只覆盖**调用之前**已注册的路由。
2. `any(h)` 的实现就是 MethodRouter 的 fallback：`any(h).get(g)` 合法（GET 走 g，其余走 h），且该路径永不返回 405。
3. `on(MethodFilter::GET.or(MethodFilter::POST), h)` 做方法子集；`connect`/`MethodFilter::CONNECT` 自 0.7.8 起可用（0.7.0–0.7.7 无）。`get` 自动应答 HEAD（去 body），不要再挂 `head(h)`。
4. `{*rest}` 不匹配空段：`/files` 不命中 `/files/{*rest}`，要单独 `.route("/files", …)`。字面花括号写 `{{`/`}}`（0.8）。

## 启动 panic 还是静默不匹配（AX-25）

所有路由错误都在 `Router` 构造期触发，不在请求期——一个构造 Router 的单测就兜住下表全部 panic 行；反过来，把 Router 构造放进请求路径会把这些 panic 变成线上 500。

| 写法 | 0.7 | 0.8 | 结果 |
|---|---|---|---|
| `"/users/:id"`、`"/f/*rest"` | 捕获 | ``Path segments must not start with `:`. For capture groups, use `{capture}`. … call `without_v07_checks` on the router.``（`*` 同款，提示 `{*wildcard}`） | 0.8 启动 panic（AX-18） |
| `"/users/{id}"` | 字面段 `{id}`，永不命中 | 捕获 | 0.7 静默 404 |
| `.without_v07_checks().route("/a/:id", …)` | 无此方法 | `:id` 是字面段，不是捕获 | 静默不匹配；只为真要字面 `:`/`*` 时用 |
| `.route("", …)` | ``Paths must start with a `/`. Use "/" for root routes`` | 同 | 启动 panic |
| `.route("users", …)` | ``Paths must start with a `/` `` | 同 | 启动 panic |
| `.route("/x", get(a)).route("/x", get(b))`；merge/nest 展开后同路径同方法亦同 | ``Overlapping method route. Handler for `GET /x` already exists`` | 同 | 启动 panic |
| `get(a).get(b)` | ``Overlapping method route. Cannot add two method routes that both handle `GET` `` | 同 | 启动 panic |
| `/items/{id}` 与 `/items/{slug}` | `Invalid route "/items/{slug}": insertion failed due to conflict with previously registered route: /items/{id}` | 同，仅 `Insertion` 首字母大写 | 启动 panic |
| `/users/me` 与 `/users/{id}` | 合法，静态胜 | 同 | — |
| `.nest("", r)`、`.nest("/", r)` | `Nesting at the root is no longer supported. Use merge instead.` | 同 | 启动 panic |
| `.nest_service("/", svc)` | `Nesting at the root is no longer supported. Use fallback_service instead.` | 同 | 启动 panic |
| `.nest("/files/{*rest}", r)` | `Invalid route: nested routes cannot contain wildcards (*)` | 同 | 启动 panic |
| `.route("/api/users", get(a)).nest("/api", r)`，r 含 `/users` 的 GET | 展开为 `/api/users` → ``Overlapping method route. Handler for `GET /api/users` already exists`` | 同 | 启动 panic |
| `.route("/api/{id}", …).nest("/api", r)`，r 含 `/{slug}` | 展开后同位置异名捕获 → `insertion failed due to conflict …` | 同 | 启动 panic |
| `a.fallback(x).merge(b.fallback(y))` | ``Cannot merge two `Router`s that both have a fallback`` | 同；0.8.4+ 可 `b.reset_fallback()` | 启动 panic |
| `.route_service("/sub", Router)` | ``Invalid route: `Router::route_service` cannot be used with `Router`s. Use `Router::nest` instead`` | 同 | 启动 panic |
| `.route_layer(l)` 在任何 route 之前 | `Adding a route_layer before any routes is a no-op. Add the routes you want the layer to apply to first.` | 同 | 启动 panic |
| `.nest("/api/", r)`（尾斜杠） | 只注册 `/api/…`；`/api` 本身 404 | 同 | 静默 |
| `.nest("/api", r)`，r 含 `/` | 命中 `/api`，`/api/` 404 | 同 | 静默 |
| `GET /files` 对 `/files/{*rest}` | 404 | 同 | 静默 |
| `GET /users/` 对 `/users/{id}` | 404 | 同（尾部空段不捕获） | 静默 |

## 404 与 405（AX-24）

路径命中但方法未注册 → MethodRouter 自己回 405 并带 `Allow` 头，**永远不进 `Router::fallback`**。两套 fallback 各管各的：

```rust
// ✗ 以为 POST /users 会进 not_found；实际 405，not_found 从未被调用
Router::new().route("/users", get(list)).fallback(not_found);

// ✓ axum 0.7.8+：404 与 405 分开接；放在所有 route/nest/merge 之后，否则后注册的路由拿不到
Router::new()
    .route("/users", get(list))
    .nest("/api", api)
    .fallback(not_found)                        // 无路由命中
    .method_not_allowed_fallback(wrong_method)  // 路径命中、方法不对；nest 进来的路由一并覆盖

// ✓ 0.7.8 之前或单路径定制：MethodRouter::fallback
Router::new().route("/users", get(list).fallback(wrong_method));
```

`any(h)` 路径不会 405，`method_not_allowed_fallback` 也不会覆盖它（其 fallback 已非默认）。404/405 的响应体走 AX-12 的 `IntoResponse` enum，handler 里不要再手拼 JSON。

## nest 的真实语义与尾斜杠（AX-25）

1. `nest` 是**展开**不是代理：子路由按 `prefix + 子路径` 逐条插进父树，每条端点套 `StripPrefix`。子路由冲突、`layer` 覆盖范围、`method_not_allowed_fallback` 都按展开后的完整路径算：子 Router 在 nest 前调的 `.layer()` 只包子路由，父 Router 在 nest 后调的 `.layer()` 也包它们。
2. 前缀不写尾斜杠。`nest("/api", r)` 里子路由 `/` 对应 `/api`（`/api/` 404）；`nest("/api/", r)` 只有 `/api/…`。`nest_service` 例外：前缀不带尾斜杠时显式注册 `prefix`、`prefix/`、`prefix/{*rest}` 三条，带不带斜杠都命中；`nest_service("/static/", …)` 只注册 `/static/` 与 `/static/{*rest}`，`/static` 仍 404。
3. 前缀可含单段捕获：`nest("/{tenant}", r)` 后子路由 `Path<(String, u32)>` 连着取；不可含 `{*rest}`（panic）。
4. 尾斜杠归一化不能靠 `Router::layer`（路由匹配之后才跑，改 URI 不会重新匹配）；`NormalizePathLayer` 必须包在 Router 外再 `into_make_service`，写法见 [middleware.md](middleware.md)。
5. 同一前缀可 `nest` 多次，按路径合并；`nest_service(prefix, Router)` 能编译但失去 fallback 继承与冲突检查，子 Router 一律 `nest`。

## fallback 继承与 merge（AX-25）

```rust
let api = Router::new()
    .route("/users", get(list))
    .fallback(api_404);          // 只接 /api/** 下的未命中；必须在 nest 之前设
let app = Router::new()
    .nest("/api", api)
    .route("/", get(home))
    .fallback(site_404);         // 其余未命中；api 若没设 fallback，/api/** 也落到这里
```

1. 未设 fallback 的子 Router 继承外层 fallback；设了就只在自己前缀下生效，外层的不再进来。
2. `merge` 时最多一边有 fallback：`a.fallback(x).merge(b.fallback(y))` panic。0.8.4+ 用 `b.reset_fallback()`；更早版本把 fallback 从子路由工厂里拿掉，只在组合根设一次。
3. `merge` 后两边的同路径会合并 MethodRouter（`/x` 的 GET 与 POST 分在两个模块也能合），同路径同方法才 panic。
4. `fallback` handler 可以要 `State`（`Handler<T, S>`），不必为它单独 `with_state`。

## Router<S> 状态穿透与 with_state 顺序（AX-22）

```rust
// ✗ 子路由工厂返回 Router（= Router<()>），handler 却要 State<AppState>
//   E0277: the trait bound `fn(State<AppState>) -> … {list}: Handler<_, ()>` is not satisfied
pub fn users() -> Router {
    Router::new().route("/", get(list))
}

// ✓ 工厂保留 S；组合根统一 with_state，且放在所有 route/nest/merge 之后
pub fn users() -> Router<AppState> {
    Router::new()
        .route("/", get(list).post(create))
        .route("/{id}", get(show).delete(remove))
}
pub fn app(state: AppState) -> Router {
    Router::new()
        .nest("/api/v1/users", users())
        .merge(health::router())    // 也返回 Router<AppState>，哪怕它不碰 state
        .fallback(not_found)
        .method_not_allowed_fallback(wrong_method) // axum 0.7.8+
        .layer(TraceLayer::new_for_http())
        .with_state(state)          // Router<AppState> → Router<()>
}
```

1. `Handler<_, ()>` 报错里第二个泛型就是「被推成 `Router<()>`」的证据；改工厂返回类型，不要给 handler 换 `Extension` 绕过去（AX-01）。
2. `nest`/`merge` 要求两边 `S` 相同。`with_state` 返回 `Router<S2>`，`S2` 由调用处推断：已喂过状态的子路由可以 nest 进任何 `S` 的父路由（`nest("/admin", admin.with_state(AdminState::new()))` 合法）；反向——未喂状态的 `Router<AppState>` 进 `Router<()>`——不行。
3. `with_state` 之后再 `.route()` 一个要 `State` 的 handler，会推出新的 `Router<S3>` 要求再次 `with_state`，且那个 handler 拿不到前一份状态。`.layer()` 不改 `S`，放 `with_state` 前后皆可；`from_fn_with_state(state.clone(), f)` 直接持值，也与 `S` 无关。
4. `axum::serve` 只收 `Router<()>`：忘 `with_state` 是编译错，不是运行时惊喜。

## 一条请求里的四个路径（AX-33）

`nest("/api", Router::new().route("/users/{id}", get(h)))`，请求 `GET /api/users/42`：

| 提取器 | 值 | 用途 |
|---|---|---|
| `Uri`（`req.uri()`） | `/users/42` | nest 已剥前缀；别拿它拼日志、重定向或签名 |
| `OriginalUri` | `/api/users/42` | 原始路径（feature `original-uri`，默认开） |
| `MatchedPath` | `/api/users/{id}` | 低基数路由模板：metrics/trace 标签只用它（AX-11）；fallback 里不可用 |
| `NestedPath` | `/api` | 子路由里拼绝对 URL，不硬编码前缀 |
| `Path<u32>` | `42` | 捕获值；nest 前缀里的捕获也在同一个 `Path` 元组里 |

## 按领域拆模块

1. 每个领域 `mod` 暴露一个 `pub fn router() -> Router<AppState>`，路径写相对路径，不知道自己会被挂在哪。版本前缀、鉴权 `route_layer`、fallback、`with_state`、全局 `layer` 只在组合根出现一次；子模块里出现 `.with_state`/`.layer(TraceLayer…)` 就是分层漏了。
2. 不需要前缀的（`/healthz`、`/metrics`）用 `merge`；需要前缀的用 `nest`。`merge` 进来的 `/healthz` 与 `nest("/api")` 下的路由互不影响。
3. 拆分依据是变化原因（WS-11），不是行数；一个 `users.rs` 里 6 条路由加 handler 完全正常。路由与 handler 同文件，跨模块只共享 `AppState` 与错误类型。

## 验证

```rust
#[tokio::test]
async fn router_builds_and_405() {
    use tower::ServiceExt;
    let app = app(AppState::for_test());              // 构造即覆盖全部路由冲突 panic
    let req = Request::builder().method("POST").uri("/api/v1/users/1").body(Body::empty()).unwrap();
    let res = app.oneshot(req).await.unwrap();
    assert_eq!(res.status(), StatusCode::METHOD_NOT_ALLOWED);
    assert!(res.headers().contains_key(header::ALLOW));
}
```

一条构造测试加几条 `oneshot`（404 对 405、nest 前缀本身、尾斜杠）就够，不起服务器（TEST-10；写法见 [testing.md](testing.md)）。升级 0.7→0.8 前 `rg -n '"[^"]*/[:*][A-Za-z_]' src/` 列出所有要改花括号的路径，再跑构造测试确认无 panic（AX-52）。
