# /rust-skills:rust harden [target] — 生产加固

目的：把「能跑」的代码推到「能上生产」。批量应用 ERR/OBS/ASYNC 域规则 + 边界条件。缺省 target = 最近改动的模块；service 模式的默认强化命令。裸调用只做体检；`--apply` 或同一请求明确写入授权后才改码。

## 加固清单（逐项过；写入时改动配规则号）

1. **错误路径**（ERR）：裸 unwrap 清点 → `?` 传播或 `expect("invariant: …")`；吞错的 `let _ =` → 记录或论证；错误上下文链完整性（应用层每跳 with_context）；main 的退出码语义。
2. **边界条件**：只对信任边界和本次目标枚举空/零长/超长、溢出、非法路径/编码和并发重入；把可观察行为补进最小契约测试，不为简单内部函数制造表格。
3. **可观测性**（OBS）：关键路径的结构化日志（级别语义对照 OBS-04）；错误处理一次原则清查（重复打日志的链路）；`#[instrument]` 的 skip 检查（大对象/敏感字段）。细节走 [obs.md](obs.md)；axum 服务再叠加 [axum/observability.md](axum/observability.md)。
4. **停机与资源**（service 模式）：优雅停机路径（统一取消信号是否贯通——CancellationToken 或可证等价的 watch/oneshot/shutdown future，见 AS-04）；spawn 任务归宿（JoinSet/TaskTracker）与总超时；channel 容量与背压在停机时的语义；连接/文件句柄的 Drop 路径。协作停机后再 abort 兜底 ≠ 失败；**硬 abort 作为唯一归宿且不 join/不观测 panic** 才判失败。axum 服务的信号/drain/健康检查接线见 [axum/deploy.md](axum/deploy.md)。
5. **超时与重试**：每个外部调用有超时吗？重试有上界与抖动吗？幂等性说明？（细节 AS-11；出站 HTTP 见 AX-17）
6. **密钥与日志**：源码/仓库无密钥；`#[instrument]` 与日志字段 skip 敏感值（OBS-02）；错误一次原则（OBS-03）。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

- **只读体检**：清单 1–6 分栏「主目标｜邻接证据」→ 通过 / 缺口 / 改进项 → 可粘贴 RUST.md 债务候选（默认不写；`--record` 才写入 managed）。
- **写入授权后**：改动 diff（按域分批）+ 新增测试清单 + 未加固残留（同上 `--record` 规则）。

完成条件：体检时每项有判定与证据；写入时目标中可触发风险已有修复和回归检查；不能运行项目门禁时如实列缺口。
