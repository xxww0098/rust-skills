# 普通实现覆盖层（非命令）

目的：用户说「实现 / 修 / 改 / 补测试」且未点名子命令时，用最小纪律写出正确 Rust。按 **edition 2024** 语义写（RPIT 默认捕获全部 in-scope 泛型、`if let` 短临时值、`#[unsafe(no_mangle)]`、`unsafe extern`、≥1.88 let chains）；不要为迁就 2021 而改写法。本文件不是菜单、不阻塞任务、不要求 RUST.md。设计未定升级 [shape.md](shape.md)；编译错误叠加 [triage.md](triage.md)；有框架证据再叠加对应 reference。

修 bug 先按 D-1 用 `rg` 枚举目标 helper/type 的全部调用方、sync/async 或快/慢等平行入口、`#[cfg]` 分支与生成输入；修拥有不变量的一层。同类路径未一起改时逐项写明为何不受影响。

## 先过四道门（每道有完成条件）

1. **所有权**（OWN / D-6）：每个新的共享或 clone 都能用一句话说清「谁拥有、谁借用、为何要副本」。完成：无「为过编译器而 clone」的裸修复。
2. **非法状态**（API-01/08）：边界 `parse`/`TryFrom` 一次；内部函数收领域类型，不收再校验的 `String`。完成：关键概念有 newtype 或 enum，或显式写明为何原始类型足够。
3. **错误**（D-2 / ERR）：可预期失败是 `Result`。库对外要 `match` 才上具名错误（手写或已有 thiserror）；应用层用项目已有的 anyhow/eyre。变体少、不发布 API → 不新加这两个 crate（ERR-08）。完成：生产路径无裸 `unwrap`，`expect` 写成不变量证明。
4. **验证**（TEST-01/08/09/10/13）：改了行为就优先补到最近的现有测试；期望值来自规格/手算，不复述实现。一次改动 1–3 个测试，填不出「会因哪条规格失败」就不要写。修 bug 要让该测试在旧行为上见红，再让当前源码见绿；无法安全见红就列缺口。并发/偶发红/补测膨胀走 [testing.md](testing.md)。运行项目已有包装入口时确认它使用当前源码产物，不调用 `PATH` 里的旧二进制。完成：相关测试已跑，或写明不能跑的原因。

## 默认写法（命中才改，不扫全仓）

- 参数 `&str` / `&[T]` / `&Path`，不要 `&String` / `&Vec<T>` / `&PathBuf`（OWN-02）。
- 互斥状态用 enum，不用 `bool` + `Option` 组合（API-01）。
- 「拿走再放回」用 `mem::take` / `mem::replace`（OWN-03）。
- newtype 用 `as_str` / `AsRef`，不为点语法 `impl Deref`（OWN-04）。
- 内部可变性是拆分失败后的工具，引入时写互斥假设（OWN-05）。
- 不该 async 就同步（SIMP-07）；不引入 `unsafe`，除非已走 D-5 且附 `// SAFETY:`。`unsafe fn` 体内每个 unsafe 操作仍要显式 `unsafe {}`（UNSAFE-03）。
- `bool` 用 `if`；互斥 enum 用 `match`；只要 `Some`/`Ok` 往下走用 `let-else`/`?`。2024 + ≥1.88 可用 let chains；≥1.95 可用 `if let` guard。不把穷尽 enum 改成 if 链（SIMP-08）。
- 拆分：先抽函数，再 `mod`；两不变量才拆文件。想独立成库走 `/rust-skills:rust crate`，不要为行数搬家（WS-11/12）。
- `artifact=cli` 或 `clap` 证据：叠加 [cli.md](cli.md)；解析只在 bin，库禁 `process::exit`。
- `tracing` / 生产路径 `println!`：叠加 [obs.md](obs.md)；axum 再叠加 [axum/observability.md](axum/observability.md)。
- 出站 HTTP / handler 里 `reqwest::Client::new()`：叠加 [axum.md](axum.md) AX-02/17（进程级 Client + 双超时）；非 axum 同样禁止每请求 new。
- 入站 JSON / `serde_json::Value` 当模型 / `from_str(...).unwrap()`：叠加 [serde.md](serde.md)。

```rust
// ✗ 为 E0382 反射 clone；参数过窄
fn first_word(s: &String) -> String {
    s.clone().split_whitespace().next().unwrap().to_string()
}

// ✓ 借用进、可选借出；非法/空输入可表示
fn first_word(s: &str) -> Option<&str> {
    s.split_whitespace().next()
}
```

## 升级，不发明流程

| 信号 | 加载 |
|---|---|
| 编译错误 / borrow checker | [triage.md](triage.md)（必须输出 HOW→WHY→WHAT 追溯链，禁止只给 clone） |
| 功能边界、状态机、错误矩阵不清 | [shape.md](shape.md) |
| 取消/停机/Stream | [async.md](async.md) |
| rayon/锁/runtime | [concurrency.md](concurrency.md) |
| 补测试 / 竞态 / flaky / 火焰山 / 测文件越写越多 | [testing.md](testing.md) |
| `sqlx` / `sea-orm` / axum / Tauri / clap / tracing 证据 | 对应框架/语言 reference；axum/Tauri 的 owner 再按「深入」表加载子 playbook（一次 1–2 个） |
| 用户要评审而不是改 | [review.md](review.md)，只读 |

## 权威源（有争议时以这些为准）

- 所有权/API：Rust API Guidelines `C-DEREF`、`C-NEWTYPE`、`C-CONV` / `C-CONV-TRAITS`
- 2024 版次：Edition Guide「RPIT lifetime capture」、「if let temporary scope」、「Unsafe attributes」、「Unsafe extern blocks」、「unsafe_op_in_unsafe_fn」、「never type fallback」；1.88 let chains；1.95 `if let` guards / `cfg_select!`
- 错误：thiserror 文档（库）、anyhow 文档（应用）；eyre 视为 anyhow 等价。二者都不是必依赖（ERR-08）
- 数据层：sqlx `Pool` 文档（默认非生产）、`query!` + `SQLX_OFFLINE`
- 构建：2025 Rust Compiler Performance Survey；Cargo `--timings` / `cargo report timings`；x86_64 Linux ≥1.90 默认 rust-lld
- 运行时：nnethercote《The Rust Performance Book》（clone / clone_from / 分配）
- 环境：`std::env::set_var` Safety（Unix 多线程几乎无法证明；子进程用 `Command::env`）

## 完成条件

目标内每处改动有所有权一句话或测试；共享改动的调用面已枚举；未越写范围；最小相关 `cargo test`/`cargo check` 已跑或声明缺口。不要先逼 `init`/`document`。按 [SKILL 输出契约](../SKILL.md) 收尾。
