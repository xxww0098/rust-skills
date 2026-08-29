# /rust-skills:rust seaorm [target] — SeaORM 数据层优化

目的：在有 sea-orm 依赖证据时审查或优化查询、连接池、事务、ActiveModel、upsert 与迁移。现行稳定线 **2.0.x**（crates.io 2.0.2，2026-08）。1.x 先确认 MSRV、runtime 与迁移约束，不凭版本号自动要求升级。本文件是 owner：先按 SO 清单体检，再按文末「深入」表只加载命中的 1–2 个子 playbook。
不要读：Cargo.toml 与当前改动都没有 `sea-orm` 证据时停。
触发族：SeaORM · N+1 · ActiveModel · Entity Loader · 内存泄漏（完整短语在 `scripts/command-metadata.json`）。

编排：多文件时按 [kernel/swarm.md](../kernel/swarm.md) — Loader/过取/泄漏分诊 · ActiveValue/嵌套save/upsert · 池/迁移/schema-sync。仍只加载 1–2 个子 playbook。 单文件或已有快照则跳过。

来源：[Entity Loader](https://www.sea-ql.org/SeaORM/docs/relation/entity-loader/)、[Nested Selects](https://www.sea-ql.org/SeaORM/docs/relation/nested-selects/)、[Model Loader](https://www.sea-ql.org/SeaORM/docs/relation/model-loader/)、[HasOne/HasMany](https://www.sea-ql.org/blog/2025-11-11-sea-orm-2.0/)、[ActiveModel](https://www.sea-ql.org/SeaORM/docs/basic-crud/active-model/)、[Insert / on_conflict](https://www.sea-ql.org/SeaORM/docs/basic-crud/insert/)、[Save](https://www.sea-ql.org/SeaORM/docs/basic-crud/save/)、[JSON](https://www.sea-ql.org/SeaORM/docs/basic-crud/json/)、[Nested ActiveModel](https://www.sea-ql.org/blog/2025-11-25-sea-orm-2.0/)、[2.0 Migration Guide](https://www.sea-ql.org/blog/2026-01-12-sea-orm-2.0/)、[Entity-first / schema-sync](https://www.sea-ql.org/SeaORM/docs/generate-entity/entity-first/)、[Writing Migration](https://www.sea-ql.org/SeaORM/docs/migration/writing-migration/)。规则只在前提命中时适用。

## SO 检查单（体检输出：位置｜编号｜问题｜修复）

本文件是 owner：编号定义在这里。细节、代码与反例只在命中的 1–2 个子 playbook 里读，不要把 `reference/seaorm/` 整目录读进来。

**连接与池** — 详见 [seaorm/pool.md](seaorm/pool.md)

- SO-01 `DatabaseConnection` 内部就是 `sqlx::Pool`，廉价 clone——禁止 `Arc`/`Arc<Mutex<>>` 包裹（同 AX-02 事故族）。
- SO-02 `ConnectOptions` 显式调优并注释依据：`max_connections`（按 DB 实测，不是越大越好）、`min_connections`、`acquire_timeout`/`connect_timeout`、`idle_timeout`/`max_lifetime`；缺省裸连 = 未做容量设计。启动 `db.ping()` 校验；关停 `db.close().await`。SQLite URL 钉 `mode=rwc` 或 `mode=ro`，不要默认可写内存库当生产。
- SO-03 生产热路径 `sqlx_logging(false)`（或调级）；慢查询观测交给 DB 侧/OBS 管道，不靠全量 SQL 日志。
- SO-09 事务优先闭包式 `db.transaction(|txn| …)`（Err 自动回滚）；手动 `begin`/`commit` 需说明理由。
- SO-10 事务要短：事务内禁止外部 IO/长 await（占住池连接 = 池饥饿的头号来源）。嵌套走 savepoint；不要自己 `SAVE TRANSACTION`。
- SO-12 迁移用 sea-orm-migration 版本化入库；实体由迁移后重新生成（schema-first）或 2.0 entity-first（要 `entity-registry` + `schema-sync`）。禁手改生成物不改迁移。已用 `sqlx::migrate!` / 纯 SQL 迁表、SeaORM 只生成实体是合法分工（X：[ccQpein](https://x.com/ccQpein/status/2051691030001422508)）。`schema-sync` 幂等只 **建** 缺表/列/键，不 DROP 表/列/FK（可 DROP INDEX）；生产关该 feature，启动路径禁 `sync()`。`apply()` 不检查现有 schema，只给初始化。慢查询先 `EXPLAIN`（META-02）。
- SO-20 旧迁移里不要用**当前** `ActiveModel` 做 seed（[discussion 1058](https://github.com/SeaQL/sea-orm/discussions/1058)）。Postgres 迁移默认原子；MySQL/SQLite **不是**。建表时 MySQL 才把 `.index()` 写进 `TableCreateStatement`；PG/SQLite 用 `SchemaManager::create_index()`。

**查询效率** — 详见 [seaorm/query.md](seaorm/query.md)

- SO-04 N+1 必查：循环里 `find_related` = 事故。一对多/多对多批量用 **LoaderTrait**（`load_many`/`load_many_to_many`，可带过滤器）；仅两实体小结果集才用 `find_with_related`（join 会复制「一」侧数据）；≥3 实体只能 loader。2.0 详情图走 SO-13，不要两条都写。
- SO-05 列裁剪：宽表禁默认全列，`DerivePartialModel`/`into_partial_model` 只取所需（SELECT * 是带宽与反序列化双税）。跨表投影用 `#[sea_orm(nested)]`。
- SO-06 大结果集用 `.stream()` 流式消费，不 `.all()` 收全量 `Vec`（SIMP-05 的数据层版）。
- SO-07 深分页用 `cursor_by`（游标），不用大 offset 的 `paginate`。`Entity::load().paginate` 先切**根**再按页 load 关系——禁止在 1-N JOIN 结果上 paginate。
- SO-08 批量写入走 `insert_many` 并按 DB 参数上限分块；2.0 用 `exec_with_returning()` 取回写入行（**仅 PG/SQLite**）。MySQL 走 `last_insert_id` 或再查。空迭代返回空/`None`，不要再写 `on_empty_do_nothing` 仪式。
- SO-11 复杂分析查询别硬掰查询构建器——2.0 的 `*_raw` 方法是正门；raw SQL 也要参数化。
- SO-14 `.eq()` / `.like()` / `.contains()` / `.add()` 必须 `use sea_orm::ExprTrait;`。`Alias::new("col")` 对静态名已不需要，写 `Expr::col("col")`。
- SO-15 `execute` / `query_one` / `query_all` / `stream` 收 SeaQuery 语句；裸 SQL 走 `execute_raw` / `query_*_raw` / `stream_raw`。`insert_many` 的 `last_insert_id` 是 `Option<Value>`。
- SO-16 1.x → 2.0 是破坏性迁移。先确认 MSRV/runtime/迁移表，不凭版本号自动升级。Diesel 不要和 SeaORM/sqlx 在同一 runtime 混用。`async-std` 迁移 crate 已弃用，换 tokio。
- SO-19 按关系过滤父行用 `EXISTS`，不要 `all()` 再内存滤。`filter_by_id` / `filter_by_*` 是主键捷径。
- SO-21 `ActiveModel`/`Model` 不直接 `Serialize` 出 API（同 SX-08 / API-08）。handler 不堆 `Entity::find()`。
- SO-22 生产路径不要把 `ModelEx` 整树当列表页 payload。列表用 SO-05 partial；详情页才 `load().with(...)`。

**Entity Loader 策略** — 详见 [seaorm/loader.md](seaorm/loader.md)

- SO-13 混合策略，不是「全部 JOIN」也不是「全部 IN」（[Entity Loader](https://www.sea-ql.org/SeaORM/docs/relation/entity-loader/)）。生成物概念上就是 `find_also`（1-1 JOIN，最多三表）+ `LoaderTrait::load_many`（1-N / M-N 走 data loader，`WHERE fk IN`；M-N 连 junction 仍一条）。JOIN 1-N 会笛卡尔复制父行。`.with(Rel)` = 根上兄弟；`.with((Child, Grand))` = 再下一跳。要 `#[sea_orm::model]`；1.x compact 没有 Loader。不要把 `find_related` 循环当 Loader。
- SO-26 三条读路径按形状选，不要叠用：列表/API 投影、列裁剪 → SO-05 `DerivePartialModel` + join；详情整棵 `ModelEx` → `Entity::load().with(..)`（SO-13）；已有 `Vec<Model>`，相关行还要过滤 → `load_many(Entity::find().filter(..), db)`（SO-04）。列表页 `load().with(posts)` = 过取（SO-22）。
- SO-27 `HasOne`/`HasMany` 是三态不是 `Option`（[HasOne/HasMany](https://www.sea-ql.org/blog/2025-11-11-sea-orm-2.0/)）：`HasOne::{Unloaded, NotFound, Loaded}`；`HasMany::{Unloaded, Loaded(Vec)}`。`Unloaded` = 没 `.with()`；`NotFound` = 加载了但没有行。禁止 `if profile.is_none()` 把 Unloaded 当缺失。钻石两 FK：`.with(Relation::Manager)` 不是两次 `.with(Worker)`（[#3030](https://github.com/SeaQL/sea-orm/pull/3030)）。深层链式 1-1 不要指望 `.with((b, (c, (d, e))))`（[discussion 2840](https://github.com/SeaQL/sea-orm/discussions/2840)）。自引用走 `load_self` / `load_self_many`。
- SO-28 Entity Loader 内存峰值按**唯一行**计，不按 JOIN 复制计（官方「each model is transferred only once」）。JOIN 1-N / `find_with_related` 峰值 ≈ 复制后的宽行。data loader 峰值 ≈ unique(父) + unique(子) + `IN` 的 ID 列表。1-1 JOIN 行数 = 父行；`HasOne::Loaded(Box<ModelEx>)` 每条 1-1 一次堆分配。官方「preventing over-fetching」= 不 `.with()` 的关系不取——**不是列裁剪**：`load()` 仍 SELECT 全列成 `ModelEx`。列表/窄 DTO 走 SO-05 PartialModel。`load().all()` 整图物化（SO-06）。不要 `clone` `ModelEx` 树。
- SO-29 内存优化按杠杆顺序，不要先调池（[discussion 2850](https://github.com/SeaQL/sea-orm/discussions/2850)）：①换路径（列表 PartialModel）②切边（只 `.with()` 用到的关系）③切根（`filter` 打在根上，`load().paginate` / `cursor_by`）④切子行（`Entity::load().with(E).filter(child::Column)` 对 has_many **无效**，缺 FROM；子行走 `load_many(Entity::find().filter(..), db)`）⑤切列（Loader 没有 `select_only`）⑥切寿命（分页丢掉上一页，禁 clone 树）。假优化：JOIN 1-N 省往返、给 `.with()` 当投影、调 `max_connections` 当内存策略。

**ActiveValue / 嵌套保存 / upsert** — 详见 [seaorm/active.md](seaorm/active.md)

- SO-17 `ActiveValue` 三态必须分清：`Set(v)` 写入 SQL；`Unchanged(v)` 来自库、UPDATE 时进 WHERE 不进 SET；`NotSet` 省略该列，让 DB `DEFAULT` / serial / identity 生效。`Set(None)` 是显式 NULL，不是默认值。新建 `ActiveModel` 默认全 `NotSet`；`Model.into_active_model()` 是 `Unchanged`。禁止 `id: Set(0)`、`created_at: Set(Utc::now())` 覆盖库默认（X：[PhyroKelstein](https://x.com/PhyroKelstein/status/1941030262324031845)）。`try_into_model` 遇 NotSet → `AttrNotSet`。同值更新用 `set_if_not_equals`。2.0 `Update::one` 要 `.validate()`。
- SO-18 2.0 嵌套图用一次 `.save(db)`（[Nested ActiveModel](https://www.sea-ql.org/blog/2025-11-25-sea-orm-2.0/)）：走 FK 顺序、同一事务、按 `Set` 检测变更。要 `#[sea_orm::model]`，`compact_model` 没有这套。二次 `save` 应是 no-op；`replace_all` 会删未列出的子行。不要手写「先 insert user 再循环 insert posts」。
- SO-23 冲突写入走 `on_conflict`（[Insert](https://www.sea-ql.org/SeaORM/docs/basic-crud/insert/)）：`OnConflict::column(Col).do_nothing()` / `.update_columns([...])`。0 行写入 = `DbErr::RecordNotInserted`，不是静默成功——要 Ok 走 `.try_insert()` → `TryInsertResult::Conflicted`。不要用单行 `save()` 当 upsert。
- SO-24 单行 `save()` 按 PK 状态分流（[Save](https://www.sea-ql.org/SeaORM/docs/basic-crud/save/)）：PK `NotSet` → insert，`Set`/`Unchanged` → update。这不是 SO-18 的 2.0 嵌套 `.save`。幂等/冲突走 SO-23。
- SO-25 `ActiveModel::from_json`：JSON 缺字段 → `NotSet`（2.0）；`set_from_json` **不改已有 PK**。入站 JSON 用 DTO 再转 ActiveModel。Entity 上 `#[serde(rename_all)]` 再 `from_json` 有字段错位先例（[issue 2257](https://github.com/SeaQL/sea-orm/issues/2257)，X：[FusionZhu](https://x.com/CoderFusionZhu/status/1909977622001619305)）。PK 用 `#[serde(skip_deserializing)]`。

**泄漏分诊** — 详见 [seaorm/leak.md](seaorm/leak.md)

- SO-30 「泄漏」先分四类，不要对着 RSS 开治（[discussion 2901](https://github.com/SeaQL/sea-orm/discussions/2901)）。官方：无缓存、无特殊 `Drop`；默认分配器不立刻把页还给 OS；RSS 不是单条语句的细粒度指标。①分配器/碎片（不是泄漏）：大 JSON/`Value`/`ActiveModel::insert` 后 RSS 台阶、raw SQL 却平稳。指纹（2901）：~10MB JSON，`ActiveModel` RSS 10→121MB，同内容 raw SQL ~13MB。换 mimalloc/jemalloc 复测；JSON 列当 `String` + `jsonb`。②活图没放：`OnceCell`/`lazy_static`/`app state` 里堆 `Vec<ModelEx>`。③连接没还：事务跨外部 IO（SO-10）；每请求 `Database::connect`（[608](https://github.com/SeaQL/sea-orm/discussions/608)）；`Arc<Mutex<DatabaseConnection>>`（SO-01）。关停 `close().await`。④真泄漏：换分配器 + 图已 Drop + 连接已还，heaptrack/dhat 仍跨请求单调涨。**分诊顺序**（不要跳）：一次语句后 RSS 上台阶、后续请求不再涨 → 桶 1。作用域结束、分配字节回落但 RSS 不还 OS → 仍桶 1。分配字节跨请求单调涨 → 桶 2。连接数一起涨 → 桶 3。1–4 排除后再 heaptrack → 桶 4。假优化：调 `max_connections`/`idle_timeout` 当治泄漏。

**测试**：单测用 `MockDatabase` 断言语句与返回；集成测真库且缺环境 fail-loud（TEST-07），禁静默跳过。

## 深入（按信号加载）

一次只加载 1–2 个；`review`/`audit`/普通实现命中 sea-orm 证据时按同表叠加，不整目录读。

| 用户信号 / 代码证据 | 加载 |
|---|---|
| 循环 `find_related`、列表慢、全列、`.all()` 收大 `Vec`、深分页、`ExprTrait`、raw SQL 改名 | [seaorm/query.md](seaorm/query.md) |
| 「Entity Loader / ModelEx / Unloaded / JOIN 1-N / Loader 内存 / 切边 / 切根」；`Entity::load().with`、`find_with_related` | [seaorm/loader.md](seaorm/loader.md) |
| 「ActiveModel / NotSet / 嵌套保存 / upsert / on_conflict / from_json」；`Set(0)`、`Set(None)`、手插子行 | [seaorm/active.md](seaorm/active.md) |
| 「连接池 / ConnectOptions / 事务占连接 / schema-sync / 迁移原子性」；`Arc<DatabaseConnection>` | [seaorm/pool.md](seaorm/pool.md) |
| 「内存泄漏 / RSS / 不释放 / 泄漏分诊」；`OnceCell<Vec<ModelEx>>`、每请求 `connect`、大 JSON `Set(Value)` | [seaorm/leak.md](seaorm/leak.md) |

## 验证（PERF-01）

同机前后对比：查询计时（p50/p99）、往返次数（N+1 修复前后 SQL 条数）、`EXPLAIN` 计划变化。内存争议再加：SELECT 列数/行宽、结果行数 vs unique 父行、RSS 或分配器峰值（`load().all().with(1-N)` vs PartialModel）。「泄漏」用分配字节/heaptrack 跨请求是否单调涨，不要单看一次 RSS 台阶（SO-30）。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表 + 按收益排序候选（SO 编号 + 全局规则号）+ 验证方案。`--apply` 或明确“修/改/实现”时：再给实际改动与前后数据。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
