---
description: /test — 最小充分、无重复的 Rust 测试
---


# /test

显式 pin：加载 rust skill，按 `reference/slim/test.md` 深读 `$ARGUMENTS` 指向的改动面、测试目标、不变量与 CI 运行图，只编译并运行足以证明本次行为的测试。

裸调用只读体检；`--apply` 或同一请求明确“修/改/实现”才按 SKILL 写入边界合并/增强测试与去重 CI。禁止靠重复全量 test、retry 或 sleep 换绿。Args `[target] [--apply]`。
