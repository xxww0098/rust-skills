# /rust-skills:rust modernize [target] — 现代化替代

目的：把过时习惯迁到现代等价物。无 target 时优先**当前改动文件集**（`git` 暂存/未暂存/未跟踪中的相关路径及其 diff）；不要把未改文件的全文误算进「改动内命中」。改动内无命中时**先询问**再扩全仓（用户已明确全仓/仓库测试除外）。先列清单；`--apply` 或用户明确「修/改/实现」才逐项执行。

编排：多文件时按 [kernel/swarm.md](../kernel/swarm.md) — edition/MSRV · 过时 API 清单。 单文件或已有快照则跳过。

## 替代表（扫描目标 → 替代）

| 扫描 | 替代 | 依据 |
|---|---|---|
| `lazy_static!` | `std::sync::OnceLock` | 1.70+ |
| `once_cell::sync::Lazy` | `std::sync::LazyLock` | 1.80+ |
| 直接依赖 `once_cell`/`lazy_static` 但源码零用法 | **删依赖**（单列，不假装要改调用点） | 死依赖清理 |
| `try!(` | `?` | 2018 |
| `failure` / `error-chain` 依赖 | thiserror / anyhow | ERR-01/02 |
| `mem::uninitialized` / 引用类型 `mem::zeroed` | `MaybeUninit` | UNSAFE-09 |
| 创建 `static mut` 的共享/可变引用 | AtomicT / Mutex / OnceLock，或严格限定的裸指针 | Rust 2024 默认拒绝 `static_mut_refs`；声明本身不是硬错误 |
| `edition = "2018"` / `"2021"` | `edition = "2024"` + `cargo fix --edition` | 本技能只支持 2024 基线（WS-05） |
| 裸 `#[no_mangle]` / `#[export_name]` / `#[link_section]` / `#[naked]` | `#[unsafe(...)]` + SAFETY | 2024 unsafe attributes（UNSAFE-10） |
| 裸 `extern "C" { … }` | `unsafe extern "C" { pub safe fn …; pub unsafe fn … }` | 2024 unsafe extern（FFI-10）；`safe fn` 仅当任意合法参数都健全 |
| Unix 多线程里 `env::set_var` / `remove_var` | `Command::env` 传给子进程；测试用独立进程 | std docs：多线程 Unix 几乎无法证明健全（UNSAFE-11） |
| `unsafe fn` 体内裸 `ptr::read` / `get_unchecked` 等 | 体内再包 `unsafe { … }` + SAFETY | 2024 `unsafe_op_in_unsafe_fn`（UNSAFE-03） |
| 2024 `!` fallback 让 `f()?` / `panic!` 闭包推不出类型 | 显式 `()` 或具体 Ok 类型 | Edition Guide never-type fallback |
| 手写 `extern` 声明 | bindgen / cbindgen | FFI-09 |
| `#[allow(x)]` 无理由 | `#[allow(x, reason = "...")]` | LINT-05 |
| 已兑现的 `#[allow(x)]` | `#[expect(x, reason = "...")]` | 1.81+；未兑现会 warn |
| `io::Error::new(ErrorKind::Other, …)` | `io::Error::other(…)` | 1.74+ |
| `once_cell::unsync::Lazy` | `std::cell::LazyCell` | 1.80+ |
| edition 2024 RPIT 多余生命周期 | 精确捕获 `use<…>` 覆盖隐式「捕获全部 in-scope」或改为拥有数据 | Edition Guide RPIT capture；先答「该不该拥有」 |
| `match` 臂里再套 `if let` | `if let` guard（`Some(x) if let Ok(y) = f(x)`） | 1.95 |
| 一长串 `#[cfg]` / `else if cfg!` | `cfg_select!` | 1.95；rustfmt 可格式化 |
| `v.push(x); v.last_mut()` | `Vec::push_mut` / `insert_mut` | 1.95 |
| `core::ops::Range` 当 `Copy` | `core::range::{Range, RangeInclusive}` | 1.96；语法改 2027 edition，现在不要手改 `..` |
| `assert!(matches!(x, P))` | `assert_matches!(x, P)` / `debug_assert_matches!` | 1.96 |
| 整数 `!= 0` 当 `bool`（FFI/SQLite） | `bool::try_from(n)` | 1.95 |

补充：
- 已是目标形态（`std::sync::LazyLock` / `OnceLock` 等）计为**非命中**；禁止因字面含 `Lazy` 误报。
- `cargo clippy --fix` 可安全吃掉的机械项先跑（确认 diff 后提交）。edition 2018/2021 → 2024 是本命令正式命中（上表），授权后与 `cargo fix --edition` 一起做，不再当「另案」。
- 未列入 workspace members 的旁路 crate 默认不扫，即使出现在 git 改动集；除非用户点名。输出须回显「已排除的旁路路径」。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

1. 报告项目根与扫描范围（改动集 / 用户 target / 全仓）及已排除旁路。
2. 改动内无命中时停在询问点；若展示全仓 peek，必须标「未授权预览」，与正式修改清单分开。仅存在于**未改** `Cargo.toml` 的死依赖属全仓范围，确认前不得进入正式清单。
3. 正式命中清单（文件:行 → 替代；死依赖单列「删依赖」）→ 凭 `--apply` 或用户授权分组修改（不自动提交）。
4. `cargo check` + 项目已有测试入口；项目采用 nextest 才使用它，否则 `cargo test`。移除的直接依赖同步清理 Cargo.toml；传递依赖残留用 `cargo tree -i` 说明，不假装 lock 已消失。
