# /rust-skills:rust audit <domain> [--record] — 领域深审

目的：单域穿透式只读审查，比 review 深一个量级。域：`unsafe` / `deps` / `tests` / `build` / `async` / `api` / `security`。无域参数 → 列出七域一句话说明，问一次。多域 = 依次执行。每域结束输出统一表格（位置|规则号|问题|修复）+ 置信度；默认只给可粘贴的债务条目，显式 `--record` 才写 RUST.md。

## audit unsafe（UNSAFE-01..11 · FFI-01..10）

1. `rg -n 'unsafe|extern |transmute|from_raw|as_ptr|MaybeUninit|static mut|no_mangle|export_name|link_section|set_var|remove_var' -g '*.rs' -g '!target/**' -g '!vendor/**'` 建立全量清单
2. 逐块过检查单：SAFETY 注释逐条对应前置条件（UNSAFE-02）；panic 安全次序（UNSAFE-06：可 panic 操作是否插在裸操作中间）；`assert!` 非 `debug_assert!`（UNSAFE-07）；手动 Send/Sync 论证（UNSAFE-08）；NonNull/cast/MaybeUninit（UNSAFE-09）；2024 链接属性是否写成 `#[unsafe(no_mangle|export_name|link_section|naked)]`（UNSAFE-10）；Unix 多线程是否 `env::set_var`/`remove_var`（UNSAFE-11）
3. FFI 逐条：panic 收口（FFI-01）、repr(C)（FFI-02）、CString 指针是否逃逸（FFI-03：查 C 契约是否保留指针）、free 义务归属表（FFI-04：每块跨界内存谁分配谁释放，列表格）、transmute 进 enum / `_unchecked`（FFI-05）、不透明句柄与契约文档（FFI-06）、错误码/out 参数而非 Result 过 ABI（FFI-07）、回调函数指针 + user_data 成对（FFI-08）、bindgen/cbindgen 生成绑定优先于手写 extern（FFI-09）、`unsafe extern` 块与 `safe fn`/`unsafe fn` 标注（FFI-10）
4. 验证：`cargo +nightly miri test -p <crate>` 能跑则跑并贴结果；缺失工具列入置信度缺口，不阻断只读结论。clippy 检查 undocumented_unsafe_blocks/missing_safety_doc/transmute_ptr_to_ptr。

```rust
// ✗ FFI-03 指针被保存，但 CString 在本语句结束时释放
let ptr = CString::new(name)?.as_ptr();
c_api_store(ptr);

// ✓ 仅用于契约明确“不保留指针”的同步调用
let c = CString::new(name)?;
c_api_borrow(c.as_ptr());
// 若 C 保存指针，须用句柄/所有权协议让 c 活到 C 端释放后。

// ✗ FFI-10 2024 裸 extern；UNSAFE-10 裸 no_mangle
extern "C" {
    fn strlen(p: *const c_char) -> usize;
}
#[no_mangle]
pub extern "C" fn plugin_init() {}

// ✓ 2024：块级 unsafe + 逐项 safe/unsafe；符号属性带 SAFETY
unsafe extern "C" {
    pub unsafe fn strlen(p: *const c_char) -> usize;
    pub safe fn sqrt(x: f64) -> f64;
}
// SAFETY: 本 cdylib 对该符号唯一
#[unsafe(no_mangle)]
pub extern "C" fn plugin_init() {}
```

## audit deps（DEP-01..13）

`cargo tree -d` 重复版本先判断是否造成类型不兼容、体积或安全影响，再给有收益的收敛路径；检查多成员共享版本是否应收口、有意局部差异是否有理由；核对 default feature 的实际内容、optional 配对与 feature 叠加性。仅在项目已配置时运行 `cargo deny check`；审 Cargo.lock 新传递依赖；现代化替代表扫一遍（lazy_static/once_cell/failure…→ 建议 `/rust-skills:rust modernize`）。供应链窗口（DEP-11..13）：CI/`Makefile` 是否无人值守 `cargo update` 或无 `--locked` 的构建；有 lock 的应用必须 `--locked`。`deny`/`audit`/`vet` 未配置标 MAY，不假装已扫零日。冷却期是解析策略不是审计替代；未启用不判红，只给应用侧候选（GATE-04）。

## audit tests（TEST-01..16）

孤儿模块全量核对（mod 图 vs 文件清单——最高优先级）；tests/ 布局（多二进制→合并 it 建议）；静默跳过模式扫描（`env::var.*is_err.*return` 族）；tautological 断言抽查；`thread::sleep` / 无 join spawn 赌时序（TEST-14/15）；配比画像（单测/集成/e2e 计数，一次改动是否堆了 >3 条套套测试，TEST-10/13）→ 债务清单。确认 flaky 是否未隔离就靠 CI retry（TEST-12/14）。项目已用 insta 则抽查快照是否人审过（禁把实现输出当期望，TEST-08/11）；mockall 只打在 I/O 端口，不 mock 纯函数；已采用 nextest/`cargo llvm-cov`/`cargo fuzz` 则沿用并报告覆盖缺口，未采用不强迫引入（TEST-12）。并发原语缺 loom/模型、并行测试只 spawn 不比加速比 → 指向 [testing.md](testing.md)。

## audit build（BUILD-01..10）

`cargo build --timings` 跑一次读图：串行长尾 crate、rmeta 等待空洞；profile 合规（禁通配 opt；package override 与 build-override 独立度量；CI profile）；拆 crate 候选（结合 WS-12 出度 0 模块）；链接器现状确认（≥1.90 Linux 默认 lld，不建议旧偏方）。给「预期收益排序」的改动清单，每项标注需要的验证数据。

## audit async（ASYNC-01..08；深层设计问题——取消安全/结构化停机/AFIT——转 [async.md](async.md)）

guard 跨 await 全扫（clippy await_holding_lock + 人工确认 parking_lot）；async 里阻塞调用（std::fs/thread::sleep/阻塞客户端）；spawn 无归宿（丢弃的 JoinHandle）；无界 channel 清单及论证注释有无；select! 分支取消安全抽查；手写 atomics 的 Ordering 论证与 loom 覆盖。

## audit security（安全面，axum + tauri 双栖）

完成条件：威胁模型一句话（谁能打到哪条边界）+ 分级发现表 + 可信代理/TLS 终止假设（未知则标缺口）+ 扫描处置说明；不得把未证实的配置缺失直接写成已利用漏洞。

范围：显式 target 优先；否则主产物 crate。**secrets 文件名级扫描可覆盖全仓**，但命中须分栏「主目标｜邻接证据｜仓外扫描」；邻接与仓外命中默认不可写修复清单。旁路 crate 排除并回显。

检查要点：
- secrets：优先脱敏扫描器（如 gitleaks `--redact`）；最低限度只列文件名 `rg -l 'sk-|BEGIN.*KEY|password\s*=' -g '!target/**' -g '!vendor/**'`，禁止把疑似密钥值打印进会话。再查 env 读取是否收口、日志脱敏（OBS-02）。
- 输入面：安全边界反序列化 `deny_unknown_fields`（SE-05，透传例外见 serde playbook）、长度/范围进类型（API-01/SE-07）。
- 认证授权：新密码哈希优先 argon2id；**存量 bcrypt 可保留**，要求登录后渐进重哈希或兼容论证，勿机械判红。token 过期与轮换；authz 统一前置层或**可证明等价**的类型化 extractor，不散落 ad-hoc 检查。axum 证据时叠加 [axum/auth.md](axum/auth.md)（JWT/session/RBAC 的具体缺陷表）。
- 浏览器/边缘：CORS 精确白名单（携凭据禁 Any）、安全响应头、TLS 终止与**可信代理**是否剥离伪造转发头——须结合部署拓扑；拓扑未知只标假设缺口。
- tauri 面：capabilities/ACL 最小化（TA-12）、CSP、shell/fs 白名单；深审清单与 capability 样板见 [tauri/security.md](tauri/security.md)。
- 依赖面：已配置则跑 cargo-deny advisories（DEP-06）；未配置标 MAY 候选，不假装已扫。有 lock 的应用 CI 无 `--locked` 或有 `cargo update` → DEP-11。冷却期未开不判红（DEP-13）。

规则号列：能映射到 OBS/SE/DEP/API/TA 则写该号；否则写 `security/<子面>`（secrets|authn|authz|exposure|supply-chain）。输出同各域表格 + 置信度。

## audit api（API-01..08，lib 模式重点）

pub 面清单：无文档 pub 项计数（missing_docs）；连环 bool/魔法字符串参数；该 non_exhaustive 未标的公共 enum；错误类型对外暴露 anyhow/String（ERR-01）；wire/row/领域/响应是否混在同一 `Serialize` 结构（API-08）；命名对照 API Guidelines 抽查；`cargo semver-checks` 能跑则跑。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。
