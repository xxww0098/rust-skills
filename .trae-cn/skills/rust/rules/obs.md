## OBS 可观测性
- OBS-01[M] 生产运行路径使用项目统一的可观测机制；服务端不以临时 println/dbg 代替日志，CLI 的 stdout/stderr 属于用户接口。
- OBS-02[S] 结构化字段（info!(user_id=%id, "…")）；#[instrument] 必须 skip 大对象与敏感字段。
- OBS-03[S] 错误处理一次：要么传播（信息进 context），要么就地记录消化；禁层层重复打日志。
- OBS-04[S] 级别语义：error=需人介入 / warn=已自愈 / info=业务里程碑 / debug、trace=开发期。
- OBS-05[S] 只有 binary `main` 安装全局 subscriber；库 crate 只 emit tracing 事件，禁止 `init`/`set_global_default`。
- OBS-06[M] 非阻塞/滚动 writer 的 WorkerGuard 必须活到进程退出；测试用 `try_init` / `with_test_writer`，禁止 `init()` 进入 `#[test]`。
