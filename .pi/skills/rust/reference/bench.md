# /rust-skills:rust bench <target> — 性能纪律

目的：给性能主张装上数据（PERF-01..05）。两种形态：**搭基准**（target 尚无 bench）与**验证改动**（有 bench，出前后对比）。脏工作区且无 before 基线时：**只读停在采集方案**，禁止 stash / 清 target / 用 after 冒充 before（场景 24）；无 `--apply`/「修/改/实现」不落盘 bench 代码。

## 搭基准

1. 优先复用项目已有压测装置（criterion、divan、或仓内 perf 脚本）；无则再建议 criterion：`benches/<name>.rs` + `[[bench]] harness = false`；bench 依赖走 dev-dependencies。
2. 数据集必须代表生产分布（PERF-04）——问用户拿真实样本或按其描述构造；玩具输入上的优化是自欺。
3. `std::hint::black_box` 包住输入与结果，防止常量折叠。
4. 首跑记录基线：机器信息 + 数字；默认输出可粘贴的 RUST.md「性能基线」条目，显式 `--record` 才写入。

## 验证改动

1. **同机同负载**跑 before 与 after，各 ≥3 轮取置信区间。before 必须在改动前采集，或使用用户明确授权的独立临时 worktree/源码副本；不得 stash、覆盖或清理用户工作区。
2. 使用真实交付 profile；为 profiling 保留符号时，其优化级别/特性必须与交付语义一致。debug 或快速迭代 profile 只用于定位，不能外推发布性能。
3. 结论只认区间不重叠的差异；噪声范围内的「提升」如实报告为无显著变化。
4. 改动违背优化次序（PERF-02：算法→分配→并行→微调）时提醒：上游还有更大的鱼（贴证据，如火焰图热点）。`collect` 完立刻再扫一遍、或冷路径为省 clone 拧设计，都算次序错。

## 深挖工具（需要定位时）

CPU：`samply record` / perf + 火焰图——先看图再动手；堆：dhat；构建性能不归本命令管 → `/rust-skills:rust slim`。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

- **无 before / 脏树未授权副本**：停止因果结论；输出采集步骤 + 可选装置候选；不改文件。
- **有数据后**：bench 代码（若已授权）+ 前后对比表（均值、区间、显著性）+ 结论一句话；PR 可粘贴数据段。无显著提升的改动建议回滚。
