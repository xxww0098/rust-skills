# /rust-skills:rust sqlx [target] — SQLx 数据层优化

目的：在有 `sqlx` 依赖证据时审查或优化连接池、编译期查询、事务与类型边界。现行稳定线 **0.8 与 0.9**（crates.io 0.9.0，2026-05，MSRV 1.94）。0.7 仍按本清单审；不要只为版本号升 0.9。0.9 可选用 crate 根 `sqlx.toml`（多库 `DATABASE_URL` 改名、宏类型覆盖、迁移表改名），**不是**新项目必做脚手架。本命令是 ASYNC/SIMP/API/PERF 的数据层特化；SeaORM 项目走 [seaorm.md](seaorm.md)。裸调用只体检。
不要读：Cargo.toml 与当前改动都没有 `sqlx` 证据时停。sqlx 0.9 的 MSRV 1.94 高于仓基线 1.85 时不要为「现行稳定线」抬全仓 rust-version（DEP-08）。

来源：sqlx `Pool` 文档（默认配置面向测试/轻负载）、`query!` 离线准备、Bulletproof Rust Web「Database Layer」。规则只在前提命中时适用。

## SX 检查单（体检输出：位置｜编号｜问题｜修复）

**连接与池**

- SX-01 `Pool` 廉价 clone（内部 Arc）——禁止 `Arc<Pool>` / `Arc<Mutex<Pool>>`（同 AX-02）。
- SX-02 sqlx 文档写明默认池面向测试/轻负载。生产必须显式 `max_connections`（按 DB 上限 ÷ 实例数）、`acquire_timeout`、`idle_timeout`/`max_lifetime` 并注释依据。缺省裸连 = 未做容量设计。注意：acquire 在取出连接后被取消/超时会把该连接丢掉。

**查询与编译期检查**

- SX-03 静态 SQL 优先 `query!` / `query_as!`（编译期对真实 schema 校验）。CI 用离线模式：入库 `.sqlx/` + `SQLX_OFFLINE=true`，并跑 `cargo sqlx prepare --check`；缺缓存或 CI 连库脆弱时标缺口，不假装已校验。
- SX-04 SQL 一律参数绑定；禁 `format!`/`+` 拼查询（注入面 + 毁掉预处理）。动态片段只走受控白名单标识符，不能把用户字符串嵌进语句。
- SX-05 大结果集用 `.fetch()` 流式消费，不 `.fetch_all()` 收全量 `Vec`（SIMP-05 的数据层版）。
- SX-06 N+1 必查：循环里再 `query!` = 事故。改 `ANY($1)` / `UNNEST` / 一次 JOIN；修复前后数 SQL 条数。

```rust
// ✗ SX-04/06 拼接 + N+1
for id in ids {
    let q = format!("SELECT * FROM users WHERE id = '{id}'");
    sqlx::query(&q).fetch_one(&pool).await?;
}

// ✓ 一次参数化查询
sqlx::query_as!(UserRow, "SELECT id, email FROM users WHERE id = ANY($1)", &ids)
    .fetch_all(&pool)
    .await?;
```

**事务与类型边界**

- SX-07 事务要短：`pool.begin()` 后只做本库读写；事务内禁止外部 HTTP/邮件/长 await（占住池连接 = 池饥饿）。`?` 早退时 `Transaction` Drop 回滚，不要手写「失败再 rollback」仪式。
- SX-08 wire/row/领域分离：`FromRow` 结构不直接 `Serialize` 出 API；密码哈希、软删标记、内部旗标不得跟响应 DTO 同体（API-08）。handler 里堆 SQL 仅当端点就是 1–2 条查询且无第二入口；查询开始复用或要跨语句事务 → 收到 repository/query 类型，不为 CRUD 发明 hexagon。
- SX-09 钱/精确小数：Postgres `NUMERIC`/`DECIMAL` 解到 `rust_decimal::Decimal`（crate feature `rust_decimal`），禁 `f64`。宏推断失败时用列覆盖 `AS "price: Decimal"`，不要改成 `f64` 过编译。

**工程面**

- SX-10 迁移用 `sqlx::migrate!` 版本化入库；多实例滚动发布不要只靠启动时 migrate（advisory lock 能串行，但失败语义含糊）——生产用独立迁移任务/init container。慢查询先 `EXPLAIN`（META-02），sqlx 不会替你建索引。0.9 若用 `sqlx.toml` 改迁移表名/忽略空白，CI 的 `prepare --check` 必须读同一份配置。
- SX-11 列裁剪：禁无理由 `SELECT *`；宏查询的列清单即契约，改列要同步 `.sqlx/` 缓存。
- SX-12 集成测真库且缺环境 fail-loud（TEST-07）；`#[sqlx::test]` / testcontainers 二选一。禁静默跳过变绿。

**0.9 工程面**

- SX-13 `sqlx.toml`（0.9，crate feature `sqlx-toml`，**sqlx 默认关**、sqlx-cli 默认开）只在多库/`DATABASE_URL` 改名、宏全局类型覆盖、迁移表改名、忽略迁移空白时用。不是新项目脚手架。CI 的 `prepare --check` 必须读同一份文件。
- SX-14 runtime feature：0.9 删了 `runtime-tokio-native-tls` 这种捆绑名，runtime 与 TLS 分开开。`async-std` 已弃用，继任是 `runtime-smol` / `runtime-async-global-executor`。workspace 混用两个 runtime = 事故。
- SX-15 事务执行器：`&mut txn` 经常报 `Executor<'_> is not implemented`——写成 `&mut *txn`（deref 到连接）。不要为过编译把事务改回 `&pool`。
- SX-16 SQLite `load_extension` / `serialize` 在 0.9 进非默认 feature 且加载是 unsafe；`SqliteValue` 不再 `Send+Sync`。不要为方便把 `sqlite-load-extension` 开进默认 features。

**测试**：单测不连库时测的是编排，不是 SQL；SQL 正确性交给宏 + 真库测试。

## 验证（PERF-01）

同机前后对比：查询 p50/p99、往返次数（N+1 修复前后 SQL 条数）、`EXPLAIN` 计划。编译期查询改动必须 `cargo sqlx prepare --check` 或等价离线证据。

## 输出

按 [SKILL 输出契约](../SKILL.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表 + 按收益排序候选（SX 编号 + 全局规则号）+ 验证方案。`--apply` 或明确“修/改/实现”时：再给实际改动与前后数据。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
