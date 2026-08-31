---
description: /review — 根据提示自适应路由的只读 Rust 评审
---

# /review

这是 `/rust-skills:rust review` 的稳定 pin。`$ARGUMENTS` 同时承载范围与评审意图：现存路径/可验证 revision 先定范围，其余自然语言用于选择测试、Cargo、unsafe/security、性能、异步/并发、框架、精简、生产或交付镜头。

执行：加载 rust skill 与 `reference/review.md`。`review` 始终是唯一只读 owner；默认选择一个主镜头，只有独立风险有直接证据时再加一个补充镜头。所有镜头共享一次 ProjectSnapshot、冻结范围和验证账本，同一命令指纹不重复执行。

缺省范围包含已跟踪改动和未跟踪文件；等价于 `/rust-skills:rust review $ARGUMENTS`。显式 `/review` 不会把子 playbook 的 `--apply` 能力带进 review；即使参数里写“修/改”，也只给 Finding 与对应的后续写命令。只有显式 `--record` 才可写 RUST.md 评审快照。
