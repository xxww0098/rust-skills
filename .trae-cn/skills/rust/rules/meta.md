## META 元规则
- META-01[M] 执行方式默认是 review/eval；只有被 xtask 真实实现、配失败 fixture 并注册的规则才升级为 machine gate。不得用固定成功桩冒充覆盖。
- META-02[M] 先量化再优化：无 timings/tree/bench 基线数据的优化一律不做。
- META-03[M] 新增规则必须同时新增可执行验证：可机械判定的补失败 fixture + 门禁；否则补独立压力/eval 场景。技能仓本身以命令级压力场景 + consistency 为准；machine gate fixture 只在用户项目落地 `gate` 后计算。
- META-04[M] 正确建模、清晰所有权、可测边界 优先于一切微优化。
- META-05[M] 风险决定验证强度：prototype 可跳过纯治理项，但不能跳过与当前改动相关的正确性、安全和数据损失防护。产物类型与成熟度分开记录，不从仓库整体推断每个 crate。
