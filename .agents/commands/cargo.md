---
description: /cargo — Cargo/build 与 Rust 开发工具带
---


# /cargo

显式 pin：加载 rust skill，按 `reference/slim/cargo.md` 深读 `$ARGUMENTS` 指向的仓库范围，优化 workspace/target/features/profile/build.rs/缓存、Rust 配套工具与 CI 命令。

`/cargo tools [target]` 进入开发体验子模式：审查 rustup/rust-analyzer、watch/test/coverage/依赖治理工具、版本安装与任务入口；一个信号只保留一个 owner。

`/cargo hygiene [target]` 进入磁盘卫生子模式：按 `reference/slim/hygiene.md` 把 `target/`、`$CARGO_HOME`、未入库垃圾、入库孤儿分四层清理。裸调用只出体积表；`--apply` 只动 L3/L4；清 `target/` 或全局缓存必须用户再说「清磁盘 / 清全局缓存」。禁止用 `cargo clean` 当加速，禁止 `rm -rf ~/.cargo`。

裸调用只读体检；`--apply` 或同一请求明确“修/改/实现”才按 SKILL 写入边界落最小 Patch。它不是任意 `cargo ...` 或 `cargo install ...` 透传器，禁止隐式 clean/sweep 共享缓存，也不静默修改用户全局工具。Args `[tools|hygiene|target] [--apply]`。
