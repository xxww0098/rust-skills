# Rust 工程规范（注入版 v0.0.54）

供按相关域渐进加载（先读同目录分文件，不要默认打开本合并件）；仅在明确的全规范审计时读取 `rules-full.md`。规则是决策约束，不是替代项目证据的检查表。
分级：[M]=适用前提命中后 MUST，违反即阻断；[S]=默认 SHOULD，项目约定或证据可推翻并说明；[Y]=MAY。先证明前提，再引用编号；不适用不是违规。**本规范只以 edition 2024 为基线**（MSRV ≥ 1.85，可用 `rust-version` 或 `rust-toolchain.toml` 声明）。edition 2018/2021 是待迁移债务。新 workspace 用 `resolver = "3"`；已经 2024 且钉在 resolver 2 的成熟仓不迁 resolver。新代码按 2024 语义写（RPIT 全捕获、`if let` 短临时值、`#[unsafe(no_mangle)]`、`unsafe extern`、≥1.88 let chains）。Unix 多线程禁止靠 `env::set_var` 改环境。

## 工作流
定位业务域与落点（D-1）→ 核对依赖方向 → 实现 → 自检 → 汇报。
自检：优先运行项目已有的 fmt、lint、test、gate 命令；没有项目门禁时使用最小相关 Cargo 检查。动了 Cargo.toml 看 lock/tree 影响；称性能改进附 bench 前后数据；动 profile 附 `--timings` 对比。
汇报：设计说明 1–3 句 + 规则引用 + 验证结果 + 置信度（高/中/低，低必须列缺口）+ 偏离声明（偏离 S 必填；偏离 M 必须有用户明确决定并记录风险）。
裁决：用户明确的目标、读写边界与更高层安全约束 > 技能规则；技能内部按 M > S > Y，规则冲突按 正确性>可维护>构建速度>微优化。
三振协议：编译错误先过 D-6 分诊翻译成设计问题，禁止条件反射修补（E0382→clone、E0277→加 bound、E0597→'static）；同一处 3 次修不过=三振，停止局部修补、升级设计层重新建模并记录。

## META 元规则
- META-01[M] 执行方式默认是 review/eval；只有被 xtask 真实实现、配失败 fixture 并注册的规则才升级为 machine gate。不得用固定成功桩冒充覆盖。
- META-02[M] 先量化再优化：无 timings/tree/bench 基线数据的优化一律不做。
- META-03[M] 新增规则必须同时新增可执行验证：可机械判定的补失败 fixture + 门禁；否则补独立压力/eval 场景。技能仓本身以命令级压力场景 + consistency 为准；machine gate fixture 只在用户项目落地 `gate` 后计算。
- META-04[M] 正确建模、清晰所有权、可测边界 优先于一切微优化。
- META-05[M] 风险决定验证强度：prototype 可跳过纯治理项，但不能跳过与当前改动相关的正确性、安全和数据损失防护。产物类型与成熟度分开记录，不从仓库整体推断每个 crate。
- META-06[M] `review`/`document`/`doctor`/`crate`/`distill`/`harden` 本轮只消费一份 ProjectSnapshot（[kernel/evidence.md](../kernel/evidence.md)）。禁止各命令再扫一遍 workspace 另画 crate 图。RUST.md 是画像不是事实源。Finding 必须含前提、证据、反证、所有权层（[kernel/finding.md](../kernel/finding.md)）。
- META-07[M] 任何源码写入必须先填 Patch（[kernel/write.md](../kernel/write.md)）：不变量、所有权层、规范形状、拒绝的捷径、最小验证。禁止 clone-to-compile、生产 unwrap、服务端 println、无规格测试、未授权新 crate/`pub`。写不出 Patch 就不要改文件。

## WS 工作区与结构
- WS-01[S] 多 crate 共享构建、依赖或发布生命周期时使用 workspace；新建 workspace 优先虚拟根，迁移现有根包须有实际收益。
- WS-02[Y] 新 workspace 可把成员平铺在 `crates/`；已有清晰布局不为统一外观迁移。
- WS-03[S] 不发布的内部 crate 设 `publish=false`；版本策略和可继承元数据由项目发布流程决定。
- WS-04[S] 入口保持薄，只做解析、初始化与编排；用职责而非固定行数判断。
- WS-05[M] `[workspace.package]` 统一 `edition = "2024"`。MSRV ≥ 1.85 由 `rust-version` **或** `rust-toolchain.toml` 声明（二者有一即可）。新 workspace 根清单 `resolver = "3"`；已是 2024 且 resolver 2 的成熟仓保持现状，不为统一数字迁 resolver。成员不得各自留在 2018/2021。
- WS-06[S] 优先让同一变化原因的代码相邻；业务域布局通常优于横跨全仓的技术层。现有局部性良好的结构不强迁。
- WS-07[M] 依赖单向无环；破环：共享类型下沉叶子 crate / 消费方定义 trait / 泛型回调参数化。
- WS-08[S] 避免无收益的深依赖链；是否拆 crate 以编译边界、所有权和复用证据决定。
- WS-09[S] 多成员共享的依赖版本在 `[workspace.dependencies]` 收口；仅单成员使用或需不同 feature/version 时可局部声明。
- WS-10[M] 可见性 private 起步：pub(crate) 优先于 pub；pub 即承诺。
- WS-11[S] 拆分三级，**不按行数阈值**。① 函数：clippy `too_many_lines`（默认 100）只是信号，抽函数不拆文件。② 文件/`mod`：同一文件出现**两个不变量、两套测试夹具、或两段独立变化原因**才拆 `mod`；难读/难测/增量编译变慢是证据，300–500 行只是线索。③ crate：仅 WS-12。生成代码、测试夹具表、单调用方转发层不拆。不设「文件 ≤ N 行」MUST，也不新增 `/split` 命令。
- WS-12[Y] 只有明确需要独立编译、复用、发布或依赖隔离时才把模块拆成 crate。

## TEST 测试
- TEST-01[S] 单元测试靠近实现；修复优先追加到覆盖该行为的现有测试文件，只有新的隔离/链接边界才新建测试目标；当测试体积妨碍阅读时移到同模块的 `tests.rs`。
- TEST-02[S] 集成测试按隔离需求组织；启动/链接成本明显时合并为较少测试二进制。
- TEST-03[M] 共享辅助：test-util crate > it 内模块 > 遗留 tests/common/mod.rs；禁 tests/common.rs。
- TEST-04[M]【最高优先级】每个 .rs 必须可被 mod 图到达（孤儿文件=静默失效）。
- TEST-05[M] 测试辅助不进生产 pub API（test-util crate 或非默认 feature）。
- TEST-06[Y] 无文档示例且 doctest 成本可见的内部 crate 可设 `[lib] doctest = false`。
- TEST-07[M] 外部服务测试：fail-loud（panic 指明缺什么）或 `#[ignore = "原因"]`；禁静默 return 变绿。
- TEST-08[M] 禁套套逻辑测试：期望值来自规格/手算/对偶实现，不得复述实现输出；每个断言都必须可失败并检查最强可观察不变量。修 bug 时须证明回归测试命中旧缺陷（改前、隔离旧版本或受控回滚见红）；无法安全见红则把它列为验证缺口。
- TEST-09[M] 确定性：固定种子；优先等待可观察事件/条件，无事件才带 deadline 轮询；tokio::time::pause 替代 sleep；不依赖执行顺序。
- TEST-10[S] 配比：大量快单测 + 适量公共 API 契约集成测试 + 少量端到端/bench。一次行为改动默认 1–3 个测试；想加更多先列出不变量再问，禁按函数名一人一个。
- TEST-11[S] 不变量/编解码→proptest；结构化输出→insta（diff 人审）；并发原语小状态→loom，状态空间大→shuttle；unsafe→Miri；多机/网络→turmoil/madsim；并行加速比→bench（PERF-01）。形状见 [testing.md](../reference/testing.md)。
- TEST-12[Y] 项目已采用 nextest 时沿用；否则 `cargo test` 足够。对外文档示例用 `cargo test --doc` 验证。nextest 的 retry 默认 0；确认 flaky 走隔离而不是重跑变绿。
- TEST-13[S] 补测预算：先 `rg` 现有测试是否已锁同一不变量——已覆盖则改夹具/加断言，禁新文件、禁新 `#[test]` 只为「看起来测了」。每个新测试必须能用一句话说「它会因哪条规格失败」。被新性质完全包含的旧测试删或合并。Agent 尤其禁止：镜像实现的套套测试、每个 getter 一条、为覆盖率凑分支。
- TEST-14[M] 火焰山（偶发变红）：根因是真实时间、未 join 的并发、进程级共享（env/cwd/端口/OnceLock），不是「再跑一次」。确认 flaky 先 `#[ignore = "flake: …"]` 或 nextest quarantine 移出阻断路径，再修生产代码或测法。禁止：删测试让 CI 绿、放宽断言、包 retry、加 `sleep` 碰运气。Agent 看见红必须先分「回归 / flake / 缺环境」（TEST-07），缺证据不改生产。
- TEST-15[S] 并发测试选层（由上到下，能停就停）：① 顺序规格/模型等价（同一串操作，并发结果 = 单线程模型）；② loom 穷举（锁/atomic，状态必须小）；③ shuttle 随机调度 + 固定种子（loom 炸了才上）；④ Miri `--many-seeds`（unsafe / 数据竞争）；⑤ tokio `start_paused` + `advance`（超时/重试，禁真实 sleep）；⑥ turmoil 等 DST（网络/多主机）。`thread::spawn` + `sleep` hammer 只冒烟，失败必须能用种子复现，否则不算证明。
- TEST-16[M] 默认并行跑测试。共享进程级状态的测试才串行（`serial_test` 或独立进程）；`#[tokio::test(flavor = "multi_thread")]` 只在测真并行调度时用，与 `serial` 组合要按插件文档排属性顺序，否则死锁。每测必须 join/cancel 自己 spawn 的任务，runtime Drop 时不许留孤儿。

## ERR 错误处理
- ERR-01[M] 稳定库公共 API 返回调用方可处理的具名错误并保留 source 链；可用手写 `Error` 或 thiserror。只在接口契约允许不透明错误时返回 `Box<dyn Error>`。
- ERR-02[S] 应用编排层为错误补上下文；可用 anyhow，或项目已有的 eyre/miette/等价 Report。不为这一点单独强加依赖，也不把库 API 改成 anyhow。
- ERR-03[M] 生产禁裸 unwrap；expect 仅限局部可证明不可失败且消息写成证明 `expect("invariant: …")`；测试不限。
- ERR-04[M] panic 只代表 bug；可预期失败一律 Result；禁 panic/catch_unwind 做控制流。
- ERR-05[M] 禁 `let _ = fallible()` 吞错；要忽略须记录或注释论证。
- ERR-06[S] 公共错误 enum 加 #[non_exhaustive]；消息小写、无尾句号、不重复 source 内容。
- ERR-07[S] builder/guard/句柄类返回值标 #[must_use]。
- ERR-08[S] anyhow/thiserror 不是精简前提：先 `Result` + `?`。变体少且调用方不必 `match` → 手写 enum 或具体类型，不新加 crate。禁止为「看起来专业」在同一产物里同时引入两个；禁止把 anyhow/eyre 当库的公共错误类型。项目已有其一则沿用。
- ERR-09[S] 信任边界禁裸 `xs[i]` / 入站整数 `/` `%`：用 `get`、`checked_div`、`checked_add`。库与生产路径里下标 panic 和除零 = bug（ERR-04），不是「下标当然合法」。

## API 接口与类型
- API-01[M] 非法状态不可表示：enum 替连环 bool/魔法值；互斥字段合并建模。
- API-02[M] 对外公共接口必须有足以正确使用的 rustdoc；存在对应行为时补 `# Errors` / `# Panics` / `# Safety`。仅 crate 内可见项按项目文档策略。
- API-03[S] 参数端宽（&str/&[T]/impl AsRef<Path>）、返回端窄（具体类型；无名类型用 impl Trait）。
- API-04[S] 评估 #[non_exhaustive]；不许外部实现的 trait 用 sealed。
- API-05[S] 标准 trait 尽量派生：Debug 必须（敏感字段脱敏），Clone/PartialEq/Eq/Hash/Default 按语义。
- API-06[Y] >3 个可选参数用 builder。
- API-07[S] 命名遵循 Rust API Guidelines（as_/to_/into_ 等）。
- API-08[S] parse, don't validate：信任边界用 `parse`/`TryFrom`/newtype 构造器产出领域类型；业务函数只收已合法类型，不再对同一 `String` 重复校验。wire / row / 领域 / 响应类型分离，不把 `FromRow`+`Serialize` 挂同一结构当 API。

## OWN 所有权
- OWN-01[M] 不为过编译器而 clone：引入 clone 消除 E0382/E0507 前必须先答 D-6（谁该拥有）。共享不可变用 `&`/`Arc`；确需副本时在调用点注释「为何两处都要所有权」。
- OWN-02[S] 参数借用不拥有：禁 `&String`/`&Vec<T>`/`&PathBuf`，改 `&str`/`&[T]`/`&Path`（API-03）。调用方已有所有权且函数必须留下值时再收 `String`/`Vec`。
- OWN-03[S] 需要「拿走再放回」用 `mem::take`/`mem::replace`，不先 clone 再覆盖原位。
- OWN-04[S] 只有智能指针才 `impl Deref`/`DerefMut`（API Guidelines C-DEREF）。newtype 用 `as_str`/`AsRef`/`AsMut`（C-CONV-TRAITS）。项目已对透明包装统一 Deref 并写明约定时，按约定推翻并记录，不升 M。
- OWN-05[S] `Cell`/`RefCell`/`Mutex` 是所有权拆分失败后的工具，不是默认共享模型；引入时写明互斥与重入假设。

## SIMP 精简纪律（跨域：反过度工程与零浪费）
- SIMP-01[M] YAGNI：只为已存在的变化维度抽象；单实现 trait、单调用方通用层或未来占位必须有当前测试、隔离或接口收益。
- SIMP-02[M] 抽象必须付得起解释成本：一句话说不清「挡住了什么复杂度」的层（wrapper/单纯转发 mod/胶水 trait）删除。
- SIMP-03[M] 代码量是负债：同等正确性与可读性，行数少者胜；删代码是贡献；pub 面最小（WS-10）。
- SIMP-04[M] 静态分派默认：能 fn 不 trait、能泛型不 dyn、能 enum 不 Box<dyn>；用 dyn 须说明理由（异构集合/编译时间热点）。
- SIMP-05[S] 热路径避免无收益的中间分配；在流式迭代与清晰循环中选更易读者，已知且显著的容量可预分配。
- SIMP-06[S] 仪式最小化：builder/宏/getter-setter 只有在减少重复或编码约束时引入；参数多或单处 struct 只是审视信号。
- SIMP-07[S] 不需要 async 不 async（async 传染整条调用链）；不需要并发不并发；同步直到度量说不行。
- SIMP-08[S] `match` 不是更高级的 `if`：`bool`/比较用 `if`；互斥 enum/多种形状用 `match`（穷尽）；只要一种变体往下走用 `let-else` 或 `?`。禁把 `true`/`false` 写成 `match`，也禁对三态 enum 用一串 `if let` 漏分支。2024 里为延长 `if let` 临时值才改 `match`，不是审美。2024 + rustc ≥1.88 可用 let chains 把 `if let` 与布尔条件串在同一 `if`/`while`，减少嵌套；这不是把 enum 穷尽改成 if 链的许可。
- SIMP-09[S] 本 diff 把手写源文件从 <1000 行推过 1000 行 → 默认评审红旗。处置走 WS-11：先抽函数，两不变量才拆 `mod`；**禁止为凑行数拆 crate**。生成代码 / bindings / 测试表豁免并声明。1000 不是 MUST 上限，是「必须问该不该分解」。
- SIMP-10[M] 禁把特判 `if` / 布尔 flag / 租户名钉进无关共享路径（spaghetti growth）。新分支进专用抽象、enum 状态机或策略对象；在已忙函数中间加窄边案当设计问题，不是风格。
- SIMP-11[M] 逻辑住在拥有不变量的一层（D-1）；复用已有 helper，禁近重复与 identity wrapper（SIMP-02）。feature 逻辑漏进通用模块、实现细节漏出 API = 边界漂移。
- SIMP-12[S] 无故把独立工作串成编排、或相关更新半应用，当设计味。能并行且独立则不要为「看起来有序」串行；部分成功状态比一次事务更难推理。不是微优化许可。
- SIMP-13[S] AI 过编译器味：`for i in 0..len` 复述 iterator、`clone()` 只为消 E0382（OWN-01）、`Vec<Box<dyn Trait>>` 而闭集 enum 够用（SIMP-04）。编译绿不是 idiomatic。

## ASYNC 并发
- ASYNC-01[S] 先按状态所有权与一致性需求选择消息传递、锁或 atomics；复杂度更高的原语须有正确性或性能理由。
- ASYNC-02[M] std/parking_lot 锁 guard 禁跨 .await（clippy::await_holding_lock）；先缩临界区，再考虑 tokio::sync::Mutex。
- ASYNC-03[M] async 里禁阻塞（std::fs、thread::sleep、阻塞客户端、长 CPU）→ spawn_blocking/rayon。
- ASYNC-04[M] spawn 的任务必须被管理（JoinSet/TaskTracker），错误必须被观测；禁丢弃 JoinHandle。
- ASYNC-05[M] channel 默认有界；无界必须注释论证内存上界。
- ASYNC-06[S] select! 逐分支确认取消安全；停机用统一取消信号（CancellationToken 或可证等价的 watch/oneshot/shutdown future）+ 可等待归宿 + 总超时（细节见 AS-04）。
- ASYNC-07[M] 手写 atomics：每个 Ordering 注释论证（SeqCst 不是免检牌）+ loom 测试。
- ASYNC-08[S] 库尽量 runtime 无关；绑定 tokio 用 feature 门控。

## UNSAFE
- UNSAFE-01[M] workspace 统一 unsafe_code="deny"；需要的 crate 单独放开并进本章约束。
- UNSAFE-02[M] 每个 unsafe 块前置 `// SAFETY:` 逐条对应前置条件；作用域最小化。
- UNSAFE-03[M] unsafe 封装进安全抽象，不变量不外溢；unsafe fn 内仍显式 unsafe {}。2024 默认 `unsafe_op_in_unsafe_fn`：函数标 `unsafe` 只声明调用约定，不授权体内裸 unsafe 操作。
- UNSAFE-04[S] Miri 支持的 unsafe 路径应定期运行；并发内存序在 loom 可建模时补 loom。工具不支持时记录替代证据与缺口。
- UNSAFE-05[M] 性能动机的 unsafe：先交安全版 + bench 证明不足，才允许。
- UNSAFE-06[M] panic 安全次序：可 panic 操作（分配/clone/回调）做完，才做不可逆裸操作（写指针/改 len）；任何时刻展开析构器不得见到半初始化状态。
- UNSAFE-07[M] unsafe 上下文的安全不变量检查用 assert!，禁 debug_assert!（release 被编译掉）。
- UNSAFE-08[M] 手动 impl Send/Sync 视同 unsafe：附论证注释 + Miri/loom。
- UNSAFE-09[S] 指针纪律：NonNull 优先 *mut；ptr.cast() 优先 as；禁 const→mut 转换写入；未初始化内存一律 MaybeUninit（引用/非零类型 zeroed 即时 UB）。
- UNSAFE-10[M] 2024 要求影响链接/符号的属性显式 unsafe：`no_mangle` / `export_name` / `link_section` / `naked` 写成 `#[unsafe(...)]` 并附 SAFETY（符号全局唯一、段布局正确）。裸 `#[no_mangle]` 是迁移债务，不是「已经安全」。`cargo fix --edition` 只改语法，不证明用法正确。
- UNSAFE-11[M] Unix 多线程程序禁止 `env::set_var` / `remove_var`（包在 `unsafe` 里也几乎无法证明无并发读环境；DNS/`ToSocketAddrs` 等都可能读）。给子进程传环境用 `Command::env`；测试隔离用独立进程或显式单线程证明。Windows 上这两函数是安全的，仍优先 `Command::env`，避免把测试污染进父进程。

## FFI 边界
- FFI-01[M] panic 不得跨 FFI 展开：`unsafe extern "C"` 体内 catch_unwind 收口翻译为错误码，或按 ABI 用 `extern "C-unwind"`。2024 裸 `extern "C" {` 是迁移债务（FFI-10）。
- FFI-02[M] 跨界类型稳定布局：#[repr(C)]/#[repr(transparent)]；平台类型用 std::ffi/libc 别名。
- FFI-03[M] 字符串走 CString/CStr；C 端会保存指针或指针逃逸当前调用时，CString 必须由明确所有者绑定并活过全部使用期。仅在 FFI 契约明确“不保留指针”时，`c_api(CString::new(s)?.as_ptr())` 的语句内借用才成立；契约必须记录。
- FFI-04[M] 所有权单边：谁分配谁释放；包装 C 指针实现 Drop 调对方 free；交给 C 的用 into_raw/ManuallyDrop 解除析构；禁 String/Vec 接管外部内存。
- FFI-05[M] 外部输入先验证再进强不变量类型：enum 用 TryFrom 禁 transmute；字节流用 from_utf8 禁 _unchecked。
- FFI-06[M] 不透明句柄必须隐藏布局并记录空值、别名、线程与生命周期契约；可用绑定生成的 opaque 类型或 `c_void` 指针，避免伪造可实例化布局。
- FFI-07[M] 错误跨界走错误码/out 参数；Result/Option/panic 语义不过 ABI。
- FFI-08[M] 回调过界数据与代码分离：函数指针 + user_data 成对（trampoline）；禁闭包/trait object 过界。
- FFI-09[S] 绑定用 bindgen/cbindgen 生成入库，不手写 extern。
- FFI-10[M] 2024 的 extern 块必须是 `unsafe extern "ABI"`。块内逐项标 `safe fn`（任意合法参数都健全，如 libm `sqrt`）或 `unsafe fn`（调用方须满足前置条件）；未标注默认 unsafe。`cargo fix --edition` 只加关键字，不证明签名正确，迁移后必须人工复核 ABI。

## BUILD 构建性能
- BUILD-01[M] 永不写 [profile.dev.package."*"] opt-level=3；热依赖点名覆盖 + 附 timings 证据。
- BUILD-02[M] `[profile.dev.package.<name>]` 与 `[profile.dev.build-override]` 独立评估、独立度量；后者作用于 build dependency、build script 与 proc-macro，可能导致同一包以不同配置重复构建，禁无数据强制配对。
- BUILD-03[M] 冷构建与热增量分开测量；依赖图、proc-macro、代码生成、链接和 profile 都可能影响，按 timings 证据归因。
- BUILD-04[M] timings/tree --duplicates/bloat 数据是构建优化讨论的入场券。
- BUILD-05[S] CI 的 incremental、debuginfo 与缓存策略按运行器和产物需求实测；发布/测试 profile 分开配置。
- BUILD-06[S] 链接器平台实测；x86_64 Linux ≥1.90 已默认 rust-lld，勿照抄旧建议。
- BUILD-07[M] 冷构建基线用独立临时 `CARGO_TARGET_DIR`，不得清理共享 target；`cargo sweep`/`cargo clean` 仅用于用户明确授权的磁盘清理。
- BUILD-08[S] 日常开发可 debug="line-tables-only"；split-debuginfo 平台实测。
- BUILD-09[S] rust-analyzer 与终端 `cargo` 抢同一 `target/` 锁时，给 RA 单独 `CARGO_TARGET_DIR`（官方 FAQ），不要杀进程或清缓存。
- BUILD-10[S] 构建优化优先序跟 2025 编译器调查：减依赖/关未用 default-features → 降 debuginfo → 换实测过的链接器 → timings 证明后再拆编译单元。禁把「拆成几百 crate」或 2021 年的「全仓 rust-lld rustflags」当默认方。

## DEP 依赖治理
- DEP-01[S] 多成员共享的三方版本优先收口；有意使用不同版本或 feature 时局部声明并保留理由。
- DEP-02[M] 新依赖评估 std/现有依赖的替代、维护状态、传递代价与 license；实现行数不是单独裁决标准。
- DEP-03[S] 明确理解默认 feature 后决定是否关闭；不要机械写 `default-features=false`。
- DEP-04[M] feature 必须可叠加：只增能力，不改语义、不互斥。
- DEP-05[M] optional 依赖必须配具名 feature；禁只用 #[cfg] 门控。
- DEP-06[S] 有供应链或许可要求的项目在 CI 使用 cargo-deny 等检查；重复版本只有造成风险、体积或类型不兼容时才治理。
- DEP-07[S] Cargo.lock 是否提交由 artifact、可复现交付需求与项目约定决定；应用通常跟踪，publish-only library 可选择不跟踪。已跟踪 lock 的依赖升级 diff 应作为评审对象；缺失本身不是违规。
- DEP-08[M] edition 必须是 2024。MSRV（≥ 1.85）用 `rust-version` 或 `rust-toolchain.toml` 显式钉住，CI 有对应编译任务。resolver：新仓 3；已有 2024+resolver 2 不是违规。依赖自己的 MSRV 可以高于仓基线（sqlx 0.9 为 1.94）：不要为对齐「现行稳定线」把全仓 rust-version 抬到最严依赖；该依赖上一主线仍在范围内就留在上一主线，抬 MSRV 必须写入 RUST.md 或 rust-version 变更。
- DEP-09[S] cargo hack --feature-powerset 每夜验证 feature 叠加性。
- DEP-10[Y] 高保证场景用 cargo-vet/cargo-crev。
- DEP-11[S] 已跟踪 lock 的应用：CI/`cargo` 调用必须 `--locked`（或等价 `--offline`）。禁无人值守 `cargo update` / 无 `--locked` 的解析。投毒窗口以小时计（arrayref 0.3.10 在线 86 分钟）；只有这段里跑过 update 的 lock 会吃进恶意版本。
- DEP-12[S] `cargo deny`/`audit`/`vet` 依赖已收录或已审；零日投毒头几小时沉默。冷却期（DEP-13）挡「发布后立刻被选中」；提前数月的慢投毒仍走审查（DEP-10）+ deny（DEP-06）。多层，不是银弹。
- DEP-13[S] 应用可设解析冷却期（Cargo RFC 3923，**实验性**：需 nightly `-Zmin-publish-age`，稳定前不改默认 toolchain）。crates.io 建议 7–14 days；安全敏感 ≥14；库作者短或不设；私有 registry 可 `0`。只影响新解析，不踢 lock 里已有版本。registry 无 `pubtime` 则静默失效。紧急热修：`CARGO_RESOLVER_INCOMPATIBLE_PUBLISH_AGE=allow cargo update -p <crate> --precise <ver>`，知情后改回 deny。git/path 源豁免。

## LINT 风格
- LINT-01[M] 使用项目 rustfmt 配置并在现有门禁执行 `fmt --check`；是否使用 pre-commit 由项目决定，不覆盖本地 hooks。
- LINT-02[M] lint 统一 [workspace.lints]；每成员显式 [lints] workspace=true。
- LINT-03[M] 禁源码 #![deny(warnings)]；严格度放 CI RUSTFLAGS=-Dwarnings。
- LINT-04[M] 存量违规用棘轮：基线入库，只降不升。
- LINT-05[S] 每个 #[allow] 必须带 reason。
- LINT-06[S] 基线集：clippy::all + dbg_macro/print_stdout/unwrap_used/undocumented_unsafe_blocks/await_holding_lock/missing_safety_doc/transmute_ptr_to_ptr；棘轮推进，不一次拉满 pedantic。
- LINT-07[S] 静态分析按层叠加，禁止同层重复工具。rustc=类型；rustfmt=G1；clippy=G2；cargo-deny=G3（advisories+license+bans）。deny 已开 advisories 则不再跑 cargo-audit。G4 按证据：有 unsafe→Miri；发布 lib→semver-checks；可选 feature→cargo-hack；项目已用 Kani 才保留。rust-analyzer / cargo-geiger / Rudra / MIRAI / Prusti / Sonar 不是默认 CI。
- LINT-08[S] clippy/rustfmt 与 rustc **同工具链**：`rust-toolchain.toml` `components = ["clippy","rustfmt"]`。调用 `cargo clippy --all-targets`（有 lock 加 `--locked`）。`--all-features` 仅当 feature 可组合；互斥 feature 走 GATE-05。CI 用 `RUSTFLAGS=-Dwarnings` 或 `CARGO_BUILD_WARNINGS=deny`，禁止源码 `#![deny(warnings)]`（LINT-03）。项目策略进 `clippy.toml`（`msrv`、`disallowed-methods`），不靠一长串 `#[allow]`。

## OBS 可观测性
- OBS-01[M] 生产运行路径使用项目统一的可观测机制；服务端不以临时 println/dbg 代替日志，CLI 的 stdout/stderr 属于用户接口。
- OBS-02[S] 结构化字段（info!(user_id=%id, "…")）；#[instrument] 必须 skip 大对象与敏感字段。
- OBS-03[S] 错误处理一次：要么传播（信息进 context），要么就地记录消化；禁层层重复打日志。
- OBS-04[S] 级别语义：error=需人介入 / warn=已自愈 / info=业务里程碑 / debug、trace=开发期。
- OBS-05[S] 只有 binary `main` 安装全局 subscriber；库 crate 只 emit tracing 事件，禁止 `init`/`set_global_default`。
- OBS-06[M] 非阻塞/滚动 writer 的 WorkerGuard 必须活到进程退出；测试用 `try_init` / `with_test_writer`，禁止 `init()` 进入 `#[test]`。
- OBS-07[S] `fmt::init()`（无 RUST_LOG→ERROR）≠ `fmt().init()`（默认 INFO）；生产一律 `EnvFilter::try_from_default_env` 带回退。多 sink 用 Registry+Layer，每个 writer 一层 fmt；同一 writer 禁止两层。`#[instrument]` 只标业务边界。

## PERF 性能纪律
- PERF-01[M] 性能声明必附同机 before/after 数据（criterion/divan 或 --timings），并使用交付 profile 或与其优化语义一致的 profiling profile；debug 数据只作诊断。
- PERF-02[M] 次序固定：算法与数据结构 → 分配与布局 → 并行 → 微调。
- PERF-03[S] 冷路径不为省 clone 扭曲设计；热路径 clone 必须说明或消除。`Arc`/`Rc` 的 clone 是计数不是深拷贝。覆盖已有缓冲时优先 `clone_from`。
- PERF-04[S] samply/perf+flamegraph 看 CPU、dhat 看堆；bench 用 black_box 和生产分布数据。不要 `collect` 再立刻遍历——迭代器直接消费。
- PERF-05[Y] 执行清单参考 nnethercote《The Rust Performance Book》。smallvec/arrayvec 只在剖析证明短向量分配热时引入。
- PERF-06[M] 火焰图主宽条是 `[unknown]` / 无符号 `main` 时禁止点名热点或改码；先修 `line-tables-only`、帧指针或采集权限。Linux `sysctl`/`setcap` 只打印，用户同意后由用户执行。

## GATE 门禁
- GATE-01[S] 本地与 CI 应复用同一组检查入口；沿用项目已有脚本/任务系统，只有复杂度值得时才新增 `cargo xtask gate`。
- GATE-02[M] 门禁覆盖不得静默减弱；删除过时检查或放宽阈值须显式记录理由、影响与补偿证据。
- GATE-03[S] 棘轮基线文件入库，变更走评审。
- GATE-04[S] 已跟踪 lock 的应用：G3 CI 必须 `--locked`；禁流水线里的 `cargo update`（DEP-11）。G4 可选 `cargo +nightly -Zmin-publish-age` 验证解析冷却（DEP-13），**不**把 nightly 当默认构建工具链。
- GATE-05[S] G4 feature 矩阵用 `cargo hack check --feature-powerset --no-dev-deps`（[taiki-e/cargo-hack](https://github.com/taiki-e/cargo-hack)）；库有可选 feature 才加，不默认引入。`--each-feature` 不够（漏组合）。未采用不强迫。
- GATE-06[S] 静态分析阶梯不可把 G4 工具塞进每次 push。Miri 只跑有 `unsafe` 的 crate；Kani/形式化验证仅已采用才留；clippy pedantic 不当 `-D`。同层不双跑（LINT-07）。

- 阶梯：G1 pre-commit ≤6s（fmt+文件系统检查）→ G2 pre-push ≤3min（xtask 全量+clippy+单测）→ G3 CI 阻塞（+deny+MSRV+doc+`--locked`）→ G4 每夜非阻塞（Miri/loom/cargo-hack powerset/semver-checks/bench/可选 min-publish-age）。
- 候选门禁集：no_orphan_modules（第一优先）、no_raw_path_deps、no_wildcard_opt_level、tests_layout、crate/module_direction、internal_doctest_off、internal_publish_false、no_test_code_in_lib、no_silent_test_skip、lints_inherited、lint_ratchet。只有实现、失败 fixture 与实跑证据齐全的检查才可注册。

## D 决策树
- D-1 落点：先 `rg` 共享函数/类型/常量的全部调用方、平行入口、`#[cfg]` 分支与生成输入，再把变化放到拥有该不变量的现有模块；同类路径要么一起修，要么逐项说明不受影响。拆分走 WS-11 三级（函数 → `mod` → crate）；只有 WS-12 才新建 crate。不按行数阈值拆，也不另开拆分命令。
- D-2 错误：调用方要编程处理→稳定具名错误（手写或 thiserror，ERR-01/08）；应用编排→项目已有 anyhow/eyre，没有则不必为小 bin 新加；局部可证不可失败→expect("invariant:…")；不变量破坏→panic/debug_assert。
- D-3 共享状态：能消息传递/单一所有权→改；临界区短不跨 await→std Mutex；须跨 await→先重构再 tokio Mutex；度量证明锁瓶颈→细分/无锁+Ordering 论证+loom。
- D-4 新依赖：比较 std/现有方案的维护成本与成熟依赖的正确性、维护、传递代价和 license；理解 feature 后最小化启用，有实质存疑再请示。
- D-5 unsafe：有安全写法→用之；性能动机→安全版 bench 证明不足才引入：最小作用域+SAFETY+封装+Miri/loom。
- D-6 编译错误分诊：E0382/E0507→谁该拥有数据（共享不可变→&/Arc，确需副本才 clone 并说明，OWN-01）；E0597/E0515/E0716→作用域边界对吗（禁反射加 'static）；E0499/E0502→数据该拆吗（重构无果才内部可变性，OWN-05）；E0277 Send/Sync→该跨线程吗（先答再 Rc→Arc）；2024 `!` fallback / `never_type_fallback_flowing_into_unsafe`→显式写 `()` 或具体 Ok 类型，禁让 `!` 流进 unsafe；3 次不过→三振升级设计层。

