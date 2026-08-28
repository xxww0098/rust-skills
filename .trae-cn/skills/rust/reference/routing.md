# 无参数路由：上下文感知菜单

用户打了裸 `/rust-skills:rust`，意思是「我该做什么」。菜单必须由项目状态推导，不是静态清单。

## 采集信号（按需，找到 2–3 个明确推荐即停）

1. 先确认 Cargo 根；不是 Cargo 项目就只给命令表并说明。
2. 读 RUST.md 的模式、债务、最近评审和基线规范版本；不存在时再看 Cargo.toml 判断 `document`/`init`。
3. Git 可用时看 status/diff stat，判断是否有可评审目标。
4. 只有门禁或测试债务是候选时才检查现有 CI/脚本/tests；不把“没有 xtask”本身当问题。
5. 只有文档治理可能进入推荐时才看 docs 首页与显式入链；不全量重读长文。

## 推荐逻辑（固定优先级，不打分）

```
显式命令 > 显式只读/写入意图 > 编译错误 > 动作动词 > 框架/领域证据 > target > 裸入口帮助
```

`/rust-skills:rust review --apply` → 显式 `review`，仍只读。`严格审查并修复 axum middleware` → 写入意图 + 领域 axum，inspect 后才 apply。

- 无 RUST.md 且项目非空 → 首推 `document`（先画像）；空项目/新项目 → 首推 `init`
- RUST.md 在但存在可观察风险（无统一关键 lint、通配 opt、工具链声明冲突）→ 推荐 `init`；纯布局差异不触发
- RUST.md 基线的规范版本落后于当前 SKILL frontmatter 版本 → 推荐 `doctor`（会标 DRIFT 并指向 `document`）
- 用户说「优化旧代码 / 整理遗留 / 这段太乱太长」且点了路径 → `distill`（结构梯子在 distill 内；crate 只建议）。没点路径先问一次目标，不扫全仓。
- 用户问「要不要拆 crate / 这个模块独立」且点了模块 → `crate`；没点模块只问一次路径。问「文件太长 / 要不要拆文件」→ 有路径的旧代码走 `distill`，写码中走 craft/WS-11。**不要**新开 `/optimize` 或 `/split`。
- Cargo.toml 仍是 edition 2018/2021 → 推荐 `init`（升 2024）或 `modernize`。edition 已是 2024 且 resolver 2 → 不因此推荐迁 resolver。
- 有未提交 .rs 改动 → `review`（点名具体文件）；改动含 unsafe/extern → 改推 `audit unsafe`
- 改动或画像显示子进程编排（`Command`/`fork`/进程池/IPC/信号处理）或用户抱怨子进程卡死/僵尸进程 → `process`
- Cargo.toml / 改动集出现 `sqlx` 依赖或 `query!`，且用户在问查询/池/事务 → `sqlx`；出现 `sea-orm` 则推 `seaorm`，两者同时存在时按当前改动命中的 crate 选，不双开
- Cargo.toml 有 `clap` 且用户在问子命令/补全/环境变量/退出码 → `cli`；有 `tracing`/`RUST_LOG` 且用户在问日志/span/OTel → `obs`（axum 的 TraceLayer 仍走 `axum`）
- Cargo.toml 有 `axum` 且用户在问鉴权/WebSocket/SSE/中间件/上传/测试/0.8 迁移 → `axum`（owner 再按「深入」表加载 `reference/axum/` 子 playbook）；有 `tauri` 且在问 capabilities/权限/插件/托盘/菜单/移动端/v1 迁移 → `tauri`（同理加载 `reference/tauri/`）。不因依赖存在就推荐，要有问题信号
- 最近评审快照有未清 M 级违规 → `harden` 或复跑 `review`
- RUST.md 债务清单里有「构建慢」类条目，或用户近期抱怨过编译时间 → `slim`
- 上次 `capture` 距今超过两周而会话里明显有踩坑痕迹 → 提醒 `capture`
- docs 存在但无首页，或有竞争权威源、失效证据/链接、未表达的 supersession → 推荐 `docs`
- 用户问「技术栈 / 用什么框架 / 选 axum 还是 actix / 该上 sqlx 还是 sea-orm」→ `stack`（默认只出表；「改」才加缺失层）
- 都不命中 → 按类别列全表，用一句话问用户现在关心什么。普通「改/实现」不要推菜单，让用户直接干，技能自己走 craft。
- 中英触发等价：路由表「触发」列含中文「」短语与英文短语，任一命中即可。改造四条互斥见 SKILL「路由」节：编译慢 → slim；升 edition/过时 API → modernize；上生产加固 → harden；旧代码删仪式 → distill。

## 输出格式

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。 先给 2–3 个带理由的推荐（每个给出可直接复制的完整命令，如 `/rust-skills:rust review crates/storage`），然后是按分类分组的完整命令表（路由表「分类」列即分组依据）；以「想执行哪条？回复命令即可」收尾。**只推荐，不执行。**
