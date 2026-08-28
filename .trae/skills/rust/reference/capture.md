# /rust-skills:rust capture [lesson] — 项目捕获与人工提升

目的：把踩坑蒸馏为可验证的候选规则，同时保持已安装插件为只读。默认只写当前项目的 `.rust-skills/capture-outbox.md`；不得写已安装插件根（`${CLAUDE_PLUGIN_ROOT}`、`${GROK_PLUGIN_ROOT}`、`${CLAUDE_SKILL_DIR}`）或 marketplace 的版本化 cache。

无参数时回顾当前会话，提出一个最值得沉淀的教训并在写入前确认；有 lesson 时视为用户已选择主题，但仍先展示候选条目和目标文件。

## 六步蒸馏

1. **事实三问**：现象（原始证据）／根因（机制→设计→领域）／正确做法（为什么这个解对）。
2. **判普适层**：只在本项目成立 → RUST.md 债务候选；Rust 通用经验 → 规则候选；模型本来稳定掌握的通识 → 只记录证据，不膨胀规则库。
3. **归域**：META/WS/TEST/ERR/API/OWN/SIMP/ASYNC/UNSAFE/FFI/BUILD/DEP/LINT/OBS/PERF/GATE 选主要矛盾；局部清单用 AS/AX/CC/CK/PR/SE/SH/SO/SX/TA/XP。
4. **写候选**：`<待分配编号>[M|S|Y] <触发条件> + <禁止/要求> + <正确替代>`；声明执行方式为“机器门禁”或“评审清单项”。高危反射坑才配 ≤10 行的反例/正例。
5. **落项目 outbox**：追加日期、证据、候选条文、执行方式、建议压力场景和来源项目；对可能含密钥/个人数据的证据先脱敏。创建目录前报告精确路径。
6. **验证写入**：回读刚追加的条目，确认没有改插件安装目录、规则源或测试源。

## 人工提升

只有用户在 **rust-skills 源码仓库**中明确要求 `capture promote`，且确认本仓库存在任一 `.*-plugin/plugin.json`、`skills/rust/SKILL.md`、`tests/pressure-scenarios.md` 和可用 Git 元数据时，才执行提升：

1. 从项目 outbox 或用户给出的候选重验证事实，分配未使用编号。
2. 原子更新对应 `skills/rust/rules/<domain>.md`（随后跑 `./scripts/gen-rules-full.py`）与对应 reference。
3. 可机检规则同时实现并实际注册 gate；不可机检规则增加独立、可执行的压力/eval 场景。禁止注册永远返回成功的桩。
4. 运行一致性检查和相关压力场景，输出 diff 供人工审阅；不自动 commit。

## 输出模板

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

```
【捕获】<一句话教训>
根因层：机制 | 设计 | 领域
候选条文：<待分配编号>[级别] <全文>
执行方式：机器门禁 | 评审清单项
项目落位：<绝对路径>/.rust-skills/capture-outbox.md
压力场景：<标题与验收>
```

完成条件：项目 outbox 条目可回读；证据已脱敏；已安装插件目录零写入。只有人工提升完成后，才声称规则库已更新。
