## ASYNC 并发
- ASYNC-01[S] 先按状态所有权与一致性需求选择消息传递、锁或 atomics；复杂度更高的原语须有正确性或性能理由。
- ASYNC-02[M] std/parking_lot 锁 guard 禁跨 .await（clippy::await_holding_lock）；先缩临界区，再考虑 tokio::sync::Mutex。
- ASYNC-03[M] async 里禁阻塞（std::fs、thread::sleep、阻塞客户端、长 CPU）→ spawn_blocking/rayon。
- ASYNC-04[M] spawn 的任务必须被管理（JoinSet/TaskTracker），错误必须被观测；禁丢弃 JoinHandle。
- ASYNC-05[M] channel 默认有界；无界必须注释论证内存上界。
- ASYNC-06[S] select! 逐分支确认取消安全；停机用统一取消信号（CancellationToken 或可证等价的 watch/oneshot/shutdown future）+ 可等待归宿 + 总超时（细节见 AS-04）。
- ASYNC-07[M] 手写 atomics：每个 Ordering 注释论证（SeqCst 不是免检牌）+ loom 测试。
- ASYNC-08[S] 库尽量 runtime 无关；绑定 tokio 用 feature 门控。
