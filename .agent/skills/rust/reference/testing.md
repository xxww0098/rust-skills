# 测试怎么写：并发 / 并行 / 火焰山 / agent 预算

目的：补测试、测竞态、测 rayon、处理偶发变红、或「agent 测文件越写越多」时加载。规则号在 [../rules/test.md](../rules/test.md)（TEST-01..16）；并发选型仍走 [concurrency.md](concurrency.md)；性能数字走 [bench.md](bench.md)。**火焰图**（samply/perf）是观测，**火焰山**在本文件 = 并发下偶发变红的测试地狱。

## 先问测什么（TEST-10/13）

每个新 `#[test]` 必须能填完这一行，填不出就不要写：

```
不变量：<一句话规格>    会因何失败：<哪种输入/交错>    已有覆盖：<文件:行 或「无」>
```

- 已有测试锁了同一不变量 → 改夹具或加断言，不新建文件、不加新函数名。
- 一次行为改动默认 **1–3** 个测试。想加第 4 个：列出不变量清单，等人说「加」再写。
- 禁止：`assert_eq!(f(x), f(x))`、把当前实现输出贴进 `assert_eq!`（TEST-08）、每个 pub 函数一条、为行覆盖率拆分支、新 `tests/foo.rs` 只因「看起来整齐」。
- 新性质完全包含旧测试 → 删或合并旧的（净变化可以是负的）。
- Agent 额外禁令：删红测试让 CI 绿；把 `assert_eq!` 改成 `assert!` 混过去；给 flake 包 retry。

## 三件不同的事，不要用同一种测法

| 你要证明的 | 不是 | 怎么测 |
|---|---|---|
| **并发正确**（交错后仍满足规格） | 「多线程跑过就算」 | TEST-15 选层：模型 → loom → shuttle → Miri |
| **并行更快**（rayon/多核） | 正确性 | 串行结果作 oracle + 1/2/4/8 核加速比（CC-02、PERF-01） |
| **多线程生命周期**（join、不泄漏、停机） | 调度排列 | `thread::scope` / 等 JoinHandle；停机测「发信号 → 零孤儿」（PR-12） |
| **火焰山已灭**（不再偶发红） | 重跑变绿 | 隔离 → 根因（时间/孤儿/全局）→ 确定性复现 → 再进 CI |

## 并发正确：选层（TEST-15）

**① 顺序规格（默认，matklad / 模型等价）**  
对实现跑并发操作，对一个单线程模型跑同一串操作，比最终状态。模型是规格，不是第二份实现。状态空间用短输入 + 种子，失败能最小化。

```rust
fn model_inc(m: &mut u32) { *m += 1; }

#[test]
fn concurrent_increments_match_model() {
    use std::sync::atomic::{AtomicU32, Ordering::SeqCst};
    let n = 8u32;
    let c = AtomicU32::new(0);
    std::thread::scope(|s| {
        for _ in 0..n { s.spawn(|| { c.fetch_add(1, SeqCst); }); }
    });
    let mut model = 0u32;
    for _ in 0..n { model_inc(&mut model); }
    assert_eq!(c.load(SeqCst), model); // 规格：n 次 inc = n，不是「看起来差不多」
}
```

这种「join 后比最终值」只能抓丢失更新，抓不住中间态竞态。中间态 / 锁/atomic 原语升级到 ②。

**② loom（小状态穷举）**  
`cfg(loom)` 把 `std::sync` 换成 `loom::sync`，在 `loom::model(|| …)` 里跑。状态必须小（几个线程 × 几个操作），否则组合爆炸。G4 每夜跑，不进 G2。生产代码用 `#[cfg(not(loom))] use std::…` 切。

**③ shuttle（loom 炸了才上）**  
随机调度，不是证明。`shuttle::check_random(f, 1000)` 固定迭代；失败打印种子，CI 钉死该种子当回归。通过 ≠ 没有 bug。

**④ Miri `--many-seeds`**  
unsafe / 自写 Send-Sync / 数据竞争。工具跑不了就记缺口（UNSAFE-04），不拿「单测绿」代替。

**⑤ async 时间**  
`#[tokio::test(start_paused = true)]` + `tokio::time::advance`。禁 `sleep(Duration::from_millis(50))` 赌调度。`select!` 分支要测取消路径（ASYNC-06），不是只测幸运胜出的那条。

**⑥ 网络 / 多主机**  
turmoil / madsim：单线程模拟多主机 + 种子复现。禁测试里真 bind 随机端口互打再 sleep 等连上。

**禁止当证明的 hammer**

```rust
// ✗ 火焰山火种：真实时间 + 未定义交错 + 无法复现
#[test]
fn hammer() {
    let c = Arc::new(Mutex::new(0));
    let mut hs = vec![];
    for _ in 0..100 {
        let c = c.clone();
        hs.push(thread::spawn(move || { *c.lock().unwrap() += 1; }));
    }
    thread::sleep(Duration::from_millis(20)); // 没 join 完就看；CI 慢就红，快就绿
    assert_eq!(*c.lock().unwrap(), 100);
}
```

Hammer 只允许：有 join、有模型、失败能用种子复现。否则删。

## 并行：测加速比，不测 rayon（CC-02/16）

- 正确性：同一输入，`par_iter` 结果与串行 `iter` **按规格**相等（集合相等或逐元素，看是否有序）。
- 性能：同机 1/2/4/8 核墙钟曲线，阈值项目自定（PERF-01）。核数不增时加速比不增 = 粒度太细或不是 CPU 瓶颈（先看火焰图，再改 `with_min_len`）。
- 不要为「证明 rayon 能用」写测试——那是依赖的事。

## 火焰山：偶发红怎么处理（TEST-14/16）

Rust CI 上最常见的火（Mergify / tokio 文档 / matklad *How to Test*）：

| 火 | 症状 | 灭法 |
|---|---|---|
| 测试间抢全局 | 单跑绿、整仓红 | 状态放测试体内；env/cwd/固定端口用 `serial_test` 或独立进程，跑完还原 |
| `OnceLock`/`Lazy` 读 env | 别的测试先改了环境 | 可配置值不要 Lazy；注入 config |
| 未 join 的 `tokio::spawn` | `dispatch task is gone` / 下一测挂 | 等 `JoinHandle` 或 `CancellationToken`；runtime Drop 前任务必须结束 |
| 真实 sleep | CI 慢机红 | `start_paused` + `advance` |
| `TempDir` 共享路径 | 并行互删 | 每个测试自己的 `tempfile` |
| `multi_thread` + `serial` 属性顺序 | 死锁 | 按 `serial_test` 文档排；能不用多线程 runtime 就不用 |
| 整仓 `cargo test` 失败就重跑 | 把竞态藏进绿 | retry=0；确认 flake 先隔离 |

Agent 看见红的分诊（先做再改代码）：

1. 同一条测试单独跑？绿 → 全局污染（TEST-16）。
2. 固定种子 / `--exact` 仍红？回归，修生产。
3. 种子变就红？火焰山，隔离 + 写确定性复现（pause/loom/种子），禁止加 sleep。
4. 缺服务/缺工具？TEST-07 fail-loud 或 `#[ignore = "…"]`，禁静默 return。

隔离文案必须含原因：`#[ignore = "flake: races on std::env in sibling test"]`。无原因的 `#[ignore]` 与静默跳过同罪。

## 形状速查

```rust
// ⑤ 暂停时间：5s 超时不必真等 5s
#[tokio::test(start_paused = true)]
async fn timeout_fires() {
    let f = tokio::time::timeout(
        std::time::Duration::from_secs(5),
        std::future::pending::<()>(),
    );
    tokio::time::advance(std::time::Duration::from_secs(5)).await;
    assert!(f.await.is_err());
}
```

```rust
// ② loom：只包原语，G4 跑。feature 由项目自定，不强迫引入
#[cfg(loom)]
#[test]
fn mutex_exclusive() {
    loom::model(|| {
        let m = loom::sync::Arc::new(loom::sync::Mutex::new(0u32));
        let m2 = m.clone();
        let t = loom::thread::spawn(move || { *m2.lock().unwrap() += 1; });
        *m.lock().unwrap() += 1;
        t.join().unwrap();
        assert_eq!(*m.lock().unwrap(), 2);
    });
}
```

## 验证

- 新测试：旧行为见红、新行为见绿（TEST-08）；`cargo test --exact <name>` 单独绿，且与全量并行不互相污染。
- 并发层：模型测试常驻 G2；loom/Miri 在 G4 或 `#[cfg(loom)]`；shuttle 失败种子钉进仓库。
- 并行：同机加速比表，没有数据只标缺口。
- 火焰山：隔离条目进债务（`audit tests` / capture），修完删 `#[ignore]`，禁止永久隔离当解决。
