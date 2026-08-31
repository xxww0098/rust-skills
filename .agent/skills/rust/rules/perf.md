## PERF 性能纪律
- PERF-01[M] 性能声明必附同机 before/after 数据（criterion/divan 或 --timings），并使用交付 profile 或与其优化语义一致的 profiling profile；debug 数据只作诊断。
- PERF-02[M] 次序固定：算法与数据结构 → 分配与布局 → 并行 → 微调。
- PERF-03[S] 冷路径不为省 clone 扭曲设计；热路径 clone 必须说明或消除。`Arc`/`Rc` 的 clone 是计数不是深拷贝。覆盖已有缓冲时优先 `clone_from`。
- PERF-04[S] samply/perf+flamegraph 看 CPU、dhat 看堆；墙钟/N+1/HTTP/锁先 instrumentation（HP），不要用采样解释 async wait。bench 用 black_box 和生产分布数据。不要 `collect` 再立刻遍历——迭代器直接消费。
- PERF-05[Y] 执行清单参考 nnethercote《The Rust Performance Book》。smallvec/arrayvec 只在剖析证明短向量分配热时引入。
- PERF-06[M] 火焰图主宽条是 `[unknown]` / 无符号 `main` 时禁止点名热点或改码；先修 `line-tables-only`、帧指针或采集权限。Linux `sysctl`/`setcap` 只打印，用户同意后由用户执行。
