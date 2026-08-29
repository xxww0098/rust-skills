# 高层剖析（hotpath）

目的：后端「慢」先拿**确定性信号**（查询次数、串行 HTTP、锁持有、通道积压、分配字节），再决定要不要开火焰图。权威：[hotpath 完全指南](https://hotpath.rs/blog/profiling-rust-guide)（与 [BV18cbQ6vEu4](https://www.bilibili.com/video/BV18cbQ6vEu4/) 同源）、[vs samply/flamegraph](https://hotpath.rs/blog/sampling_comparison)、[overhead](https://hotpath.rs/profiling_overhead)。crate **`hotpath` 0.24.x**（官方钉 `^0.24`，2026-08）。本文件不是新命令，owner 仍是 `/bench`。

> 「优化 CPU 热路径可能省微秒；去掉一次多余 DB 往返或并行独立 HTTP，常常从响应里砍掉几百毫秒。」

## HP 检查单

- HP-01 **层序**（按 ROI，禁止跳）：SQL/HTTP → I/O 吞吐 → 锁/通道 → 分配 → CPU 采样。用户说「慢 / 剖析」没点名火焰图 → 停在本文件。点名 samply/火焰图才走 [profile.md](profile.md)。假优化：第一反应 `cargo flamegraph`。
- HP-02 **墙钟 ≠ CPU**。采样（samply/`cargo flamegraph`/`perf`）看「CPU 花在哪」；instrumentation（`#[hotpath::measure]`）看「墙钟为何慢」，含 `.await` 等待。async I/O 上采样会把时间算到 executor，看起来像运行时热、业务冷——那是采样对了执行器，不是业务没问题。[sampling comparison](https://hotpath.rs/blog/sampling_comparison)：CPU-bound 两者一致；async I/O 必须墙钟。criterion 答「快了吗」，hotpath 答「为什么慢」。
- HP-03 **N+1 用查询次数**，不是火焰图宽度。指南：21 次 SELECT → 1 次 JOIN，函数 104µs→70µs；常见可到 10×。sqlx/Diesel/Toasty 可自动记 SQL；**SeaORM 无一等 tracing** → 计往返走 [seaorm.md](../seaorm.md) SO-04/13，不要假装 `hotpath` 能拆 Entity Loader。
- HP-04 **独立 HTTP 禁止串行 await**。墙钟 ≈ 各请求之和 → `tokio::try_join!` / `join_all`，墙钟 ≈ max。指南：874ms→396ms（~2.2×）。进程级 `Client` 仍走 AX-02，不要每请求 `Client::new`。
- HP-05 **I/O 看 KB/s**，不只看函数时间。指南：Brotli 配错 27.9 KB/s（响应 126–230ms）→ 1.6 MB/s（<9ms）。用 `hotpath::io!` 包 `Read`/`Write`/`AsyncRead`/`AsyncWrite`。
- HP-06 **锁不跨 `.await`**（同 ASYNC/CC）。`acquire` 高 = 持有者慢；`wait` 高 = 被堵。指南：写锁包住 HTTP，读 P95 1.11s → 先下载再加锁，P95 9.42µs。`hotpath::mutex!` / `rw_lock!` 支持 std / parking_lot / tokio / async-lock。
- HP-07 **通道 `Max queue` 要低且稳**。积压 + send→recv 秒级 = 消费者慢或无界队列。过通道 `clone String` → `Arc<str>`（指南：4.8 GB 分配 → 25.1 KB）。`hotpath::channel!` 默认 wrap；legacy proxy 3.5–11µs/次，不要默认开。
- HP-08 **CPU 采样最后**。regex 每次 `Regex::new` 占 92% CPU → `OnceLock`/`LazyLock`（[optimize.md](optimize.md)）。exclusive 采样才是 self。无符号图仍走 PERF-06，禁止猜热点。
- HP-09 **功能门才是零成本**。`hotpath` / `hotpath-alloc` / `hotpath-cpu` 全是 feature；关掉则宏 no-op、依赖不进构建。生产 default features **不要** 开 profiling。`#[hotpath::measure]` ~40ns/次——标业务单元，不要标 getter。子微秒热循环相对开销最大；4µs 函数约 1% 税。
- HP-10 **宏顺序与分配器**：tokio 项目 `#[tokio::main]` 在 `#[hotpath::main]` **之上**。`hotpath-alloc` 换 jemalloc/mimalloc 时由 hotpath **包住**你的全局分配器，不要各装一套。axum 路由可把 SQL/出站 HTTP 记到具体 endpoint。
- HP-11 **不要把 Diff/CI 噪声当回归**。共享 runner 常见 10–15% 偏差（指南自述）。`hotpath Diff` 2026-08 仍是 waitlist，禁止当必装门禁。前后对比仍 PERF-01（同机、交付 profile、区间不重叠）。

```rust
// ✗ HP-01 先开火焰图；HP-03 N+1；HP-04 串行 HTTP；HP-06 锁跨 await
for p in posts { comments(p.id).await?; }
let a = client.get(u1).send().await?;
let b = client.get(u2).send().await?;
let mut g = lock.write().await;
client.get(url).send().await?;

// ✓ 一次 JOIN；并行 HTTP；慢活在锁外
let (a, b) = tokio::try_join!(client.get(u1).send(), client.get(u2).send())?;
let body = client.get(url).send().await?;
*lock.write().await = body;
```

```toml
[dependencies]
hotpath = "0.24"
[features]
hotpath = ["hotpath/hotpath"]
hotpath-alloc = ["hotpath/hotpath-alloc"]
hotpath-cpu = ["hotpath/hotpath-cpu"]
```

```rust
#[tokio::main]
#[hotpath::main]
async fn main() { /* … */ }
```

`cargo run --features='hotpath,hotpath-alloc'`。未授权不往 Cargo.toml 加依赖。

## 验证

确定性信号前后对比：SQL 条数、HTTP 并发度、锁 wait/acquire、通道 Max queue、分配字节、再墙钟 p50/p99（PERF-01）。采样图只解释 CPU 层。
