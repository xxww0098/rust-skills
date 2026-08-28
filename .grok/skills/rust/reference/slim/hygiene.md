# /cargo hygiene [target] — 过期开发文件分层清理

目的：Rust 仓库变胖几乎从来不是「再删一遍代码」，而是四类东西混在一起：`target/` 坟场、`$CARGO_HOME` 缓存、未入库的剖析/备份垃圾、以及已经提交但没人引用的源文件。权威是 Cargo 自己的 [`cargo clean`](https://doc.rust-lang.org/cargo/commands/cargo-clean.html) 与稳定配置 [`cache.auto-clean-frequency`](https://doc.rust-lang.org/cargo/reference/config.html)（只扫全局缓存，不扫 `target/`）。X 上反复出现的实证：一份 `target/` 就能到数 GB 乃至十几 GB（[judeVector 用 cargo-sweep 清掉 17GB](https://x.com/judeVector/status/2025947553628398024)；把 `target` 比成 `node_modules` 是常见抱怨，不是许可证）。本文件是 `slim` 的磁盘卫生子模式，**不是新命令**。构建慢仍走 [cargo.md](cargo.md)；活文件里的死代码走 [distill](../distill.md)；死依赖走 machete/udeps 复核。

编排：多文件时按 [kernel/swarm.md](../../kernel/swarm.md) — 本文件是 slim 第四条车道。禁止清共享 target；禁止把 distill 的死码当文件删。 单文件或已有快照则跳过。

先消费本轮唯一 ProjectSnapshot。孤儿名单以 `graphs.orphans` 为准（TEST-04），不要手扫第二遍 crate 图。

## 授权（比普通 `--apply` 更严）

| 层 | 是什么 | 裸调用 / 普通 `--apply` | 才能动手 |
|---|---|---|---|
| L1 | 项目 `target/`、独立 `CARGO_TARGET_DIR` | 只读体积表 + 可粘贴命令 | 用户说「清磁盘 / 清 target / cargo clean / sweep」 |
| L2 | `$CARGO_HOME` registry/git | 只读；提示 Cargo 自动 GC | 用户说「清全局缓存」 |
| L3 | 未跟踪的 `.bak` / `perf.data` / flamegraph | `--apply` 或「删」可删未跟踪项、补 `.gitignore` | 不碰 `target/` |
| L4 | 已跟踪的孤儿 `.rs`、误提交的剖析产物 | `--apply` 按清单删文件，不 `git commit` | 每条都有可达图或 git 证据 |

SKILL 的「不清理共享构建缓存」仍然有效：`--apply` **不够**授权 L1/L2。RA 单独 target dir（BUILD-09）未点名不准动。

## HY 检查单（体检输出：层｜路径｜体积/证据｜动作｜编号）

**HY-01 必须分层** 四层分开报，禁止 `rm -rf target ~/.cargo src/scratch.rs` 一把删。L1 可再生；L2 可再下载（离线除外）；L3/L4 可能含劳动成果，删前要证据。

**HY-02 先量后扫** 没有体积表不准删。最小盘点（命令换成仓库真实路径）：

```bash
du -sh target "${CARGO_TARGET_DIR:-}" "$CARGO_HOME" ~/.rustup 2>/dev/null
cargo clean --dry-run
git ls-files -- 'perf.data*' '*flamegraph*.svg' '*.folded' 'tarpaulin-report.html' 'lcov.info' '*.rs.bak' '*.orig'
```

快照 `graphs.orphans` 是 L4 的机械名单。`cargo clean --dry-run` 不存在时改报「将删除整个 target/」，不要假装预览过。

**HY-03 `cargo clean` 不是加速** 禁止用 clean / sweep 当「下次更快」或冷构建基线（BUILD-07）。清完下一发是冷构建。编译慢走 timings，不走扫帚。场景 5/52 仍然成立。

**HY-04 收窄 `cargo clean`** 整仓默认 `cargo clean` 是最后一档。先试：

```bash
cargo clean --dry-run --release          # 只扔掉 release 产物
cargo clean --dry-run --doc              # 只扔掉 rustdoc
cargo clean --dry-run -p <pkg>           # 只扔掉一个包的产物
cargo clean --dry-run --profile profiling
```

用户共享的 `CARGO_TARGET_DIR`、sccache、RA 的独立 target 都要在表里点名；没点名就当共享缓存，不动。

**HY-05 sweep 是 MAY** [cargo-sweep](https://crates.io/crates/cargo-sweep) 适合「多 toolchain / 多日增量坟场、还想留热缓存」。先 dry-run（`--time <days>` / 递归），再动手。CI 里 stamp 文件是它的正当用途。项目没装就给可粘贴命令，**禁止为清磁盘 `cargo install`**。不要把它写成默认门禁。

**HY-06 `CARGO_HOME` 走 Cargo GC** Cargo ≥1.88 在 `cargo build`/`fetch` 时按 [`cache.auto-clean-frequency`](https://doc.rust-lang.org/cargo/reference/config.html)（默认 `"1 day"`）回收**全局** registry/git 缓存；`--offline`/`--frozen` 时自动 GC 关闭。这 **不清理 `target/`**。禁止 `rm -rf ~/.cargo` 或清空 `git/checkouts`。`cargo-cache` 是第三方 MAY，与自动 GC 二选一，不要叠着清。用户要更狠时给 `CARGO_CACHE_AUTO_CLEAN_FREQUENCY=always` 的说明，不改用户全局 config。

**HY-07 rustup 旧 toolchain** `rustup toolchain list` 对照 `rust-toolchain.toml`、CI matrix、Miri/udeps 每夜车道。只把确认不用的 channel 列成可粘贴 `rustup toolchain uninstall`。不准卸载当前项目钉住的 toolchain，不准顺手卸 nightly「以防万一」。

**HY-08 孤儿源文件看可达图** 只有 `inspect_project` 标了孤儿、且 `mod`/`include!`/`#[path]`/`build.rs` 生成入口都搜过，才是死文件（TEST-04）。`src/bin/*.rs`、`tests/*.rs` 集成目标、`examples/`、`benches/` 以 manifest `[[bin]]`/`[[test]]`/`[[example]]`/`auto*` 为准，不要把合法入口当孤儿。活文件里的死函数走 distill，不在本命令删行。

**HY-09 agent 残骸与剖析产物不入库** 典型垃圾：`*.rs.bak` / `*.orig` / `scratch.rs` / 未 `mod` 的实验文件、agent 新写却没进测试图的 `tests/*_more.rs`、`perf.data`、`flamegraph.svg`、samply json、criterion 报告、`tarpaulin-report.html`、`lcov.info`、`rustc-ice-*.txt`。已跟踪 → L4 删除表；未跟踪 → L3；`.gitignore` 缺 `/target` 或缺这些名字就补**具体规则**，禁止 `*.svg` 通配。sqlx 离线数据、bindgen 生成入口交给对应框架 owner，本命令只点名。

**HY-10 永不删** `Cargo.lock`、`rust-toolchain.toml`、图内源码、用户没点名的 `$CARGO_HOME`、CI 仍用的 toolchain、git 历史、密钥/`.env`。不 sudo。不隐式 stash/commit。不覆盖 hook。

## 不要

- 为了「瘦身」把还在用的 example/bench/integration target 删掉。
- 把 `workspace.default-members` 当扫把（那是 cargo.md）。
- 清完宣称构建更快（HY-03）。
- 在 RA 正在用的 target dir 上 `cargo clean`。
- 用 distill 的 judo 代替本文件的文件删除，或反过来。

## 输出与完成条件

按 [kernel/finding.md](../../kernel/finding.md) 组织。

只读调用：四层表（层｜路径｜体积或 git 证据｜建议动作｜HY）+ 可粘贴 dry-run。L1/L2 即使带 `--apply` 也只给命令，除非用户说了「清磁盘/清全局缓存」。

明确「修/改/实现/删」或 `--apply` 时：只落 L3/L4 冻结清单（删未跟踪垃圾、删已跟踪孤儿/误提交产物、补 `.gitignore`）；L1/L2 仍要更强授权。每条删除填 Patch。跑最小 `cargo check`/`cargo test` 证明没把入口当孤儿删掉。不 commit。
