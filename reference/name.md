# /rust-skills:rust name [target] [--apply] — 函数与方法命名

目的：按 [Rust API Guidelines · Naming](https://rust-lang.github.io/api-guidelines/naming.html) 体检或改名。权威是 C-CASE / C-CONV / C-GETTER / C-ITER / C-CTOR / C-WORD-ORDER，不是 Java `getX` 或 C 的 `type_do`。X 上 [Raphael Luba](https://x.com/LubaRaphael/status/2048444288866934979)：转换写成 `Thing::from_stuff`，不要 `stuff_to_thing`。裸调用只体检；`--apply` 或明确「修/改/实现」才改标识符并更新调用点。不改行为、不 distill 结构。

编排：多文件时按 [kernel/swarm.md](../kernel/swarm.md) — 转换前缀 · getter · 谓词/构造器。单文件或已有快照则跳过。

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

**NM-03 C-GETTER** 字段读取用字段名，不要 `get_`。可变用 `foo_mut`。例外：容器按键取值 `get`/`get_mut`/`get_unchecked`；`Cell::get`。`TempDir::path` 是 getter，`into_path` 才是交出所有权——不要写成 `as_path`/`get_path`。

**NM-04 C-CTOR** 一般构造 `new` / `with_*`。转换构造是 **`from_*`（目标类型上）**，不是源类型上的 `to_*` 自由函数。对齐 Luba：`User::from_row(row)` 优于 `row_to_user(row)`，所有「怎么得到 User」都在 `User` 下能搜到。已有 `From`/`TryFrom` 就不要再加同义自由函数。

**NM-05 C-ITER** 齐次集合：`iter` / `iter_mut` / `into_iter`。迭代器类型名跟方法走（`Iter`/`IterMut`/`IntoIter`）。`str::chars` 这种语义不是「元素迭代」的保持现状，不机械改名。

**NM-06 谓词** `bool` 返回用 `is_` / `has_` / `can_` / `contains`，不要 `check_` / `get_is_`。

**NM-07 C-WORD-ORDER** 错误类型 `VerbObjectError`（`ParseIntError`），不要 `IntParseError`。与本 crate 和 std 已有词序一致。

**NM-08 方法优于 type_verb** 已有 `self` 就不要 `user_save` / `array_clear`。Luba 线程里的 C/Jai `type_do` 在 Rust 里是方法 `save` / `clear`。自由函数只留给没有合理 `self` 的情况，并仍用 `snake_case`。

**NM-09 禁止从 Java/Go/TS 原样搬** `getName`、`setEnabled`、`parseUser` camelCase、`IUserService`。setter 能改字段就用字段或 `set_enabled`；trait 不要 `I` 前缀。

**NM-10 一次改名要改全调用面** 按 D-1 枚举调用方、`#[cfg]`、测试、宏、生成入口。只改定义 = 失败。公开 API 改名先问，或留 `#[deprecated] pub use old_name as …` 过渡。

## 不要

- 为「好看」改行为或拆函数（那是 `distill`）。
- 把 `as_str` 用在要做 UTF-8 检查的 `Path::to_str` 上。
- Copy 类型的 `into_radians`（std 用 `to_radians`）。
- 全仓无差别 `get_` 大扫除：只报冻结范围内、且有 Rust 惯用替代名的。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织。

只读调用：表「位置｜NM｜现名｜应名｜理由（C-* / 所有权）」+ 调用点数。`--apply` 或明确“修/改/实现”时按 NM-10 改定义和调用点，跑最小 `cargo test`/`cargo check`。公开符号未授权不改。
