---
description: /rust-skills:rust review 的稳定插件别名
---

# /review

这是一个 **pin**：把高频子命令提升为独立快捷命令的模式示例。

执行：加载 rust 技能，按其 `reference/review.md` playbook 对 `$ARGUMENTS` 执行规范评审。缺省范围包含已跟踪改动和未跟踪文件；等价于 `/rust-skills:rust review $ARGUMENTS`。默认只读，只有显式 `--record` 才写 RUST.md。

要 pin 其他子命令，照抄本文件改两处：文件名（=快捷命令名）与最后一行指向的 reference。不常用的 pin 及时删——命令空间也要治理。
