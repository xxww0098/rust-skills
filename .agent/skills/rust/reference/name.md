# /rust-skills:rust name [target] [--apply] — 函数、方法与 crate 命名

目的：按 [Rust API Guidelines · Naming](https://rust-lang.github.io/api-guidelines/naming.html) 体检或改名。权威是 C-CASE / C-CONV / C-GETTER / C-ITER / C-CTOR / C-WORD-ORDER / C-FEATURE，外加 Cargo 的 `-sys` 约定。不是 Java `getX`、C 的 `type_do`、也不是 `my-app-rs`。X 上 [Raphael Luba](https://x.com/LubaRaphael/status/2048444288866934979)：转换写成 `Thing::from_stuff`，不要 `stuff_to_thing`。C-CASE 原文：crate 名不要 `-rs`/`-rust` 前缀或后缀——每个 crate 都是 Rust。裸调用只体检；`--apply` 或明确「修/改/实现」只改函数/方法；crate/包名必须再听到「改 crate 名 / 改包名」。不改行为、不 distill 结构、不代替 `/crate` 决定拆不拆。

编排：多文件时按 [kernel/swarm.md](../kernel/swarm.md) — 转换前缀 · getter · 包名/`-rs`/workspace 成员。单文件或已有快照则跳过。

## NM 检查单（体检输出：位置｜编号｜问题｜修复）

**NM-01 C-CASE** 函数/方法/局部 `snake_case`；类型/trait/变体 `UpperCamelCase`；常量和静态 `SCREAMING_SNAKE_CASE`。缩写在 camel 里算一个词（`Uuid` 不是 `UUID`）；snake 里全小写（`is_xid_start`）。`clippy::non_snake_case` 已覆盖的不重复报，除非是 `getUser` / `parseJSON` 这种从别的语言搬来的。

**NM-02 C-CONV** 转换方法前缀必须同时说清成本和所有权：

| 前缀 | 成本 | 所有权 |
|---|---|---|
| `as_` | 免费 | 借 → 借（视图） |
| `to_` | 贵 | 借→借（要检查）、借→拥有、Copy 值→值 |
| `into_` | 不定 | 拥有→拥有（吃掉 self） |

```rust
// ✗ NM-02 分配却叫 as_；不消费却叫 into_
fn as_owned(s: &str) -> String { s.to_owned() }
fn into_str(s: &String) -> &str { s }

// ✓
fn as_str(s: &String) -> &str { s }
fn to_owned_string(s: &str) -> String { s.to_owned() }
fn into_bytes(s: String) -> Vec<u8> { s.into_bytes() }
```

`as_`/`into_` 降低抽象（视图或拆开）；`to_` 同层变换。包装类型给 `into_inner()`。名字里的 `mut` 必须对上返回值：`as_mut_slice` 不是 `as_slice_mut`。

**NM-03 C-GETTER** 字段读取用字段名，不要 `get_`。Rust 允许字段和方法同名，这就是不写 `get_` 的原因。可变用 `foo_mut`。例外：容器按键取值 `get`/`get_mut`/`get_unchecked`；`Cell::get`。`TempDir::path` 是 getter，`into_path` 才是交出所有权——不要写成 `as_path`/`get_path`。

**NM-04 C-CTOR** 一般构造 `new` / `with_*`（`new` 不可失败）。失败用 `try_new` / `TryFrom`，不要 `new() -> Result`。转换构造是 **`from_*`（目标类型上）**，不是源类型上的 `to_*` 自由函数。对齐 Luba：`User::from_row(row)` 优于 `row_to_user(row)`，所有「怎么得到 User」都在 `User` 下能搜到。已有 `From`/`TryFrom` 就不要再加同义自由函数。

**NM-05 C-ITER** 齐次集合：`iter` / `iter_mut` / `into_iter`。迭代器类型名跟方法走（`Iter`/`IterMut`/`IntoIter`）。`str::chars` 这种语义不是「元素迭代」的保持现状，不机械改名。

**NM-06 谓词** `bool` 返回用 `is_` / `has_` / `can_` / `contains`，不要 `check_` / `get_is_`。

**NM-07 C-WORD-ORDER** 错误类型 `VerbObjectError`（`ParseIntError`），不要 `IntParseError`。与本 crate 和 std 已有词序一致。

**NM-08 方法优于 type_verb** 已有 `self` 就不要 `user_save` / `array_clear`。Luba 线程里的 C/Jai `type_do` 在 Rust 里是方法 `save` / `clear`。自由函数只留给没有合理 `self` 的情况，并仍用 `snake_case`。

**NM-09 禁止从 Java/Go/TS 原样搬** `getName`、`setEnabled`、`parseUser` camelCase、`IUserService`。setter 能改字段就用字段或 `set_enabled`；trait 不要 `I` 前缀。

**NM-10 一次改名要改全调用面** 按 D-1 枚举调用方、`#[cfg]`、测试、宏、生成入口。只改定义 = 失败。公开 API 改名先问，或留 `#[deprecated] pub use old_name as …` 过渡。crate 改名的调用面是 Cargo.toml + path 依赖 + `use` ident + CI matrix，见 NM-11。

**NM-11 C-CRATE 包名** `[package].name` 用小写 ASCII `[a-z0-9-_]`，清单里 **kebab-case**（`serde-json`），代码里自动变成 `serde_json`。crates.io 把 `-` 和 `_` 看成同一个名字，同一仓库不要混用。不要 `-rs` / `-rust` 前缀或后缀（C-CASE：「Every crate is Rust」）。不要 Rust 关键字、Windows 保留名（`nul`/`con`/`aux`）、空名、非 ASCII。crates.io ≤64 字符。`[lib] name` 覆盖只有在必须跟包名分叉时才用，默认等于包名转下划线。

```toml
# ✗ NM-11
name = "my-app-rs"
name = "rust-utils"
name = "MyCrate"

# ✓
name = "acme"
name = "acme-cli"
```

**NM-12 项目里的成员 crate** 按**职责/领域**起名，不要技术层或占位词。多成员时用产品前缀，目录跟包名走（`crates/acme-cli`）。值不值得拆仍走 `/crate`（WS-12）；这里只管起名。

| 角色 | 包名 | rustc ident |
|---|---|---|
| 产品库 | `acme` | `acme` |
| 二进制 | `acme-cli` | `acme_cli` |
| proc-macro | `acme-macros` / `acme-derive` | `acme_macros` |
| 链接 native `libfoo` | `foo-sys`（[Cargo `-sys`](https://doc.rust-lang.org/cargo/reference/build-scripts.html#-sys-packages)） | `foo_sys` |
| 测试辅助 | `acme-test-support`（TEST-03） | `acme_test_support` |

禁止：`utils` / `common` / `helpers` / `shared` / `lib` / `core`（产品不叫 core 时）/ `app` / `backend` / `my-crate` / `rust-app`。单 crate 仓直接用产品名，不要再套一层 `*-core`。`-sys` 只给 FFI 声明+链接，不塞安全抽象（那是旁边的 `foo`）。内部不发布仍要正经名字，并 `publish = false`（WS-03）。

**NM-13 三层名字对齐** 包名（kebab）≠ 目录可不同但应相同 ≠ rustc ident（下划线）≠ 模块（`snake_case` 文件）。`mod FooBar` / `FooBar.rs` 是 NM-01。`use my_app_rs::…` 暴露了 NM-11。不要为了短 `use` 偷偷改 `[lib] name` 让它和包名脱节。

**NM-14 C-FEATURE** feature 名就是能力本身：`std` / `serde`，不要 `use-std` / `with-serde` / `no-foo`。Cargo feature 必须可叠加，负名几乎永远错。可选依赖的隐式 feature 跟包名同款 kebab。

## 不要

- 为「好看」改行为或拆函数（那是 `distill`）；为「好看」拆 crate（那是 `/crate`）。
- 把 `as_str` 用在要做 UTF-8 检查的 `Path::to_str` 上。
- Copy 类型的 `into_radians`（std 用 `to_radians`）。
- 全仓无差别 `get_` 大扫除：只报冻结范围内、且有 Rust 惯用替代名的。
- 已上 crates.io 的包名不因规范改（名字不可回收）。稳定内部 crate 无用户「改 crate 名」授权不改。
- 把 workspace 成员改成互撞的 `foo-bar` 与 `foo_bar`。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织。

只读调用：表「位置｜NM｜现名｜应名｜理由（C-* / 所有权 / 包角色）」+ 调用点数。`--apply` 或明确“修/改/实现”时按 NM-10 改**函数/方法**定义和调用点，跑最小 `cargo test`/`cargo check`。crate/包名另需明确“改 crate 名”才动 Cargo.toml / path / `use` / CI；公开符号与已发布包名未授权不改。
