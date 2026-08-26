# /rust-skills:rust shape <feature> — 写码前设计

目的：在写第一行代码前把四个建模问题回答掉。产出是一页设计小结，不是代码。设计问题从**领域约束向下**（WHY → WHAT → HOW），不要先选 `Arc`/`sqlx`。跳过 shape 直接写复杂功能，返工概率远高于这十分钟。

## 四问（依次，引用决策树）

1. **落点**（D-1 / WS-11）：属于哪个业务域？默认追加现有模块。文件里两个不变量才建议新 `mod`。拿不准是否拆 **crate** 时停手，改走 `/rust-skills:rust crate <模块>`。不要为行数建议搬家，不要发明 `/split`。
2. **类型**（API-01/03/04/08）：核心数据怎么建模才能让非法状态不可表示？
   - **parse, don't validate**：边界一次 `Email::parse` / `TryFrom`，内部只传领域类型；禁业务层反复校验同一 `String`。
   - **newtype 字段私有**：只能经构造器产出，不提供 `&mut` 内层。
   - **三分类型**：row（`FromRow`）≠ 领域实体 ≠ 响应 DTO；转换写显式 `From`/`TryFrom`。
   - **状态机**：生命周期非法跳转会损坏数据或安全时用 typestate（`Order<Paid>` 才有 `ship`）；要入库/混放不同状态时用 enum。不为 CRUD 发明 phantom 状态。
   - 列出 3–6 个关键签名，标注 pub / `pub(crate)`。
3. **错误**（D-2）：每个可失败点是库错误（手写 enum 或已有 thiserror）还是应用错误（项目已有 anyhow/eyre）？变体少时不要为精简去加 crate（ERR-08）。哪些是不变量（expect 证明）？对外 API 是否把内部错误链映射成用户可处理变体（不泄 SQL/路径）？
4. **并发**（D-3，若涉及）：共享模型是消息传递还是共享内存？锁的临界区在哪、跨不跨 await？channel 容量依据？

## 输出格式

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

```
## <feature> 设计小结
落点：<路径> —— <理由>（D-1）
类型：<3-6 个关键签名>
错误：<错误类型草案>
并发：<模型一句话 | 不涉及>
测试面：单测 <哪些不变量> / 集成 <哪个公共 API 行为>（TEST-10）
风险：<最不确定的 1-2 点>
```

用户确认或修正后再进入实现；实现时逐条兑现小结，偏离要说明。facets 影响权重：artifact=lib 多问 semver；maturity=prototype 四问可从简但不省略错误建模。端口/适配器/hexagon 只在第二入口或可测边界已存在时引入（SIMP-01），不为单 handler CRUD 搭分层脚手架。有 axum 证据时落点/状态/错误类型参考 [axum/scaffold.md](axum/scaffold.md)；Tauri 项目的平台集合→插件→capabilities→窗口拓扑规划清单见 [tauri/develop.md](tauri/develop.md)，同样只出小结不写码。
