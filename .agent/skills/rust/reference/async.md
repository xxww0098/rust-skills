# /rust-skills:rust async [target] — 异步深审与设计

目的：审查 async 代码本身的正确性与设计。**该不该并发/用什么形态**归 [concurrency.md](concurrency.md) 选型节；全局底座 ASYNC-01..08，SIMP-07 门先过。停机/tracker 证据可引用邻接组合根，并标「邻接证据」。

## 取消安全（异步正确性的最深水区）

- AS-01 `select!` 每个未选中分支的 future 被 **drop**——逐分支回答「在任意 await 点被 drop 会丢什么」。`read_exact`/手写多步 IO 不取消安全（半读缓冲随 future 消失）；`mpsc::recv`、`Notified` 取消安全。tokio 文档标注了各 API，引用它而不是猜。
- AS-02 改造手法：把状态挪出 future（缓冲外提为循环变量、用 `&mut` 借用）、多步操作封成消息交给专职任务、或改用天然取消安全的原语。
- AS-03 任务取消语义：drop `JoinHandle` **不**取消任务（与 drop future 不同）；`abort()` 只在 await 点生效；abort 后的清理靠 Drop guard 兜底，不靠 await 之后的代码（那行可能永不执行）。
- AS-04 结构化停机：需要**统一取消信号 + 可等待归宿 + 总超时**。推荐 `CancellationToken` + `TaskTracker`（`cancel → close → wait`）；`watch`/`oneshot`/自定义 shutdown future 若能证明等价语义也算通过。判定时先搜 `watch`/`oneshot`/`TaskTracker`/`with_graceful_shutdown`，勿先查 CT 再误杀。协作停机后再用 `abort` 作兜底 ≠ 失败；**硬 `abort` 作为唯一归宿且不 join/不观测 panic** 才判失败。

```rust
// ✗ AS-01 read_exact 不取消安全：cancelled 命中 → 半读缓冲随 future 丢弃
loop {
    select! {
        r = sock.read_exact(&mut buf) => handle(&buf, r?),
        _ = token.cancelled() => break,
    }
}

// ✓ AS-02 专职读任务持有缓冲，主循环只 recv（取消安全）
loop {
    select! {
        Some(msg) = rx.recv() => handle(msg),
        _ = token.cancelled() => break,
    }
}

// ✓ AS-04 推荐停机三步 + 总超时（watch/oneshot 等价亦可）
token.cancel();
tracker.close();
timeout(Duration::from_secs(10), tracker.wait()).await?;
```

## 结构化并发

- AS-05 spawn 必入 `JoinSet`/`TaskTracker`（ASYNC-04）；join 结果必须检查 `JoinError::is_panic()`——吞掉任务 panic 的服务是「三天前就死了」事故的标准剧本。
- AS-06 `join!` 用于全都要，`select!` 用于竞速；优先级明确才加 `biased`（省随机化且语义显式）；「loop + select + 显式状态」是长任务状态机的标准形，替代散落的 spawn。

## Stream 与背压

- AS-07 集合并发显式限流：`buffered(N)` / `buffer_unordered(N)`（要顺序选前者），N 有依据并注释；裸 `join_all` 一把梭无上限并发是气味（对下游就是自我 DoS）。
- AS-08 背压贯通链路：有界 channel（ASYNC-05）→ `ReceiverStream` → 消费端；生产快于消费的证据用队列深度度量说话，不靠加大容量掩盖。

## API 与 trait

- AS-09 公共 trait 的 async：native `async fn in trait`（1.75+）为默认；需要 `dyn` 分发时——AFIT 在 dyn 位置**仍未原生稳定**——手写返回 `BoxFuture`、`async-trait`、或 dynosaur 式擦除，三选一并注明代价；下游要 spawn 则 Send bound 显式化（`trait_variant` 或手写 `+ Send`）。
- AS-10 库 API runtime 无关（ASYNC-08 深化）：签名不暴露 tokio 类型，IO 用 trait 注入；回调参数用 `AsyncFn` 系（1.85+ 稳定）替代 `impl Fn() -> impl Future` 双层仪式（SIMP）。
- AS-11 时间纪律：边界调用处处包 `timeout`（AX-04 同族）；`interval` 的 missed-tick 策略显式选择（Burst/Delay/Skip 语义完全不同）；重试 = 次数上界 + 指数退避 + 抖动 + 幂等前提，四缺一不上线。

## 底层与诊断

- AS-12 手写 `Future`/`poll`/`Pin` 是最后手段（SIMP-01）：先 combinator/`async-stream`；必须写 → `pin-project`，存 `Waker` 的唤醒正确性配并发测试；**async Drop 不存在**——异步清理走显式 `async fn close(self)`，`Drop` 只做同步兜底并对未 close 记警告（ERR-05 精神）。
- AS-13 「future 不前进」三问定位：没人 wake（丢 Waker/死 channel）？worker 被阻塞（CC-04/ASYNC-03）？锁跨 await（ASYNC-02）？工具：tokio-console 看 busy/idle/wakes，`#[instrument]` 贯通 span（OBS-02）。

## 验证

取消路径要有测试（注入 cancel 断言不丢数据、清理执行）；停机路径端到端测（统一取消 → 归宿等待 → 总超时，或证明等价）；loom 用于自写原语；tokio-console/metrics 前后对比佐证调度类改动（PERF-01）。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表（位置｜AS/ASYNC 编号｜问题｜修复）+ 验证缺口。`--apply` 或明确“修/改/实现”时：再给实际改动与验证证据。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
