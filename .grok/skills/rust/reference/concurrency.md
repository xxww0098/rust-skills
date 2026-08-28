# /rust-skills:rust concurrency [target] — 并发 / 并行 / 多线程调度

目的：为并发设计选择正确形态，并用数据优化线程、池、runtime 与竞争。[async.md](async.md) 管取消、结构化和背压语义；全局底座 ASYNC-01..08 与 D-3，SIMP-07 先行。组合根里大量 `Arc` 共享 ≠ 锁竞争（CC-13 要证据）；`TaskTracker`/`watch`/等价停机出现时标 **AS 旁注**，不得据此否决 concurrency 选型结论。

## 选型（先分形态，形态错了后面全错）

```
瓶颈是什么？（先测：perf/samply 火焰图 or tokio-metrics）
├─ IO 等待多、连接多 → 并发：async/tokio（少线程调度海量任务）
├─ CPU 算力饱和、可分块 → 并行：rayon / std::thread::scope（吃满核）
└─ 两者都有 → 混合：async 做编排与 IO，CPU 块桥接出去（CC-04）
判据（Alice Ryhl）：单次占用线程 >10–100µs 量级的计算，对 async runtime 就算「阻塞」
```

## 数据并行（rayon）

- CC-01 可分块 CPU 工作首选 `par_iter()` 系（声明式、工作窃取、自动负载均衡）；手写线程分片需说明 rayon 为何不适用。
- CC-02 粒度要够粗：单元过细则窃取与同步开销吃掉收益——`with_min_len`/`chunks` 调块；加速比曲线（1/2/4/8 核）是验收证据（PERF-01）。
- CC-03 rayon 全局池按部署核数配置（`RAYON_NUM_THREADS`/`build_global`）；库代码禁改全局池（污染宿主，WS-10 精神），要隔离就建局部 `ThreadPool`。
- CC-04 **rayon/重 CPU 禁止直接跑在 tokio worker 上**（饿死 IO 调度，ASYNC-03）。桥接三选一：`spawn_blocking`（偶发、粗块）；rayon 池 + oneshot 回传（吞吐型：`pool.spawn(move || { let r = work(); tx.send(r) })` 后 `rx.await`）；独立专用线程（长驻有状态）。反向同理：rayon 线程里禁 `block_on` runtime 句柄。

```rust
// ✗ CC-04 rayon 直接占 tokio worker：IO 调度被饿死
async fn handler(data: Vec<Item>) -> Vec<Out> {
    data.par_iter().map(heavy).collect()
}

// ✓ 桥接：rayon 池算、oneshot 回传（worker 只在 await 等待）
async fn handler(data: Vec<Item>) -> Result<Vec<Out>, Error> {
    let (tx, rx) = tokio::sync::oneshot::channel();
    rayon::spawn(move || { let _ = tx.send(data.par_iter().map(heavy).collect()); });
    Ok(rx.await?)
}
```

## 线程与调度

- CC-05 手写线程用 `std::thread::scope`（借用局部数据、自动 join，杜绝泄漏 handle）；长驻线程用 Builder 命名 + 必要时 stack 大小（可观测性起点）。
- CC-06 线程数 = 按角色预算：CPU 池 ≈ 物理核；IO/阻塞池另算；「每任务一线程」超过几十个即设计气味 → 池化或 async。
- CC-07 核绑定（affinity）/优先级是最后手段：仅在尾延迟敏感且火焰图证明调度抖动后用，跨平台行为差异写明；thread-per-core 架构（glommio/monoio 系）[MAY] 仅在共享状态可按核分片时评估。

## tokio runtime 调优

- CC-08 默认参数是对的居多：`worker_threads` 缺省=核数；改动必须附 tokio-metrics 前后对比（META-02）。容器内注意 cgroup 配额与探测核数不符 → 显式设。
- CC-09 阻塞池（`max_blocking_threads`，缺省 512）是给阻塞 IO 的，不是免费 CPU 池——CPU 重活走 CC-04 的 rayon 桥。
- CC-10 隔离多 runtime [MAY]：延迟敏感面与吞吐面互相踩踏时，拆两个 runtime 各管各的线程组（同一进程可多 runtime）；先证明踩踏（worker 忙时长/steal 次数），再拆。
- CC-11 长循环任务插 `yield_now().await` 或 `coop` 预算意识：单任务霸占 worker 会拖垮同 worker 所有任务的尾延迟（tokio-console 的 busy 时长可证）。

## 原语与竞争

- CC-12 channel 选型表：一对一取值 `oneshot`；多生产单消费 `mpsc`（有界，ASYNC-05）；广播最新值 `watch`；广播事件 `broadcast`（注意 lag 丢弃语义）；同步线程间用 crossbeam。拓扑上「管道 + 单一所有权」优先于「共享大状态」（ASYNC-01）。
- CC-13 锁竞争诊断后再优化：先证据（perf lock / parking_lot 竞争计数 / tokio-console poll 时长）→ 缩临界区 → 分片（dashmap/按 key 分桶）→ 读多写少换 `RwLock`（注意写者饥饿）→ 最后才是无锁/atomics（ASYNC-07：Ordering 论证 + loom）。
- CC-14 伪共享：相邻热原子/计数器用 `crossbeam_utils::CachePadded` 隔开——仅在剖析显示缓存行弹跳后（不预防性乱加，SIMP 精神）。
- CC-15 并发**正确性**按 [testing.md](testing.md) 的 TEST-15 选层：顺序模型 → loom → shuttle → Miri；禁 `sleep` hammer 当证明。详见测试 playbook，本文件不重复形状。
- CC-16 并行**收益**与正确性分开验：与串行结果按规格相等 + 1/2/4/8 核加速比（CC-02、PERF-01）。不测 rayon 框架本身。偶发红走 TEST-14（火焰山），不是再开几条线程碰运气。

## 验证

原语正确性：顺序模型常驻；loom 穷举 + Miri 在 G4（TEST-15、CC-15）；调度观测：tokio-console（开发）/ tokio-metrics 导出（生产，OBS 管道）；并行收益：加速比曲线 + 火焰图前后（PERF-01、CC-16，全部同机）；死锁：压测 + `parking_lot` deadlock detection [MAY]。偶发红先隔离再修（TEST-14），禁止 CI retry 当修复。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：形态判定（选型结论与证据）+ 体检表分栏「主目标｜邻接证据」（位置｜CC/ASYNC 编号｜问题｜修复）+ 所需数据。`--apply` 或明确“修/改/实现”时：再给实际改动与前后数据。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
