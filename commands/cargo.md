---
description: /cargo — Cargo/build 最短反馈回路
---


# /cargo

显式 pin：加载 rust skill，按 `reference/slim/cargo.md` 深读 `$ARGUMENTS` 指向的仓库范围，优化 workspace/target/features/profile/build.rs/缓存与 CI 命令。

裸调用只读体检；`--apply` 或同一请求明确“修/改/实现”才按 SKILL 写入边界落最小 Patch。它不是任意 `cargo ...` 透传器，禁止隐式 clean/sweep 共享缓存。Args `[target] [--apply]`。
