# kernel/write — 只决定能改什么、改成什么样

授权之后才读本文件。目标：落盘的 Rust **一开始就是规范形状**，不是先写绿再等 review 纠偏。

每处写入填一张 Patch（[schemas/patch.schema.json](../../../schemas/patch.schema.json)）。写不出 Patch 就不要改文件。

## Patch

| 字段 | 必须回答 |
|---|---|
| `intent` | 用户目标的一句话 |
| `finding_id` | 对应 Finding，或 `greenfield` |
| `owner_layer` | 拥有该不变量的那一层（不是「顺便也改」的层） |
| `files` | 冻结清单内的路径，禁止扩围 |
| `invariant` | 本补丁保护什么（所有权 / 非法状态 / 错误 / 边界） |
| `shape` | 采用下方哪条规范形状 |
| `refused` | 明确拒绝的捷径（至少一条，或「未见捷径」） |
| `verification` | 将跑的最小 `cargo test`/`cargo check`；跑不了就写原因 |

落盘后输出 Patch 表。没有这张表 = 这次写入不合格。

## 拒绝落盘（即使能编译）

- 为过编译器而 `.clone()` / `clone()` 满天飞（OWN-01）。先改所有权或 API。
- 生产路径裸 `unwrap()`；`expect` 不是不变量证明（ERR-03）。
- 服务端 `println!`/`dbg!` 当日志（OBS-01）。
- 信任边界 `xs[i]`、入站 `/`（ERR-09）。
- `for i in 0..len` 复述 iterator；闭集却 `Vec<Box<dyn Trait>>`（SIMP-13）。
- 新 crate / 新测文件 / 扩大 `pub` / 升 MSRV：Patch 未声明并获得同意。
- 填不出「这条测试会因哪条规格失败」的测试（TEST-13）。
- `Span::enter()` 跨 `.await`；`fmt().init()` 当生产 subscriber（TR-05/19）。
- 新函数 `get_foo` 读字段、转换却叫错 `as_`/`to_`/`into_`（API-07 / NM-02/03）。
- 新建 crate 名叫 `utils`/`common`/`helpers`/`*-rs`/`rust-*`（NM-11/12）。
- 用 `cargo clean`/`sweep` 当加速，或未获「清磁盘」授权就删共享 `target/` / `$CARGO_HOME`（BUILD-07/11、HY-03/10）。
- `ActiveModel` 把 PK / `DEFAULT` 列写成 `Set(0)` / `Set(now)`，或 `Set(None)` 当默认值（SO-17）；有 `#[sea_orm::model]` 却手循环 insert 子行（SO-18）。
- `on_conflict` 0 行当成功、用 `save()` 当 upsert（SO-23/24）；handler 把 Entity JSON/`rename_all` 直接 `from_json`（SO-25）；生产启动 `schema-sync`（SO-12）。
- 列表页 `Entity::load().with(..)` 整棵 `ModelEx`（SO-22/26）；把 `HasOne::Unloaded` 当 `None`（SO-27）；JOIN 1-N 再 paginate（SO-07/13）；`load().all()` 后 `clone` `ModelEx` 树（SO-28）；`load().with().filter(子列)` 当切子行（SO-29）。

## 规范形状（直接按这个写）

**所有权**：`&str` / `&[T]` / `&Path` 进去；需要所有权才 `to_owned`。互斥用 enum，不用 `bool+Option`。

```rust
fn first_word(s: &str) -> Option<&str> {
    s.split_whitespace().next()
}
```

**错误**：边界 `Result`；库具名错误、应用沿用项目已有 anyhow/eyre。不要为三个变体新加 thiserror。

```rust
pub fn parse_port(s: &str) -> Result<u16, ParsePortError> {
    s.parse().map_err(|_| ParsePortError::Invalid)
}
```

**应用错误（service）**：一个 enum，在边界转 HTTP/退出码；handler 不 `unwrap`。

```rust
enum AppError { NotFound, Internal(anyhow::Error) }
```

**观测**：binary `main` 一次 `Registry` + `EnvFilter::try_from_default_env` 回退 `info`。库只 emit。禁止 `fmt().init()` 当生产配置。

**测试**：改行为 → 最近的现有 `#[test]` 加 1 条，期望值来自规格。禁止新开 `tests/foo_more.rs` 复述实现。

**异步**：不该 async 就同步。`tokio::spawn` 必须 `.instrument(span)`；锁不跨 `.await`。

## 写完

1. 按 [kernel/verification.md](verification.md) 跑 `check_patch.py` + Patch 里的 cargo 命令。
2. 范围行来自 snapshot，文件数对得上 `files`。
3. 下一步最多一条：`/rust-skills:rust review <刚改的路径>`。
