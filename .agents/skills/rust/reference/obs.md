# /rust-skills:rust obs [target] — tracing 可观测性

目的：在有 `tracing` / `log` / `println!` 生产路径、或用户问「日志 / span / RUST_LOG / OpenTelemetry / 日志丢了」时审查或接线。现行线 **tracing 0.1.x**（crates.io 0.1.44）+ **tracing-subscriber 0.3.x**（crates.io 0.3.23；`env-filter` 必开，生产加 `json`）。axum 的 TraceLayer / request-id 走 [axum/observability.md](axum/observability.md)；本命令管进程级 subscriber、库/二进制分界、字段纪律、测试与 CLI/服务分界。裸调用只体检。
不要读：当前改动没有日志/tracing 证据、且用户没问可观测性时停。CLI 的 stdout 是用户接口，不要当成日志缺口。

## TR 检查单（体检输出：位置｜编号｜问题｜修复）

**谁装 subscriber（进程一次）**

- TR-01 `tracing_subscriber::registry().with(filter).with(layer).init()` 只在 **binary `main`** 调一次、早于业务。第二次 `init()` panic。`.with()` / `.init()` 来自 `prelude::*`。已有 `env_logger`/`tauri-plugin-log` 再装 = 「logger already set」。测试里用 `try_init`（TR-13），不要 `init()`。
- TR-11 **库 crate 禁安装 subscriber**（OBS-05）。库只 `tracing::info!` / `#[instrument]`；由二进制决定 fmt/json/OTel。`set_global_default` 放进 `lib.rs` = 下游应用一启动就撞全局。
- TR-02 过滤用 `EnvFilter::try_from_default_env()` 带回退，不用 `from_default_env()`（写错指令被静默忽略；未设 `RUST_LOG` 时只剩 ERROR）。回退开发 `info,<crate>=debug`，生产 `info`。应用专用变量 `from_env("APP_LOG")`。指令按 **target** 写：`myapp=debug,hyper=warn,reqwest=warn,tower=warn`，禁止生产 `RUST_LOG=debug` 打穿依赖。
- TR-19 **`fmt::init()` ≠ `fmt().init()`**（OBS-07）。`tracing_subscriber::fmt::init()`（有 `env-filter`）≈ `fmt().with_env_filter(EnvFilter::from_default_env()).init()`，无 `RUST_LOG` → **ERROR**。`fmt().init()` 不配 filter → SubscriberBuilder 默认 **INFO**。禁止以为两个便利函数等价；一律 `try_from_default_env().unwrap_or_else(|_| "info".into())`。禁止 `EnvFilter::new("trace")` 写死全局级别。
- TR-03 **同一 writer 一层 fmt**：TTY/开发 `.pretty()`，生产/文件 `.json()`（feature `json`）。stdout 上 pretty/json 用 `.boxed()` 二选一。**禁止**两个 fmt 层写同一个 writer（每行打两遍）。
- TR-20 **多消费者 = Registry + Layer**（OBS-07）。`fmt().init()` 只能配一个 FmtLayer + 一个全局 EnvFilter。要「控制台 pretty + 文件 json」必须 `Registry::default().with(env_filter).with(stdout_layer).with(json_layer).init()`。文件层 `.with_writer(non_blocking).json().with_ansi(false)`；pretty 只给 TTY。`ErrorLayer`（`tracing-error`）是 MAY，不默认加 crate。

```rust
use tracing_subscriber::{fmt, prelude::*, EnvFilter, Registry};
fn init_tracing(json: bool) {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| format!("info,{}=debug", env!("CARGO_CRATE_NAME")).into());
    let layer = if json { fmt::layer().json() } else { fmt::layer().pretty() };
    Registry::default().with(filter).with(layer).init(); // 只在 main；要第二 sink 再 with() 另一个 writer
}
```

**非阻塞、文件、测试**

- TR-12 热路径日志走 `tracing-appender::non_blocking`；返回的 `WorkerGuard` **必须活到进程退出**（OBS-06）。写成 `let _ = non_blocking(...)` 或函数结束就 drop = 缓冲日志丢失，症状是「崩溃前最后几行没有」。滚动文件 `rolling::daily(dir, prefix)` 仅在需要落盘时用；stdout 服务优先让编排采集 stdout。
- TR-13 测试：`fmt().with_test_writer().try_init()`（忽略 AlreadySet）。禁止 `#[test]` 里 `init()`（毒化并行测、偶发 panic）。断言优先查可观察行为，不要把整行日志字符串当契约；要锁字段时用 `tracing-test` / `with_test_writer` 捕获后再搜 `request_id=`。
- TR-17 `console-subscriber` / tokio-console **只进 dev/debug profile**，禁止打进生产 subscriber（性能与端口暴露）。

```rust
// ✓ main 持有 guard 直到 return
let (writer, guard) = tracing_appender::non_blocking(std::io::stdout());
tracing_subscriber::fmt().with_writer(writer).with_env_filter(filter).init();
run()?;
drop(guard); // 显式 flush；或让它活到 main 结束
```

**字段、span、错误**

- TR-04 事件是常量消息 + `key = value`（`%` Display、`?` Debug）。禁止 `info!("user {id} fetched")` 把变量揉进句子（OBS-02，不可过滤）。
- TR-14 span **名是静态类别**（`"http"` / `"sql.query"`），基数走字段。禁止 `info_span!("GET {}", uri)`（每个 URL 一个 span 名，后端按量计费/丢掉）。HTTP 聚合键是路由模板，见 axum 的 `MatchedPath`。
- TR-16 `span.record("k", v)` 只对创建时用 `tracing::field::Empty` 预声明的字段生效，未声明则**静默丢弃**。要事后填的（status、user_id、latency_ms）必须先 `Empty`。
- TR-05 `#[instrument]` 默认 Debug 全部参数：生产写 `skip_all`，再用 `fields(...)` 挑。`State` / 请求体 / 密钥一律 skip（OBS-02）。**只标业务边界**（handler / service / repository），禁止每个私有 helper 都 instrument（span 创建有成本）。`Span::enter()` 禁止跨 `.await`（guard 是 thread-local，跨 await 会挂错任务或泄漏）；async 用 `#[instrument]` 或 `.instrument(span)`。`tokio::spawn` **不继承**当前 span，必须显式 `.instrument(...)`；`spawn_blocking` 把 `Span::current()` move 进去再 `enter()`。
- TR-21 第三方也走 tracing 时，用 `span.in_scope(|| third_party())` 把那段执行绑进当前 span；改不了的 `log` facade 走 TR-10 桥，不要包一层假 span 名。
- TR-22 `FmtSpan::FULL` / span 生命周期事件（new/enter/exit/close）只在排 span 嵌套时开；生产默认关。`span!(Level::INFO, ...)` 的级别只管这些生命周期事件，**不管** span 内 `error!`/`debug!` 的事件级别。
- TR-15 昂贵 `Debug` 先 `tracing::enabled!(Level::DEBUG)` 再格式化，或改 `%` Display。`debug!(?huge_vec)` 在过滤掉 DEBUG 时仍可能先把 vec 格式化完（视调用方式）；热路径禁止。
- TR-06 错误只记一次（OBS-03）：要么 `?` 把上下文放进错误类型，要么就地记录并消化。禁 handler + `#[instrument(err)]` + 中间件三层各打一条 ERROR。
- TR-07 级别（OBS-04）：error=需人介入 / warn=已自愈 / info=业务里程碑 / debug、trace=开发期。4xx、可重试抖动不是 ERROR。

```rust
// ✗ 基数爆炸 + 揉句子
let span = tracing::info_span!("GET {}", req.uri());
tracing::info!("user {id} fetched");

// ✓ 名静态，值进字段；未就绪的键先 Empty
let span = tracing::info_span!("http", matched_path, status = tracing::field::Empty);
span.record("status", 200);
tracing::info!(user_id = %id, "fetched");
```

**形态边界**

- TR-08 服务端禁 `println!`/`dbg!` 当日志（OBS-01）。CLI：stdout 给用户、诊断走 stderr/`tracing`；成功路径不要打 INFO 刷屏。
- TR-09 OpenTelemetry 只在真有导出后端时接。单服务 JSON 日志够用（不要为「将来可观测」加 otel 全家桶，SIMP-01）。接了 OTel：registry 上的全局 `EnvFilter` 会同时滤掉导出 span；要「控制台 info、OTel debug」用 per-layer `layer.with_filter(...)`。停机必须 `provider.shutdown()`，否则 batch 队列丢失。形状见 [axum/observability.md](axum/observability.md)。
- TR-10 `log` facade：旧库打 `log::info!` 时用 `tracing-log` **单向**桥进 tracing。禁止 tracing→log 与 log→tracing 同时开（环）。不要并存 `env_logger` + tracing 两套全局 logger。
- TR-18 `max_level_*` / `release_max_level_info` 是编译期剥 DEBUG 的 MAY：有体积/热路径证据再开；不要默认给每个 crate 加。

有 axum 证据时叠加 [axum/observability.md](axum/observability.md)（TraceLayer、MatchedPath、request-id、utoipa）。有 Tauri 证据时看 [tauri/plugins.md](tauri/plugins.md) 的 log 插件：它是 `log` facade，与 tracing 二选一。CLI 证据叠加 [cli.md](cli.md) 的 CL-10。本命令管到 TR-22；TR-01..18 仍有效。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表 + 按收益排序候选（TR 编号 + OBS 规则号）。`--apply` 或明确“修/改/实现”时：再给实际改动。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
