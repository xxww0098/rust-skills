# axum/scaffold — 新服务骨架、组合根与状态

目的：用户要「新建 axum 服务 / 搭骨架 / 整理 main.rs」，或代码证据是 `Router::new()` 组合根、`AppState`、`with_state`、`axum::serve`、进程秒退或 `Handler is not satisfied` 时加载。只讲组合根、状态与启动；超时/限流/停机/可观测/错误映射的规则在 [../axum.md](../axum.md)（AX-04..AX-12）只链接不复述，数据层见 [../sqlx.md](../sqlx.md)，停机细节见 [../async.md](../async.md)，镜像与发布见 [../ship.md](../ship.md)。

## 三层分工：先问「谁拥有这个能力」

1. tokio 拥有调度、`TcpListener`、定时器、`signal`、`spawn_blocking`；hyper 1.x（经 hyper-util）拥有 HTTP/1、HTTP/2 收发，藏在 `axum::serve` 里；tower/tower-http 拥有 `Service`/`Layer` 与超时、trace、限流、压缩、CORS、request-id；axum 只做 `Router`、extractor、`Handler`、`IntoResponse`、`serve`。手写 tower-http 已有的 layer 是 SIMP-01 违规且没过规范测试。
2. `Router<()>` 本身就是 `tower::Service`：能进 `axum::serve`、能 `nest`/`merge`、能 `oneshot` 测试。只实现 `FromRequestParts`/`IntoResponse` 的可复用库依赖 `axum-core`（0.8 配 axum-core 0.5），不拖整个 axum（DEP-02）。入口 `axum::serve(listener, app)` 在 0.7/0.8 完全相同，禁止为版本写 `cfg` 分叉；`axum::Server` 是 0.6 债务；0.7→0.8 影响骨架的只有路径语法（AX-18）与自定义 extractor 去掉 `#[async_trait]`。

## Cargo 最小依赖集（AX-49）

```toml
axum = "0.8"                  # 默认 feature：tokio http1 json query form matched-path original-uri tracing；http2、macros 不默认
tokio = { version = "1", features = ["rt-multi-thread", "macros", "net", "signal"] }  # 二进制可用 "full"；库禁止（ASYNC-08）
tower-http = { version = "0.6", features = ["trace", "timeout", "limit", "request-id", "cors"] }  # 并发上限再加 tower 的 limit/load-shed
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
anyhow = "1"                  # 只给 main 编排层（D-2）；API 错误用 error.rs 的 enum，变体多再 thiserror（ERR-08）
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "macros"] }  # 有库才加；0.9 见 ../sqlx.md
```

1. `[package]` 写 `edition = "2024"` + `rust-version = "1.85"`（DEP-08）；版本钉 minor 浮 patch，禁 `"*"`；应用提交 Cargo.lock（DEP-07）。
2. `default-features = false` 后必须手动加回 `tokio` + `http1`/`http2`，否则 `axum::serve` 不存在（DEP-03）；`macros` 只在用 `#[debug_handler]`/`#[derive(FromRef)]` 时开；`http2` 在 LB 终结 TLS 的部署里用不上，需要 h2c 再开。
3. tokio 漏 `signal` → 写不出优雅停机；漏 `net` → 没有 `TcpListener`。`[dev-dependencies]` 的 `tower` 要开 `util` 才有 `ServiceExt::oneshot`，`http-body-util` 的 `BodyExt::collect` 读响应体。

## 模块布局

```
src/
  main.rs          读 env → init tracing → 建资源 → bind → serve；零业务（WS-04）
  config.rs        Config::from_env()：typed 字段、启动即校验、Debug 脱敏 secrets（SH-05、API-05）
  state.rs         AppState + FromRef impl
  error.rs         AppError + IntoResponse（AX-12）
  routes/mod.rs    根组合：nest/merge → layer → with_state
  routes/users.rs  pub fn router() -> Router<Arc<AppState>> + 本资源的薄 handler（AX-14）
```

1. 同一资源的 `router()` 与 handler 同文件；service/ 层只在 handler 开始编排多查询、外呼时出现（SIMP-01）；拆 handlers/ 只因独立变化原因，不按行数（WS-11）。新建 `routes/orders.rs` 必须在 `routes/mod.rs` 写 `mod orders;` 并挂进根（TEST-04：孤儿文件 = 路由静默不存在，编译照过）。
2. oneshot 测试放同 crate 的 `#[cfg(test)]`（TEST-01）不需要 lib.rs；要 `tests/` 目录才拆 `lib.rs`（集成测试链接的是 lib，bin 里的 `app()` 对它不可见）。禁 `static POOL: OnceLock<PgPool>` 代替 State——测试无法注入、多实例互串。

## 最小可运行骨架（三段共 70 行）

```rust
// main.rs —— 只做解析、初始化、编排；零业务（WS-04）
mod error; mod state;
use std::sync::Arc;
use axum::{extract::{Path, State}, routing::get, Router};
use error::AppError;
use state::{AppState, Config};
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let filter = tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into());
    tracing_subscriber::fmt().with_env_filter(filter).init();      // OBS-01；RUST_LOG 覆盖
    let cfg = Config::from_env()?;                                  // 缺变量 = 启动失败，不带病上线
    let db = sqlx::postgres::PgPoolOptions::new().max_connections(10) // SX-02：池参数显式并注明依据
        .connect(&cfg.database_url).await?;
    let state = Arc::new(AppState { db, cfg });
    let listener = tokio::net::TcpListener::bind(&state.cfg.listen).await?;
    axum::serve(listener, app(state))
        .with_graceful_shutdown(shutdown_signal())                  // AX-06；定义见下，ctrl_c + SIGTERM
        .await?;                                                    // 不 await = 进程秒退
    Ok(())
}

async fn shutdown_signal() {                                        // AX-06；官方 graceful-shutdown 例子同形
    let ctrl_c = async { tokio::signal::ctrl_c().await.expect("install Ctrl+C handler") };
    #[cfg(unix)]
    let term = async {
        tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())
            .expect("install SIGTERM handler").recv().await;
    };
    #[cfg(not(unix))]
    let term = std::future::pending::<()>();                        // Windows 无 SIGTERM
    tokio::select! { _ = ctrl_c => {}, _ = term => {} }
}

fn app(state: Arc<AppState>) -> Router {                            // 路由超一屏就搬去 routes/mod.rs，签名不变
    Router::new()
        .route("/healthz", get(|| async { "ok" }))                  // SH-03：liveness 不查下游
        .route("/users/{id}", get(show_user))                       // 0.8 花括号（AX-18）
        .layer(tower_http::trace::TraceLayer::new_for_http())       // 其余边界层见 AX-04/05/11
        .with_state(state)                                          // 最后一步：Router<Arc<AppState>> → Router<()>
}

async fn show_user(State(s): State<Arc<AppState>>, Path(id): Path<i64>) -> Result<String, AppError> {
    let email = sqlx::query_scalar!("SELECT email FROM users WHERE id = $1", id).fetch_optional(&s.db).await?;
    email.ok_or(AppError::NotFound)
}
// state.rs —— 启动期建好的长生命周期资源；handler 只读（可变部分见 AX-03）
pub struct Config { pub listen: String, pub database_url: String }
impl Config {
    pub fn from_env() -> anyhow::Result<Self> {
        use anyhow::Context;
        let listen = std::env::var("LISTEN").unwrap_or_else(|_| "0.0.0.0:3000".into());
        let database_url = std::env::var("DATABASE_URL").context("DATABASE_URL")?;
        Ok(Self { listen, database_url })
    }
}
pub struct AppState { pub db: sqlx::PgPool, pub cfg: Config }
// error.rs —— 具名 enum 集中映射状态码（AX-12）；变体多、要 source 链时再上 thiserror（ERR-08）
use axum::{http::StatusCode, response::{IntoResponse, Response}};
#[derive(Debug)]
pub enum AppError { NotFound, Db(sqlx::Error) }
impl From<sqlx::Error> for AppError { fn from(e: sqlx::Error) -> Self { Self::Db(e) } }
impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let status = match &self {
            Self::NotFound => StatusCode::NOT_FOUND,
            Self::Db(e) => { tracing::error!(error = %e, "database"); StatusCode::INTERNAL_SERVER_ERROR }
        };
        status.into_response()                                      // 只在这里记一次（OBS-03）；对外不泄内部细节
    }
}
```

## AppState、`State<Arc<…>>` 与 FromRef 收窄（AX-22）

1. `S: Clone + Send + Sync + 'static`，axum 每请求 clone 一次 state。两种形态二选一：**A** `#[derive(Clone, FromRef)] struct AppState { db: PgPool, http: Client, cfg: Arc<Config> }` + `State<AppState>`，要求每个字段都廉价 Clone；**B** `Arc<AppState>` + `State<Arc<AppState>>`，字段不要求 Clone，一次 Arc 计数搞定。字段里出现 `Rc`/`RefCell`/`!Sync` 客户端时先答 D-6「该不该跨线程」，不是套 `Mutex`。
2. 禁混用：`#[derive(FromRef)]` 生成的是 `impl FromRef<AppState> for Field`，对 `Router<Arc<AppState>>` 无效——`State<PgPool>` 直接报 `PgPool: FromRef<Arc<AppState>>` 不满足。形态 B 的收窄必须手写，且 impl 目标只能是本 crate 的 newtype——`Arc<AppState>` 不是本地类型（`Arc` 非 `#[fundamental]`），为 `PgPool`/`Client` 这类外部类型直接 impl 是孤儿规则 E0117；嫌麻烦就老老实实 `State<Arc<AppState>>` 取 `s.db`。
3. 收窄的收益是测试边界：handler 只依赖 `State<PgPool>`，单测 `Router::new().route(..).with_state(pool)` 直接喂子状态（`Clone` 类型对自身有 `FromRef` 毯式实现），不必拼整个 AppState。只在有第二个调用方或测试需要时才收窄（SIMP-01）。
4. 池、`reqwest::Client` 内部已是 Arc：禁 `Arc<PgPool>`、每请求 `Client::new()`（AX-02）；大 `Vec`/`HashMap` 不加 Arc 就是每请求深拷贝。可变共享 `Arc<Mutex<_>>` 可进 state，guard 不跨 await（AX-03、ASYNC-02）。

```rust
// ✗ Arc<AppState> 配 derive(FromRef)：生成的 FromRef<AppState> 对不上 Router<Arc<AppState>>
#[derive(Clone, FromRef)] struct AppState { db: PgPool }
async fn h(State(db): State<PgPool>) {}          // error: PgPool: FromRef<Arc<AppState>> 不满足
// ✓ 形态 B 的手写 impl 只能落在本 crate 类型上：newtype 收窄（为 PgPool 直接 impl 撞孤儿规则 E0117）
pub struct Db(pub PgPool);
impl FromRef<Arc<AppState>> for Db { fn from_ref(s: &Arc<AppState>) -> Db { Db(s.db.clone()) } }
async fn h2(State(Db(db)): State<Db>) {}
```

## `with_state` 时机与 `Router<S>` 穿透（AX-22、AX-23）

1. `Router<S>` 读作「还欠一个 S」，不是「持有 S」（docs 原话）。只有 `Router<()>` 能进 `axum::serve` / `oneshot`。
2. 每个模块 `pub fn router() -> Router<Arc<AppState>>`，写明类型参数让错误落在模块而不是根；模块内**不调** `with_state`。根：`nest`/`merge` → `layer` → `with_state` **一次**。`.layer()` 只包住调用前已注册的路由，后加的 `.route()` 不被 Trace/Timeout 覆盖且不报错——路由全部注册完再 layer。嫌长就 `type AppRouter = Router<Arc<AppState>>;`。
3. 需要 state 的中间件 `middleware::from_fn_with_state(state.clone(), f)` 在 `with_state` 之前挂，clone 的是 Arc 计数（PERF-03）。两个子树用不同 State 类型也拼得起来：子树先 `with_state(sub)`（`with_state<S2>` 的 `S2` 由 nest 处推断）再 nest，见 [routing.md](routing.md)。骨架默认仍统一一个 AppState + FromRef 收窄，少一层心智负担。
4. `Handler is not satisfied` 是五种错误的合集（AX-26）：参数不是 extractor（裸 `bool`/`u32`）、body extractor 不在最后（AX-13）、返回类型不实现 `IntoResponse`（最常见是 `Result<T, E>` 的 `E` 没实现）、函数不是 `async`、future 非 `Send`（`std::sync::MutexGuard`/`Rc` 跨 await，ASYNC-02）。禁止猜：开 `macros` feature 加 `#[axum::debug_handler]` 读精确错误，修完删掉（与 `dbg!` 同级）；报错同时出现 `Handler` 与 `State` 字样先查下表。

| 编译错误 | 根因 | 修复 |
|---|---|---|
| `expected Router<Arc<AppState>>, found Router<()>`（在 `nest`/`merge`） | 子路由已经 `.with_state()` 过 | 删子路由的 `with_state`，只在根调用 |
| `Handler<_, ()> is not satisfied`（在 `.route()`） | `.with_state()` 之后又加了用 `State` 的路由 | `with_state` 移到所有 route/layer 之后 |
| `Router<Arc<AppState>>: Service<IncomingStream<…>>` 不满足（在 `serve`/`oneshot`） | 忘了 `with_state` | 补 `.with_state(state)` |
| 类型不匹配提到两个不同 state 类型；或 `type annotations needed` | `with_state` 传错类型；或没有任何 handler 约束 `S2` | 统一 AppState + FromRef；标 `let app: Router = …` |

## `Extension` 何时可用

1. 可用：中间件**按请求**产生的值——`from_fn` 里 `req.extensions_mut().insert(CurrentUser)`，handler 取 `Extension<CurrentUser>`；鉴权类值优先写成 `FromRequestParts` extractor（AX-15），缺失返回 401 而不是 500。也是三方 layer 的约定出口：`ConnectInfo<SocketAddr>` 要 `app.into_make_service_with_connect_info::<SocketAddr>()` 才有值。
2. 禁用：启动期资源（AX-01）。`.layer(Extension(pool))` 忘挂或挂错子树，编译照过，每请求 500 `Missing request extension`；`with_state` 忘了是编译错误。`.layer(Extension(x))` 同样只覆盖之前注册的路由。

## 进程秒退、启动即 panic、收不到停机（AX-47）

| 症状 | 根因 | 修复 |
|---|---|---|
| 秒退、无日志、退出码 0 | `axum::serve(...)` 没 `.await`，`Serve` 只是个值 | `.await?` 作为 main 最后一句 |
| 秒退 | `tokio::spawn(axum::serve(..))` 后 main 返回，或手建 `Runtime` 是局部变量——runtime drop 取消全部任务 | 不 spawn serve；多监听器 `try_join!`；手建 runtime 用 `block_on` |
| 秒退带 Err | bind 失败（端口占用 / 1024 以下无权限）或 env 缺失被 `?` 早退 | 这是设计内的 fail-fast；读 Err，别 `let _ =` 吞掉（ERR-05） |
| 启动 panic `Path segments must not start with ':'` | 0.8 路由写了 0.7 的 `:id`，`route()` 时直接 panic | 改 `{id}`（AX-18）；`without_v07_checks()` 只给真要匹配字面冒号的路由 |
| 启动 panic ``Overlapping method route. Handler for `GET /x` already exists`` | 同路径**同方法**注册两次（`.route` 两次、或 `merge`/`nest` 展开后重合）；同路径不同方法分两次 `.route()` 会自动合并，不是根因 | 删掉重复的那个 handler；panic 全表见 [routing.md](routing.md) |
| SIGTERM 后不退，宽限期后被 SIGKILL | 没 `with_graceful_shutdown`，或只监听 `ctrl_c`（只管终端） | `select!` 同时等 `tokio::signal::ctrl_c()` 与 `signal(SignalKind::terminate()).recv()`（非 unix 分支用 `std::future::pending`）；drain 上限见 AX-06、SH-04 |
| 停机卡住不退 | `with_graceful_shutdown` 只停 accept、等在途请求，不管你 spawn 的后台任务 | `CancellationToken` + `TaskTracker`（AS-04、AS-05） |

## 搭建顺序

1. Cargo.toml：edition 2024 + `rust-version`，axum 0.8，按上表开 feature；路径一律花括号。
2. state.rs / config.rs：列出长生命周期资源（池、`Client`、配置），选形态 A 或 B；Config typed + `from_env()`。
3. error.rs：AppError + `IntoResponse` + 需要的 `From`；handler 返回 `Result<_, AppError>`，零 `unwrap`（ERR-03）。
4. routes/：每资源 `router() -> Router<Arc<AppState>>`；handler 薄（AX-14）；鉴权 extractor（AX-15）。组合根：`nest`/`merge` → 边界 layer 栈（AX-04/05/11；浏览器调用时 CORS 显式 allowlist，禁 `CorsLayer::permissive()`，AX-32）→ `with_state`（AX-22）。
5. main.rs：tracing → Config → 资源 → bind → `serve` + `with_graceful_shutdown`；后台任务进 TaskTracker（AS-05）。测试：`app()` + `oneshot` 覆盖每条路由的成功与主要错误分支；连外部服务的测试 fail-loud（TEST-07）。发布走 [../ship.md](../ship.md)。

## 生产就绪检查单

| 项 | 证据位置 | 关联规则 |
|---|---|---|
| main.rs 只有 env / tracing / 资源 / bind / serve | main.rs | WS-04 |
| edition 2024 + `rust-version`；axum 0.8 且路径花括号 | Cargo.toml、routes/ | DEP-08、AX-18 |
| 资源建一次进 State；无 `Arc<Pool>`、无每请求 `Client::new()`；`with_state` 只在根调用一次 | state.rs、routes/mod.rs | AX-01、AX-02 |
| Config typed、启动校验 fail-fast；secrets 不进日志/镜像/git | config.rs | SH-05、API-05 |
| 池 `max_connections`/`acquire_timeout` 显式并注明依据 | main.rs | SX-02 |
| 超时分层；body 上限；并发上限 / 卸载 | 组合根 layer 栈 | AX-04、AX-05 |
| `ctrl_c` + SIGTERM 停机；drain 上限；后台任务可等待 | main.rs | AX-06、AS-04、SH-04 |
| `TraceLayer` + request-id；错误只记一次；AppError 集中映射；handler 无 `unwrap`、`#[debug_handler]` 已删 | 组合根、error.rs、handlers | AX-11、AX-12、OBS-03、ERR-03 |
| 鉴权走 extractor，授权与认证分开；CORS 显式 allowlist（有浏览器调用时） | extractors、组合根 | AX-15 |
| `app()` 可被 oneshot 构造；缺外部服务 fail-loud | `#[cfg(test)]` / tests/ | TEST-10、TEST-07 |
| `/healthz` liveness 独立于业务路由、不查下游；多阶段镜像、非 root、版本单源 | routes/、Dockerfile、CI | SH-01、SH-03、SH-11 |

## 验证

1. `cargo run` 后 `curl -i localhost:3000/healthz` 得 200；`kill -TERM <pid>` 应在在途请求结束后以 0 退出，不等 SIGKILL。
2. oneshot：`app(state).oneshot(Request::builder().uri("/healthz").body(Body::empty())?).await?` 断言 200；缺 DB 的测试 panic 指明缺什么（TEST-07）。
3. 动过依赖：`cargo tree -e features -i axum` 确认 `tokio`/`http1` 仍开、`macros` 没被顺手带上；`cargo build --timings` 留基线（BUILD-04）。
