# /rust-skills:rust process [target] — 多进程选型 / 子进程编排 / IPC

目的：在「多进程」确实成立的边界内，把子进程的启动、生命周期、停机与进程间通信做成正确、可观测、可验证的实现；不需要多进程时明确拒绝。[concurrency.md](concurrency.md) 管线程/runtime 选型，本 reference 只接「隔离与故障域」那一类问题：多进程替代不了线程内共享，多线程也替代不了进程边界。全局底座 SIMP-07 先行——不需要多进程就不多进程，META-02 有数据再拆。

## 选型（先问该不该，再问怎么拆）

```
什么时候多进程是对的？
├─ 隔离是第一需求：崩溃域隔离 / 内存硬上限 / 语言运行时不同（嵌入 Python 等）/ 不可信插件 → 进程
├─ 数据要共享、延迟敏感、通信频繁 → 线程/async（CC/ASYNC），进程的 IPC 序列化 + 上下文切换不是免费的
├─ 想用多进程吃满核 → 先 rayon（CC-01）；Rust 没有 GIL，fork 不会带来解释器那种收益
└─ 判据：进程边界 = 故障域边界 + 安全边界；性能是附带结果，不是首要理由（META-02）
```

- PR-01 起手用 `std::process::Command`：参数数组传参、显式环境、显式工作目录。禁 `sh -c "拼接字符串"`——用户输入拼进命令即任意执行（注入源）；禁让 shell 解析文件名中的空格/引号/元字符。给子进程传环境用 `Command::env` / `envs`，**不要**在父进程 `env::set_var` 再 spawn（Unix 多线程几乎无法证明健全，UNSAFE-11）。
- PR-02 直用 `fork`（`nix::unistd::fork`）是最后手段：fork 后子进程只许 async-signal-safe 操作、应立即 exec；多线程程序 fork 后，子进程里除 fork 线程外所有锁都处于死锁状态（分配器、日志、glibc 内部锁全中）。要用 pre-fork pool 或 fork-exec 前，先用 `Command` 把不行在哪说清楚。
- PR-03 子进程生命周期显式：`Command::kill_on_drop` 只覆盖 Drop 能跑到的路径。会话/worker 可能楔死导致 Drop 不跑——要有**活在 worker 之外**的 supervisor（进程组/Job + 登记表），超时 kill → 再 wait。禁「spawn 完不管」。项目已有 enroll/scope 辅助时，裸 `Command::spawn` 应用 clippy `disallowed-methods` 挡（门禁候选，不强迫引入外部 crate）。进程池：只有协议正常完成的 worker 才回池；超时/强杀/崩溃的进程仍在处理上一单，回池会串单（TA-43）。`Child::kill` 只杀直接子进程——worker 内再 spawn 孙进程等于杀不干净。

```rust
// ✗ PR-01 字符串拼命令：name 含分号即注入
Command::new("sh").arg("-c").arg(format!("ffmpeg -i {name}.mp4 out.mp4"));

// ✓ PR-01/03 数组传参 + 环境白名单 + 生命周期兜底
let mut cmd = Command::new("ffmpeg");
cmd.args(["-i", input]).arg("out.mp4")
   .env_clear().envs(allowlist)
   .current_dir(&root)
   .kill_on_drop(true);
let status = cmd.status()?;
if !status.success() { bail!("ffmpeg exit {status}"); }
```

## 进程池与 pre-fork

- PR-04 进程池/预派生（nginx 模型）只在「每请求一次 fork+exec 太贵」有同机基准证据时评估（PERF-01）：worker 数 = 核数预算，主进程只 fork 不干活，任何 worker 崩溃主进程可感知、可重启——故障域隔离是它唯一的买点。
- PR-05 worker 崩溃必须被观测：主进程 wait/管道心跳兜底，退出码 + stderr 摘要进结构化日志（OBS-01/02）。「worker 死了没人知道」= 多进程方案自废武功。

## 停机与信号

- PR-06 优雅停机按进程组发信号（SIGTERM → 宽限 → SIGKILL），子进程自成进程组（`setsid`/`setpgid`），否则 Ctrl-C 只打到前台父进程、孤儿子进程继续跑。Windows 无 POSIX 信号语义：用 `taskkill /T` 或 Job Object，行为差异写明（XP 精神）；信号处理用 signal-hook/ctrlc 统一收口。

## IPC 选型

- PR-07 IPC 按数据形态选：请求/响应控制面 → stdin/stdout 行协议或 UDS；高吞吐大块 → 共享内存（shm_open/memmap2 + /dev/shm）配同步原语。禁「临时文件当消息队列」与「日志文件当 IPC」。
- PR-08 管道协议必须定界与超时：`wait_with_output` 在输出大时互打死锁——stdout/stderr 管道（64K）填满后子进程阻塞等写、父进程阻塞等 EOF。大输出用 `spawn` + 流式读（`take`/`read_to_end` 在独立线程），或证明输出有界才用 `output`；每步读设超时。要合并 stdout+stderr 时优先 1.87 `std::io::pipe()` 接到同一个 `Command` 端，仍须先读完再 `wait`。

```rust
// ✗ PR-08 ffmpeg 大输出：管道填满，父子互等，服务卡死
let out = Command::new("ffmpeg").args(&args).wait_with_output()?;

// ✓ PR-08 流式读 + 超时 + 退出码
let mut child = Command::new("ffmpeg").args(&args)
    .stdout(Stdio::piped()).stderr(Stdio::piped())
    .spawn()?;
let stdout = std::thread::spawn(move || { let mut s = Vec::new(); child.stdout.take().unwrap().read_to_end(&mut s)?; Ok::<_, io::Error>(s) });
// 对 child.wait() 包超时：超时 → child.kill() → wait() 回收（PR-03）
```

## async 与跨平台

- PR-09 async 上下文用 `tokio::process::Command`（spawn + 异步 wait），禁在 async 里阻塞 `std::process::Command::output`（ASYNC-03 同族）；并发子进程数用信号量限流，别让一批请求 spawn 出无界进程风暴。
- PR-10 跨平台差异显式处理：Windows 无 fork、无 kill 信号语义，路径查找与可执行后缀不同；平台分支用 `#[cfg(target_family)]` 模块收口，CI 矩阵覆盖声明支持的平台（XP-03）。

## 错误与可观测

- PR-11 子进程失败建三类具名错误：spawn 失败 / 非零退出码 / 超时，携带 exit status 与 stderr 摘要（ERR-01）；重试 = 幂等前提 + 次数上界 + 退避（AS-11 同族），四缺一不做。
- PR-12 可观测：spawn/exit/信号事件记结构化日志字段（pid、exit_code、duration_ms）；验证清单含 `pgrep -P`/`ps --forest` 零孤儿、零残留进程树。

## 验证

子进程生命周期三路 fixture（正常退出 / 非零退出 / 超时 kill 回收）；管道死锁用大输出 fixture 复现（PR-08）；停机端到端：发信号 → 子树全部退出，`pgrep -P` 零残留；IPC 协议用 proptest 压边界长度；性能声明附同机 fork+exec vs 常驻池基准（PERF-01）。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：选型判定（该不该多进程 + 证据）+ 体检表分栏「主目标｜邻接证据」（位置｜PR 编号｜问题｜修复）+ 所需数据。`--apply` 或明确“修/改/实现”时：再给实际改动与前后数据。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
