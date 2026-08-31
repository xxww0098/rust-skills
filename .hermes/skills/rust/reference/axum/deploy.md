# axum/deploy — 部署、停机与 runtime 性能

目的：代码里出现 `Dockerfile`/`[profile.release]`/`with_graceful_shutdown`/`ConnectInfo`/`worker_threads`，或用户问「滚动发布丢请求、SIGTERM 后被 SIGKILL、容器里连不上、压测一上并发就卡、服务莫名变慢」时加载。深化 [../axum.md](../axum.md) 的 AX-06/AX-08 与 [../ship.md](../ship.md) 的 SH-01..05：Dockerfile/cargo-chef 不重复（SH-01），最小 `shutdown_signal()` 与 main 骨架见 [scaffold.md](scaffold.md)，subscriber 装配见 [observability.md](observability.md)，池参数见 [../sqlx.md](../sqlx.md)。本文 API 对 axum 0.7/0.8 相同，唯一差异是 `TCP_NODELAY` 写法（见「连接层」）。

## 构建产物

1. `lto = "fat"` 只在 `--timings` 与压测都有数据后改（BUILD-03/PERF-01）。`strip = true` 让生产 panic backtrace 只剩地址；要行号则 `debug = "line-tables-only"` 不 strip，体积实测。
2. **禁止 `panic = "abort"`**（AX-47）：服务里一个 handler panic 就杀整个进程，所有在途请求陪葬；默认 unwind 下 tokio 只丢该任务，`CatchPanicLayer` 再把它变 500（ERR-04；装配顺序见 [observability.md](observability.md)）。CLI/嵌入式模板里的这一行不要抄。

```toml
[profile.release]
lto = "thin"
codegen-units = 1
strip = "debuginfo"   # 保留符号名：backtrace 可读；strip = true 只剩地址
# panic = "abort"     # 服务禁用，见上
```

3. 目标三元组按运行层选（SH-01/SH-02）；musl 下禁 `native-tls`/`openssl` 系依赖，确要 C 依赖用 `cargo zigbuild` 或 `cross`：

| 运行层 | 构建 | 代价 |
|---|---|---|
| `scratch` | `--target x86_64-unknown-linux-musl`（arm64 节点 `aarch64-unknown-linux-musl`），全静态 | musl malloc 多线程下慢且碎片多——延迟敏感换 `mimalloc` 全局分配器后压测（META-02）；镜像无 CA：出站 TLS 用 rustls + `webpki-roots`（reqwest feature `rustls-tls-webpki-roots`），或 `COPY` CA bundle |
| `distroless/cc` | 默认 gnu 目标 | 有 libc 与 CA；无 shell，调试靠 ephemeral container |
| `debian-slim` | 默认 gnu 目标 | 能 `apt`、进 shell；体积最大 |

## 启动：绑定与配置

1. 容器内绑 `0.0.0.0:$PORT`（`127.0.0.1` 只有容器自己能连，`-p` 映射进来是 connection refused）；端口从环境读，默认值只给非密钥项。
2. typed config 启动即校验（SH-05）：全部 `std::env::var` 在 `Config::from_env()` 一处解析成 `u16`/`Duration`/`Url`，缺失或格式错 → 非零退出并点名变量；handler 里禁止再碰 `env::var`；`Debug` 脱敏 secrets（API-05）。几个变量不值得引 `figment`/`config` crate，手写 `parse` 即可。
3. 启动日志打印：监听地址、`std::thread::available_parallelism()`、版本/git sha、`RUST_LOG` 生效值——排「容器里怎么不一样」的第一手证据。

```rust
struct Config { port: u16, database_url: String, drain_grace: Duration }
impl Config {
    fn from_env() -> anyhow::Result<Self> {
        let var = |k: &str| std::env::var(k).map_err(|_| anyhow::anyhow!("missing env {k}"));
        let secs: u64 = var("DRAIN_GRACE_SECS").unwrap_or_else(|_| "20".into()).parse()?;
        Ok(Self {
            port: var("PORT").unwrap_or_else(|_| "3000".into()).parse()?,
            database_url: var("DATABASE_URL")?,              // 密钥类无默认值
            drain_grace: Duration::from_secs(secs),
        })
    }
}
```

## 停机序列（AX-06/AX-46/SH-04）

`with_graceful_shutdown` 只做两件事：signal 完成后停 accept、等在途请求。它**不**等 upgrade 后的 WS 连接和你 spawn 的任务，也**没有**总超时。生产序列五步，时间预算必须满足 `摘流等待 + drain_grace + 任务收尾 < terminationGracePeriodSeconds`（k8s 默认 30s；`docker stop` 默认 10s；systemd `TimeoutStopSec`）。

```rust
// axum 0.8（0.7 同形）；tokio-util features = ["rt"]；tokio ≥1.39（select! 才接受 IntoFuture）
use std::{net::SocketAddr, sync::{Arc, atomic::Ordering}, time::Duration};
use tokio::net::TcpListener;
use tokio_util::{sync::CancellationToken, task::TaskTracker};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cfg = Config::from_env()?;
    let state = Arc::new(AppState::build(&cfg).await?);      // 含 pool 与 ready: AtomicBool
    let token = CancellationToken::new();
    let tracker = TaskTracker::new();
    tracker.spawn(jobs::run(state.clone(), token.clone()));  // 后台任务统一归宿（AS-04/AS-05）

    let listener = TcpListener::bind(("0.0.0.0", cfg.port)).await?;
    let app = routes::app(state.clone()).into_make_service_with_connect_info::<SocketAddr>();
    let server = axum::serve(listener, app)
        .with_graceful_shutdown(on_shutdown(state.clone(), token.clone()));

    tokio::select! {                                           // ① drain 正常完成 或 ② 到期硬退
        r = server => r?,
        _ = async { token.cancelled().await; tokio::time::sleep(cfg.drain_grace).await } =>
            tracing::warn!("drain 超时，放弃剩余连接"),
    }
    tracker.close();
    if tokio::time::timeout(Duration::from_secs(5), tracker.wait()).await.is_err() {
        tracing::warn!("后台任务 5s 内未退出");
    }
    state.pool.close().await;                                  // 连接干净归还，DB 侧不再记一波 reset
    // OTel provider.shutdown() 在此（observability.md）
    Ok(())
}

async fn on_shutdown(state: Arc<AppState>, token: CancellationToken) {
    shutdown_signal().await;                                   // SIGINT + SIGTERM，见 scaffold.md
    state.ready.store(false, Ordering::Relaxed);               // Relaxed：独立旗标，不与其他数据同步
    tokio::time::sleep(Duration::from_secs(3)).await;          // 等 LB/endpoint 摘流传播；有 preStop sleep 则删
    token.cancel();                                            // SSE/WS 循环、后台任务收到取消
}                                                              // 返回 → 停 accept → drain
```

1. 先翻 readiness 再停 accept：endpoint 撤销是异步的，立即停 accept 会让 LB 在几秒内继续把新连接送进来吃 connection refused——滚动发布那一波 5xx 的主因。
2. 非流式路由的 `TimeoutLayer`（AX-04）天然给 drain 封顶；SSE/WS 不能靠它（AX-04 禁一刀切），要在循环里加 `token.cancelled()` 分支主动发 Close/结束流（见 [realtime.md](realtime.md)），再由 `drain_grace` 兜底。
3. `shutdown_signal` 的 Windows 分支 `pending()` 是对的（XP-07、AX-47）；只监听 `ctrl_c()` 在编排器下永远不触发。
4. signal 后 hyper 主动关 HTTP/1.1 空闲 keep-alive 连接、对 h2 发 GOAWAY；客户端复用旧连接收到 reset 属客户端重试策略问题，但服务端日志要能区分停机期错误（OBS-02 加 `phase="draining"` 字段）。

## 连接层：ConnectInfo、可信代理、TLS、h2c（AX-48）

1. `ConnectInfo<SocketAddr>` 依赖 `into_make_service_with_connect_info::<SocketAddr>()`；直接 `serve(listener, app)` 时该 extractor 运行期 500 `Missing request extension`。oneshot 测试挂 `.layer(MockConnectInfo(SocketAddr::from(([127, 0, 0, 1], 0))))`。
2. LB/ingress 后面 `ConnectInfo` 永远是代理 IP。客户端 IP 取法：维护**可信代理 CIDR 列表**，`X-Forwarded-For` 从右往左跳过可信地址，取第一个不可信的；`Forwarded`（RFC 7239）同理。取最左 = 任何人一条 header 伪造 IP 绕过限流/审计。`axum-client-ip` 把来源做成显式配置（`RightmostXForwardedFor`/`CfConnectingIp` 等，版本以 docs.rs 为准），未配置报错而不是默默信任。
3. `X-Forwarded-Proto`/`X-Forwarded-Host` 同样只信可信代理；生成绝对 URL、判定 Secure cookie 用它们，不用 `Host`。
4. TLS 默认在 LB/ingress/sidecar 终止，axum 只听明文——少一套证书轮换。必须自己终止（直连公网、mTLS、无 LB）：`axum-server` + rustls（`bind_rustls(addr, RustlsConfig::from_pem_file(cert, key).await?)`；`Handle::graceful_shutdown(Some(dur))` 自带 drain 上限；`reload_from_pem_file` 热换证书）。
5. HTTP/2：axum `http2` feature **不是默认**（AX-49）。开了之后 `axum::serve` 同端口自动识别 h2c（prior knowledge）与 HTTP/1.1；gRPC（tonic）共端口、LB 用 h2c 回源都需要它。h2 over TLS 要 ALPN `h2, http/1.1`（axum-server 的 `RustlsConfig` 默认配好）。
6. `TCP_NODELAY`：小响应多 RTT（长轮询、gRPC 流）场景实测后再开。`// axum 0.8` `listener.tap_io(|s| { if let Err(e) = s.set_nodelay(true) { tracing::debug!(%e, "nodelay") } })`（`axum::serve::ListenerExt`）；`// axum 0.7` `axum::serve(l, app).tcp_nodelay(true)`（0.8 已删）。`SO_REUSEADDR` tokio bind 在 Unix 已默认设；`SO_REUSEPORT` 多 accept 循环只在单 accept 循环被火焰图证明是瓶颈后用 `socket2` 建 listener。

## 探针与日志（SH-03、AX-33）

1. `/healthz` liveness 只答 200，**禁查 DB**：DB 抖动时 liveness 失败 = k8s 重启全部 pod，故障放大。`/readyz` readiness = `ready` 旗标 && 下游快速探活（`timeout(500ms, pool.acquire())`），停机先翻 503。
2. 探针路由放在鉴权、限流、`TraceLayer` 之外：`Router::new().merge(api.layer(edge_layers)).merge(health)`；探针每秒打，进 TraceLayer 就是日志刷屏。公网 LB 不应能打到探针——独立 admin 端口或 ingress 规则挡住。
3. 容器日志 = stdout 一行一条 JSON（`fmt().json()` + `EnvFilter` 读 `RUST_LOG`，缺省 `info,tower_http=info`），不写文件不自转；采集交给平台。用了 `tracing_appender::non_blocking` 必须把 `WorkerGuard` 持到 main 末尾，否则退出前的日志丢。
4. 生产 `RUST_LOG=debug` 是事故（TraceLayer 每请求多行 + sqlx 每条语句）；按 target 精确：`info,myapp=debug,sqlx=warn`。`RUST_BACKTRACE=1` 可常开（只在 panic 时付代价），配「构建产物」的 strip 策略才可读。

## runtime 性能

1. 不阻塞 worker（ASYNC-03/AX-08）：`std::fs`/`std::thread::sleep`/`reqwest::blocking`/rusqlite、diesel 同步驱动/`std::process::Command::output`（PR-09）/argon2、bcrypt、图片、大 JSON 序列化——全部离开 worker。`tokio::spawn` 不是逃生口，它还在同一 worker 池。偶发粗块 → `spawn_blocking`；持续并行 CPU → rayon 池 + `oneshot` 回传（CC-04），否则 512 个阻塞线程被 CPU 占满后 `tokio::fs` 也跟着排队（CC-09）。

```rust
// ✗ worker 上跑 argon2：同一 worker 的其他请求全部冻住几百毫秒
async fn signup(Json(req): Json<SignUp>) -> Result<StatusCode, AppError> {
    let hash = argon2_hash(&req.password)?;
    // …
}
// ✓ 两个 ? 分别是 JoinError（任务 panic）与业务错误；AppError 需 From<JoinError>
async fn signup(Json(req): Json<SignUp>) -> Result<StatusCode, AppError> {
    let hash = tokio::task::spawn_blocking(move || argon2_hash(&req.password)).await??;
    // …
}
```

2. `State<T>` 每请求 clone 一次 `T`：要么 `Arc<AppState>`，要么字段全是句柄（`PgPool`/`reqwest::Client`/`Arc<Config>`）。`#[derive(Clone)]` 的 state 里直接放 `Vec`/`HashMap`/`String` = 每请求深拷贝（AX-01/PERF-03）。
3. `Mutex<HashMap>` 热点：先用 tokio-console poll 时长或 `perf lock` 证明竞争（META-02/CC-13），再按 CC-13 顺序：缩临界区（锁内不算不分配）→ `DashMap`/按 key 分片 → 读多写少换 `RwLock`（注意写者饥饿）→ 单一所有者任务 + 有界 mpsc（ASYNC-01/ASYNC-05）。`tokio::sync::Mutex` 不更快，只是能跨 await；跨 await 持锁 = 整个服务按锁串行（ASYNC-02）。
4. `Bytes` 零拷贝：透传/代理直接 `Bytes` 进 `Body::from`，`slice()` 不复制；`String`/`Vec<u8>` 转 `Body` 接管缓冲也零拷贝；`Json<T>` 必走 `serde_json::to_vec`，几 MB 的 JSON 是 CPU 活（第 1 条）或改流式 `Body::from_stream`（AX-07）。静态资源 `Bytes::from_static(include_bytes!(..))`。
5. worker 数：默认 = `available_parallelism()`，Linux 上读 cgroup CPU quota（k8s `limits.cpu`）；只设 `requests` 不设 `limits` 时探到的是宿主机核数，64 个 worker 挤 2 核配额 → 全是上下文切换。修法：`TOKIO_WORKER_THREADS=2` 环境变量，或 `#[tokio::main(flavor = "multi_thread", worker_threads = 2)]`，改动附 tokio-metrics 前后（CC-08）。不要为了「更快」往上调。
6. 诊断：`console-subscriber` + `RUSTFLAGS="--cfg tokio_unstable"`（feature 门控的诊断构建，不进生产镜像）。看三项：任务 busy 占比高 = 在 worker 上阻塞；任务详情页 poll 时长直方图出现几十 ms 的 poll，或 `never yielded` 警告（busy ≥1s 触发）= 大循环不 yield（CC-11，插 `yield_now().await` 或拆块）；`lost waker` = future 永不前进（AS-13）。`tokio-metrics` 的 `TaskMonitor` 稳定版可长期进指标。
7. 后台任务：长驻进 `TaskTracker` + `CancellationToken`（见停机序列）；请求内扇出用 `JoinSet` 并限并发（AS-07），join 结果必查 `is_panic()`（ASYNC-04/AS-05）。丢 `JoinHandle` 的任务死了没人知道。
8. 池与边界对齐：`max_connections` 按 SX-02 定；HTTP 边界并发上限（`GlobalConcurrencyLimitLayer`/`load_shed`，接线见 [middleware.md](middleware.md)）与池大小同量级——否则 1000 并发排 5 条连接，全部等完 `acquire_timeout` 才 503，不如在边界早拒（AX-05）。

## 『服务卡死/变慢』根因表

| 症状 | 根因 | 定位手段 | 修法 | 规则 |
|---|---|---|---|---|
| 单客户端飞快，并发一上 p99 爆炸 | handler/WS 任务里同步阻塞或重 CPU | tokio-console busy 占比；`samply`/`perf` 火焰图在 worker 线程看到同步栈 | async 替身 / `spawn_blocking` / rayon 桥 | ASYNC-03、AX-08、CC-04 |
| 请求不报错，一直挂到客户端超时 | 池无 `acquire_timeout` 饱和排队；事务里 await 外部调用占着连接 | 池 `size()`/`num_idle()` 指标、`pg_stat_activity` | `acquire_timeout` → 503；事务只含本库语句 | SX-02、SX-07 |
| RPS 恰好 ≈ 1 / 某段代码耗时 | 锁跨 await 或全局大锁 | tokio-console poll 时长；`perf lock` | 缩临界区 → 分片 → 消息传递 | ASYNC-02、AX-03 |
| 压到约 1k 连接不再 accept，日志 `Too many open files` | fd 上限 1024 | `cat /proc/<pid>/limits`、`ss -s` | 容器 `--ulimit nofile`/systemd `LimitNOFILE`；边界并发上限 | AX-05 |
| 每次发布一波 5xx / connection reset | 无 graceful shutdown；或 readiness 没先翻红就停 accept | 发布窗口错误率 + reset 计数 | 双信号 + ready=false + 摘流等待 + drain 上限 | AX-06、SH-04 |
| SIGTERM 后等满宽限被 SIGKILL | SSE/WS/后台任务不响应取消，drain 永不结束 | 停机日志里的在途连接数与任务数 | `CancellationToken` 广播 + `drain_grace` 兜底 | AS-04、AX-04 |
| 容器 2 核配额却 64 个 worker，CPU 全在切换 | 只设 requests 没设 limits，探测核数 = 宿主机 | 启动日志 `available_parallelism` | `TOKIO_WORKER_THREADS` / 显式 `worker_threads` | CC-08 |
| `spawn_blocking` 的文件 IO 也开始排队 | 持续 CPU 重活占满阻塞池 | tokio-metrics blocking 队列深度 | rayon 池 + oneshot | CC-09、CC-04 |
| 内存随流量线性涨直到 OOM | 收全量 body、`fetch_all`、无界 channel、内存拼大响应 | dhat/heaptrack；看 `DefaultBodyLimit` 是否缺 | 流式 + 有界 | AX-05、AX-07、ASYNC-05、SX-05 |
| 后台任务三天前就死了没人知道 | 丢 `JoinHandle`、panic 被吞 | JoinSet 结果 / 任务存活指标 | `TaskTracker`/`JoinSet` + `is_panic()` 处理 | ASYNC-04、AS-05 |
| 一个请求 panic 整进程退出 | `panic = "abort"` 抄自 CLI 模板 | 退出码 134 + 无 500 日志 | 删 abort；`CatchPanicLayer` → 500 | ERR-04 |
| 间歇 1–2 s 延迟尖刺 | 单任务长时间不 yield；musl malloc 争用 | tokio-console poll 时长直方图 / `never yielded` 警告；火焰图 malloc 占比 | `yield_now`/拆块；mimalloc 后压测 | CC-11、SH-02 |

## 验证

1. 压测（PERF-01）：`cargo build --release` 后同机 `oha -z 30s -c 200 http://127.0.0.1:3000/api/items`（或 `wrk -t4 -c200 -d30s --latency`），前后对比 p50/p99/RPS/非 2xx 数；先 `ulimit -n 65536`；压测同时开 tokio-console 看 worker 是否被阻塞。debug 构建的数字不算数。
2. 停机冒烟：压测进行中 `kill -TERM <pid>`（或 `docker stop`，默认宽限 10s）→ 期望 0 个 5xx/reset、进程在预算内以 0 退出、DB 日志无 reset；`kubectl rollout restart` 配持续负载再跑一遍。
3. oneshot（TEST-10）：`/healthz` 恒 200；`ready=false` 后 `/readyz` 503；带 `MockConnectInfo` 的路由能取到 IP；`X-Forwarded-For` 伪造最左地址时解析结果仍是最右不可信地址。
