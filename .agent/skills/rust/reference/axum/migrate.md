# axum/migrate — 0.7 → 0.8 迁移矩阵

目的：`Cargo.toml` 里 `axum = "0.7"` 要升 `"0.8"`、升完启动即 panic 或 `cargo build` 成片报错、或要判断一段代码/示例针对哪条版本线时加载。只给破坏性变更矩阵、检测命令与有序迁移步骤；规则本体在别处：路径语法与 panic 表见 AX-18 与 [routing.md](routing.md)，`Option<T>` 与自定义 extractor 见 [extractors.md](extractors.md)，WebSocket `Message` 见 [realtime.md](realtime.md)，`MatchedPath` 标签见 [observability.md](observability.md)。0.8.0 发布于 2024 年 12 月末，现行 0.8.x；0.6 及更早只做债务识别（末节）。

## 先判版本

| 证据 | 结论 |
|---|---|
| 路由串含 `/:id`、`/*rest`；extractor impl 顶着 `#[async_trait]`；`Message::Text(String)`、`socket.close()` | 0.7 |
| 路由串含 `/{id}`、`/{*rest}`；`OptionalFromRequestParts`；`Utf8Bytes`；`without_v07_checks` | 0.8 |
| `axum::Server::bind`、`Router<S, B>`、`Next<B>`、`hyper::Body`、`axum::TypedHeader` | 0.6 债务 |
| `axum::serve(listener, app)`、`into_make_service()`、`NestedPath`、无泛型 `Next` | 0.7 与 0.8 相同，**不能**据此判版本 |

反向错误同样致命：0.8 语法写进 0.7 仓，`"/users/{id}"` 是字面段，不 panic、永远 404。

## 破坏性变更矩阵（AX-19、AX-52）

症状分三类：**panic** = 编译通过、`Router` 构造时 panic（整棵树不起，不是单条路由）；**编译** = `cargo build` 失败；**静默** = 编译通过、运行时行为改变——没有任何报错，审计优先级最高。检测列对应下节编号。

| 变更 | 0.7 写法 | 0.8 写法 | 症状 | 检测 |
|---|---|---|---|---|
| 路径捕获（matchit 0.8，AX-18） | `"/users/:id"`、`"/f/*path"` | `"/users/{id}"`、`"/f/{*path}"`；字面花括号双写 `{{`/`}}` | panic，信息含 `without_v07_checks` | ① |
| `nest`/`route_service`/axum-extra `#[typed_path]` 的路径 | 旧语法 | 新语法；nest 前缀仍禁止通配 | panic | ① |
| 真要字面 `:`/`*` 段 | 直接写 | `Router::new().without_v07_checks()` 再 `.route` | 拿它止血 = **静默** 404（`:id` 成字面段） | ① |
| `impl FromRequest(Parts)` | `#[async_trait]` 必须 | 删属性（RPITIT）；`axum::async_trait` 再导出已删 | 编译：签名不匹配 / unresolved import | ② |
| 实现了 `Optional*` 的类型：`Path`/`Json`/`Extension`/`Multipart`/`MatchedPath`，axum-extra 的 `TypedHeader`/`Host` | 任何失败 → `None` | 缺席 → `None`；在场但坏 → 400/415/422 | **静默** | ③ |
| `Option<自定义 extractor>`，以及 0.8 未实现 `Optional*` 的 `Query`/`Form`/`CookieJar`（`Query` 的 impl 在 0.8.0 发布前被 #3088 移除） | 可用 | 需 `T: OptionalFromRequestParts`/`OptionalFromRequest` | 编译：`FromRequestParts<_> is not implemented for Option<T>` | ③ |
| 元组 `Path<(A, B)>`（AX-19） | 与捕获数不等也放行 | 必须与 `{}` 个数相等，否则 500 | **静默**（该路由每个请求 500） | ④ |
| handler / service 的 `Sync` | 不要求 | `.route()`/`MethodRouter` 要求 `Sync` | 编译：`cannot be shared between threads safely`；先 `#[debug_handler]` 定位 | 编译驱动 |
| `Host` extractor | `axum::extract::Host` | `axum_extra::extract::Host`（axum-extra 0.10） | 编译：unresolved import | ⑤ |
| `axum::serve` 的 listener | 只收 `TcpListener` | `serve::Listener` trait：`TcpListener`/`UnixListener` 直传 | 无（调用形状不变） | — |
| `Serve::tcp_nodelay`、`WithGracefulShutdown::tcp_nodelay` | 有 | 删；`serve::ListenerExt::tap_io` 在 listener 上设 | 编译；漏补 = 延迟静默回升 | ⑥ |
| `IncomingStream` | `IncomingStream<'a>` | `IncomingStream<'a, L>`；自定义 `Connected` impl 补 listener 泛型 | 编译 | ⑥ |
| WebSocket `Message::Text` | `String` | `Utf8Bytes`（deref 到 `str`） | 编译：`expected Utf8Bytes, found String`；`push_str` 等 `String` 方法消失 | ⑦ |
| `Binary`/`Ping`/`Pong`、`CloseFrame.reason`、`into_text()`/`into_data()` | `Vec<u8>`、`Cow<str>` | `Bytes`、`Utf8Bytes`，返回类型同步变 | 编译 | ⑦ |
| `WebSocket::close()` | 有 | 删；显式 `send(Message::Close(None))` | 编译 | ⑦ |
| `MatchedPath::as_str()` 的值 | `/users/:id` | `/users/{id}`（按注册模板原样返回） | **静默**：metrics 路由标签、span 名、告警/看板全换值 | ⑧ |
| `MethodFilter::CONNECT`、`routing::connect` | 无 | 新增；`any()` 含 CONNECT；WebSocket 可走 HTTP/2 扩展 CONNECT | 无 | — |
| `into_make_service()` | 传给 `serve` | 仍可用但多余：`serve(listener, app)` 直接收 `Router`；`ConnectInfo` 仍只能经 `into_make_service_with_connect_info::<SocketAddr>()` | 无 | ⑨ |
| MSRV | 1.66 | 1.75（RPITIT）；项目按 DEP-08 本就 ≥ 1.85，只在 CI 镜像钉旧版时撞 | 编译：`impl Trait` in trait 不稳定 | `rust-toolchain.toml` / CI 镜像 |

## 依赖对齐（AX-49）

一个依赖图里同时出现左右两列 = 两份 `Service`/`Layer`/`Router` 类型；报错是 `the trait Layer<Route> is not implemented` 或 `expected axum::Router, found axum::Router`，与业务代码无关，先查 ⑩。

| crate | 配 axum 0.7 | 配 axum 0.8 | 备注 |
|---|---|---|---|
| axum-core | 0.4 | 0.5 | 只实现 extractor/`IntoResponse` 的库依赖它，不拖 axum（DEP-02） |
| axum-extra | 0.9 | 0.10 | `Host`、`TypedHeader`（feature `typed-header`）、`#[typed_path]` 同步换语法 |
| axum-macros | 0.4 | 0.5 | 由 axum `macros` feature 拉入，不手写 |
| tower | 0.4 | 0.5 | `ServiceExt::oneshot` 等用法不变 |
| tower-http | 0.5 | 0.6 | 内部 tower 0.5 |
| hyper / http / http-body | 1.x | 1.x | 不变 |
| tokio-tungstenite（`ws`） | 0.23（0.7.6+；0.7.3–0.7.5 是 0.21，更早 0.20） | 0.26+（0.8.9 已到 0.29） | `Message` 载荷类型的来源 |
| 三方 axum 集成（session/openapi/auth） | 各自 0.7 线 | 各自声明支持 0.8 的版本 | 没有 0.8 线就停住，不要 `[patch]` |

## 检测命令

```bash
# 路径参数显式给 .：stdin 非 tty（agent 工具里）时 rg 会改读 stdin 而挂住
# ① 0.7 路径语法（route/nest/typed_path/路径常量）——迁移完成的判据是零输出
rg -n --type rust '"[^"]*/[:*][A-Za-z_]' .
# ② async_trait 残留
rg -n --type rust 'async_trait' .; rg -n 'async-trait' -g 'Cargo.toml' .
# ③ Option 提取器：内置 + 自定义（先列出自定义 extractor 名，再逐个 rg 'Option<名>'）
rg -n --type rust 'Option<(Path|Query|Json|Form|Extension|TypedHeader|Host|CookieJar|Multipart)\b' .
rg -on --type rust 'FromRequest(Parts)?<[^>]*> for \w+' . | sort -u
# ④ 元组 Path：逐个对照路由里 {} 的个数
rg -n --type rust 'Path<\(' .
# ⑤ 搬到 axum-extra 的类型
rg -n --type rust 'axum::extract::Host|axum::(TypedHeader|headers)' .
# ⑥ serve 泛型化影响
rg -n --type rust 'tcp_nodelay|Connected<IncomingStream' .
# ⑦ WebSocket Message
rg -n --type rust 'Message::(Text|Binary|Ping|Pong)\(|\.close\(\)\.await|into_text\(\)|into_data\(\)|CloseFrame \{' .
# ⑧ MatchedPath 消费方 + 看板/告警里的旧模板
rg -n --type rust 'MatchedPath|matched_path' .; rg -n '/:[a-z_]+' -g '*.json' -g '*.y*ml' -g '*.promql' .
# ⑨ 多余的 into_make_service
rg -n --type rust 'into_make_service\(\)' .
# ⑩ 版本双份：报 "did not match any packages" 才是通过
cargo tree -i axum@0.7; cargo tree -i tower@0.4; cargo tree -i tower-http@0.5
```

## 有序迁移清单（AX-52）

按序做，每步独立可验证、可单独提交；到第 7 步前不改业务逻辑。

1. 对齐依赖：按上表改 `Cargo.toml`（workspace 在 `[workspace.dependencies]` 收口，WS-09），`cargo update`，⑩ 三条全空再继续。
2. 路径语法：跑 ①，sed 批量替换后 `git diff` 逐行审，再跑 ① 直到零输出；剩下的是路径常量/拼接，手改。禁止用 `without_v07_checks()` 止血。
3. 删 `#[async_trait]`：每个 `impl FromRequest(Parts)` 删属性与 `use axum::async_trait`，函数体不动；`async-trait` 无其他使用者就从 `Cargo.toml` 删（SIMP-03）。
4. `Option<T>` 审计：③ 每一处回答「0.7 时有没有依赖坏值变 `None`」。依赖 → 改 `Result<T, T::Rejection>` 并显式 `.ok()`；自定义 extractor 要 `Option` → 补 `OptionalFromRequestParts`（模板见 [extractors.md](extractors.md)）。可选路径段多半是设计味道：拆成 `/users` 与 `/users/{id}` 两条路由。
5. WebSocket：`Message::Text(s.into())`/`Message::text(s)`、`Message::Binary(v.into())`、`CloseFrame { reason: "bye".into(), .. }`；`socket.close()` → `socket.send(Message::Close(None))`；模式匹配里把 `text: String` 的用法改成借用 `&*text`。
6. 服务入口：nodelay 与自定义 `Connected` 改到 listener 侧；`into_make_service()` 多余就删，`_with_connect_info` 保留。
7. 编译驱动：`cargo build` 依次处理 import（⑤）、`Sync`（先 `#[debug_handler]`/`#[debug_middleware]` 看真实原因，再给捕获类型换 `Arc`/`tokio::sync`，不要加 `unsafe impl Sync`）、`Option<自定义>`、`Message`、`IncomingStream`。
8. 可观测：⑧ 命中处与 Grafana/告警规则同步把 `:id` 改 `{id}`；旧标签的告警在迁移后是「无数据」而不是报警（AX-11）。
9. 测试与冒烟：`cargo test` 之外必须有一个构造完整 `Router` 的测试（路径 panic 只在构造期触发，不构造就测不到）；元组 `Path` 路由各打一次 `oneshot`（④ 是 500 不是编译错）；启动一次二进制看日志。

```bash
# 第 2 步：只改 route/nest/typed_path 所在行；.bak 审完 git diff 再删
rg -l --type rust '"[^"]*/[:*][A-Za-z_]' . | xargs sed -i.bak -E \
  '/(route|nest|route_service|nest_service|typed_path)[[:space:]]*\(/ { s#/:([A-Za-z_][A-Za-z0-9_]*)#/{\1}#g; s#/\*([A-Za-z_][A-Za-z0-9_]*)#/{*\1}#g; }'
find . -name '*.rs.bak' -delete
```

```rust
// 第 6 步：axum 0.7
axum::serve(listener, app).tcp_nodelay(true).await?;

// axum 0.8：nodelay 挪到 listener；Unix socket 走同一入口，不再手写 accept 循环
use axum::serve::ListenerExt;
let listener = tokio::net::TcpListener::bind(addr).await?
    .tap_io(|tcp| if let Err(e) = tcp.set_nodelay(true) { tracing::debug!(%e, "set_nodelay") });
axum::serve(listener, app).with_graceful_shutdown(shutdown).await?;

let uds = tokio::net::UnixListener::bind("/run/app.sock")?;
axum::serve(uds, app).await?;
// 自定义连接信息：impl Connected<IncomingStream<'_>> for X  →  impl Connected<IncomingStream<'_, TcpListener>> for X
```

```rust
// 第 9 步：一个构造测试吃掉 0.7 语法 / 重叠路由的全部 panic（panic 清单见 routing.md）
#[test]
fn router_builds() { let _ = crate::app::router(); }
```

## 0.6 → 0.7 债务识别（hyper 1.0）

只识别不展开；命中即在升 0.8 之前先清掉，0.8 的每个 API 都建立在 0.7 形状上。

| 0.6 残留 | 0.7+ 写法 | 症状 |
|---|---|---|
| `axum::Server::bind(&addr).serve(app.into_make_service())` | `let l = TcpListener::bind(addr).await?; axum::serve(l, app)` | 编译：`axum::Server` 不存在 |
| `Router<S, B>`、`MethodRouter<S, B>`、`Next<B>`、`Request<B>` 泛型中间件 | 去掉 `B`；`Request` 用 `axum::extract::Request`，`Next` 无泛型 | 编译：泛型参数数量不对 |
| `hyper::Body`、`BoxBody`/`.boxed()`、`Full`/`Empty` 响应体 | `axum::body::Body`（`Body::new`/`Body::empty`/`Body::from`） | 编译 |
| `RawBody`、`extract::BodyStream` | `Body` 直接做 extractor；流式 `Body::into_data_stream()` | 编译 |
| `axum::TypedHeader`、`axum::headers`、`headers` feature | `axum_extra::TypedHeader` + feature `typed-header` | 编译 |
| `nest_service` 依赖父 fallback | 只有 `nest` 继承 fallback | **静默**：`nest_service` 下未命中回默认 404 |
| http 0.2 / hyper 0.14 生态（reqwest 0.11、tonic ≤ 0.11、tower-http ≤ 0.4） | http 1.x 生态（reqwest 0.12+、tonic 0.12+、tower-http 0.5+） | 编译：两份 `HeaderMap`/`StatusCode`，`expected http::HeaderMap, found http::HeaderMap` |

检测：`rg -n --type rust 'axum::Server|hyper::Body|BodyStream|RawBody|Next<|Router<[^>]*,\s*B>|axum::(TypedHeader|headers)' .`；`cargo tree -i http@0.2`。

## 验证

- 迁移按清单拆成至少三次各自可编译的提交：依赖对齐 → 路径与 extractor → 其余；回退粒度由此决定。
- `cargo build` 通过不是完成：① 零输出 + `router_builds` 通过 + ③/④ 每处有一条打坏输入的 `oneshot` 测试（TEST-10）。
- 压测前后 p50/p99 不应变（PERF-01）；变了先查 nodelay 是否随 `Serve::tcp_nodelay` 一起丢了。
