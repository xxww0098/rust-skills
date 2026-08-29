# /rust-skills:rust seaorm [target] — SeaORM 数据层优化

目的：在有 sea-orm 依赖证据时审查或优化查询、连接池、事务、ActiveModel、upsert 与迁移。现行稳定线 **2.0.x**（crates.io 2.0.2，2026-08）。1.x 先确认 MSRV、runtime 与迁移约束，不凭版本号自动要求升级。
不要读：Cargo.toml 与当前改动都没有 `sea-orm` 证据时停。

编排：多文件时按 [kernel/swarm.md](../kernel/swarm.md) — Loader/过取/泄漏分诊 · ActiveValue/嵌套save/upsert · 池/迁移/schema-sync。 单文件或已有快照则跳过。

来源：[Entity Loader](https://www.sea-ql.org/SeaORM/docs/relation/entity-loader/)、[Nested Selects](https://www.sea-ql.org/SeaORM/docs/relation/nested-selects/)、[Model Loader](https://www.sea-ql.org/SeaORM/docs/relation/model-loader/)、[HasOne/HasMany](https://www.sea-ql.org/blog/2025-11-11-sea-orm-2.0/)、[ActiveModel](https://www.sea-ql.org/SeaORM/docs/basic-crud/active-model/)、[Insert / on_conflict](https://www.sea-ql.org/SeaORM/docs/basic-crud/insert/)、[Save](https://www.sea-ql.org/SeaORM/docs/basic-crud/save/)、[JSON](https://www.sea-ql.org/SeaORM/docs/basic-crud/json/)、[Nested ActiveModel](https://www.sea-ql.org/blog/2025-11-25-sea-orm-2.0/)、[2.0 Migration Guide](https://www.sea-ql.org/blog/2026-01-12-sea-orm-2.0/)、[Entity-first / schema-sync](https://www.sea-ql.org/SeaORM/docs/generate-entity/entity-first/)、[Writing Migration](https://www.sea-ql.org/SeaORM/docs/migration/writing-migration/)。规则只在前提命中时适用。

## SO 检查单（体检输出：位置｜编号｜问题｜修复）

**连接与池**

- SO-01 `DatabaseConnection` 内部就是 `sqlx::Pool`，廉价 clone——禁止 `Arc`/`Arc<Mutex<>>` 包裹（同 AX-02 事故族）。
- SO-02 `ConnectOptions` 显式调优并注释依据：`max_connections`（按 DB 实测，不是越大越好）、`min_connections`、`acquire_timeout`/`connect_timeout`、`idle_timeout`/`max_lifetime`；缺省裸连 = 未做容量设计。启动 `db.ping()` 校验；关停 `db.close().await`。SQLite URL 钉 `mode=rwc` 或 `mode=ro`，不要默认可写内存库当生产。
- SO-03 生产热路径 `sqlx_logging(false)`（或调级）；慢查询观测交给 DB 侧/OBS 管道，不靠全量 SQL 日志。

**查询效率**

- SO-04 N+1 必查：循环里 `find_related` = 事故。一对多/多对多批量场景用 **LoaderTrait**（`load_many`/`load_many_to_many`，可带过滤器）；仅两实体小结果集才用 `find_with_related`（join 会复制「一」侧数据）；≥3 实体只能 loader。2.0 详情图走 SO-13，不要两条都写。
- SO-05 列裁剪：宽表禁默认全列，`DerivePartialModel`/`into_partial_model` 只取所需（SELECT * 是带宽与反序列化双税）。跨表投影用 `#[sea_orm(nested)]` 嵌进 typed partial，不要 join 完再丢全实体。
- SO-06 大结果集用 `.stream()` 流式消费，不 `.all()` 收全量 `Vec`（SIMP-05 的数据层版）。
- SO-07 深分页用 `cursor_by`（游标），不用大 offset 的 `paginate`（DB 扫描代价随页深线性涨）。`Entity::load().paginate` 先切**根**再按页 load 关系——禁止在 1-N JOIN 结果上 paginate（按子行切片）。
- SO-08 批量写入走 `insert_many` 并按 DB 参数上限分块；2.0 用 `exec_with_returning()` 取回写入行（**仅 PG/SQLite** 有 RETURNING）。MySQL 走 `last_insert_id` 或再查，不要假装 returning 通用。空迭代返回空/`None`，不要再写 `on_empty_do_nothing` 仪式。

```rust
// ✗ SO-04 N+1：1 + N 条 SQL
for cake in Cake::find().all(db).await? {
    let fruits = cake.find_related(Fruit).all(db).await?;
}

// ✓ 2 条 SQL，内存合并；可带过滤
let cakes = Cake::find().all(db).await?;
let fruits = cakes.load_many(Fruit, db).await?;
```

**Entity Loader 策略**（2.0 读图正门）

- SO-13 混合策略，不是「全部 JOIN」也不是「全部 IN」（[Entity Loader](https://www.sea-ql.org/SeaORM/docs/relation/entity-loader/)）。生成物概念上就是 `find_also`（1-1）+ `LoaderTrait::load_many`（1-N），不是新引擎。
  - **1-1**：JOIN，最多三表一条 SQL。1-1 不爆炸行数，所以才 JOIN。
  - **1-N / M-N**：data loader，`WHERE fk IN (..)`；M-N 连 junction 仍一条。JOIN 1-N 会笛卡尔复制父行。
  - **嵌套**：收齐上一跳 ID 再发一条。`user JOIN profile` + `post WHERE user_id IN` + `comment WHERE post_id IN` = 3 条，不是 N+1。
  - `.with(Rel)` = 根上的兄弟关系；`.with((Child, Grand))` = 沿 Child 再下一跳。要 `#[sea_orm::model]` 或 `#[sea_orm::compact_model]`；1.x compact 没有 Loader。不要把 `find_related` 循环当 Loader。
- SO-26 三条读路径按形状选，不要叠用：
  - 列表/API 投影、列裁剪 → SO-05 `DerivePartialModel` + join，一条 SQL。
  - 详情整棵 `ModelEx` → `Entity::load().with(..)`（SO-13）。
  - 已有 `Vec<Model>`，相关行还要过滤 → `load_many(Entity::find().filter(..), db)`（SO-04）。
  列表页 `load().with(posts)` = 过取（SO-22）。
- SO-27 `HasOne`/`HasMany` 是三态不是 `Option`（[HasOne/HasMany](https://www.sea-ql.org/blog/2025-11-11-sea-orm-2.0/)）：`HasOne::{Unloaded, NotFound, Loaded}`；`HasMany::{Unloaded, Loaded(Vec)}`。`Unloaded` = 没 `.with()`；`NotFound` = 加载了但没有行。禁止 `if profile.is_none()` 把 Unloaded 当缺失。钻石两 FK 指向同一表：`.with(Relation::Manager)` 不是两次 `.with(Worker)`（[#3030](https://github.com/SeaQL/sea-orm/pull/3030)）。深层链式 1-1 不要指望 `.with((b, (c, (d, e))))`（[discussion 2840](https://github.com/SeaQL/sea-orm/discussions/2840)）——逐步 load 或 PartialModel join。自引用走 `load_self` / `load_self_many`。
- SO-28 Entity Loader 内存峰值按**唯一行**计，不按 JOIN 复制计（[Select / batch loading](https://www.sea-ql.org/SeaORM/docs/basic-crud/select/)：「one side rows may duplicate」；Loader「each model is transferred only once」，多一次往返换带宽）。
  - **JOIN 1-N / `find_with_related`**：线上父行 × 子行；解码后再去重。峰值 ≈ 复制后的宽行。
  - **data loader**：峰值 ≈ unique(父) + unique(子) + `IN` 的 ID 列表；`load_many` 先给出 `Vec<Vec<T>>` 再 zip 进 `HasMany`，短时间双持有。
  - **1-1 JOIN**：行数 = 父行，行宽 = 最多三表全列；`HasOne::Loaded(Box<ModelEx>)` 每条 1-1 一次堆分配（递归类型 + 压 enum）。
  - 官方「preventing over-fetching」= 不 `.with()` 的关系不取、1-N 不 JOIN 复制父行。**不是列裁剪**：`load()` 仍 SELECT 被加载实体的全列成 `ModelEx`。列表/窄 DTO 走 SO-05 PartialModel。
  - `load().all()` 整图物化（SO-06）；切根用 `load().paginate`（SO-07）。不要 `clone` `ModelEx` 树再 Serialize（OWN-01 + SO-22）。无界 `.all().with(1-N)` 的子行和 `IN` 列表才是 RSS 主项，Loader 不会自动分块。
- SO-29 内存优化按杠杆顺序，不要先调池（[Entity Loader paginate](https://www.sea-ql.org/SeaORM/docs/relation/entity-loader/) · [Nested Selects](https://www.sea-ql.org/SeaORM/docs/relation/nested-selects/) · [discussion 2850](https://github.com/SeaQL/sea-orm/discussions/2850)）：
  1. **换路径**：列表/卡片 → PartialModel（SO-26/05）。详情才 `load().with`。这是最大一刀。
  2. **切边**：只 `.with()` 响应真正用到的关系。`.with((post, comment))` 会把该页所有 post 的全部 comment 拉齐。
  3. **切根**：`filter` 打在**根**上；`load().paginate` / `cursor_by` 切根（深页用游标，SO-07）。禁止无界 `.all()`，禁止 `all()` 再内存 skip。
  4. **切子行**：`Entity::load().with(E).filter(child::Column)` 对 has_many **无效**（缺 FROM，[2850](https://github.com/SeaQL/sea-orm/discussions/2850)）。子行过滤走 `load_many(Entity::find().filter(..), db)`。按子条件滤父行走 EXISTS（SO-19），不要先 load 再内存滤。
  5. **切列**：Loader 没有 `select_only`。要窄列就离开 `load()`。1-1 JOIN 仍是相关表全列。
  6. **切寿命**：分页循环丢掉上一页；映射 DTO 后放掉 `ModelEx`；禁 `clone` 树（SO-28）。`load()` 概念实现是 `all` + `load_many`，不要指望它 `stream` 整图。
  假优化：JOIN 1-N 省往返、给 Loader 加更多 `.with()` 当投影、调 `max_connections` 当内存策略。
- SO-30 「泄漏」先分四类，不要对着 RSS 开治（[discussion 2901](https://github.com/SeaQL/sea-orm/discussions/2901) · [Connection](https://www.sea-ql.org/SeaORM/docs/install-and-config/connection/)）。官方：无缓存、无特殊 `Drop`；默认分配器不立刻把页还给 OS；RSS 不是单条语句的细粒度指标。
  1. **分配器/碎片（不是泄漏）**：大 JSON/`Value`/`ActiveModel::insert` 后 RSS 台阶式上升、raw SQL 却平稳 → 换 mimalloc/jemalloc 复测；JSON 列尽量当 `String` + `jsonb` 写入，不要把 10MB `serde_json::Value` 推进 `Set`。
  2. **活图没放**：`OnceCell`/`lazy_static`/`app state` 里堆 `Vec<ModelEx>`、clone 树、无界 `.all()`（SO-28/29）。进程级该复用的是**池**（`DatabaseConnection`），不是查询结果。
  3. **连接没还**：事务跨外部 IO（SO-10）；`stream` 没消费完就丢任务；每请求 `Database::connect`（[608](https://github.com/SeaQL/sea-orm/discussions/608) 要复用池）；`Arc<Mutex<DatabaseConnection>>`（SO-01）。关停 `close().await`（sqlx 无 async Drop，最后一把 handle 丢了未必立刻拆连接）。`idle_timeout`/`max_lifetime` 回收闲连接，不是治泄漏。
  4. **真泄漏**：换分配器 + 图已 Drop + 连接已还，heaptrack/dhat 仍跨请求单调涨 → 再查依赖。禁止把 2901 那种 RSS 当 SeaORM 泄漏修代码。

```rust
// ✗ JOIN 1-N 再 paginate；Unloaded 当 None；深层 1-1 塞进一层 tuple
User::find().find_with_related(Post).paginate(db, 10);
let u = user::Entity::load().one(db).await?.unwrap();
if u.profile.is_none() { /* Unloaded，不是没 profile */ }
user::Entity::load().with((b::Entity, (c::Entity, d::Entity))).all(db);

// ✗ SO-28 列表整图 + clone 树；SO-29 用子列 filter 当切子行
let users = user::Entity::load().with(post::Entity).all(db).await?;
let _ = users.clone();
user::Entity::load().with(post::Entity).filter(post::Column::Published.eq(true)).all(db);

// ✗ SO-30 静态堆图；每请求 connect；10MB Value 进 Set
static FEED: OnceCell<Vec<user::ModelEx>> = OnceCell::new();
let db = Database::connect(url).await?;
FEED.set(user::Entity::load().all(&db).await?).ok();
ActiveModel { json: Set(blob), ..Default::default() }.insert(&db).await?;

// ✓ 列表 PartialModel；详情只点名边；子行过滤走 load_many
let cards: Vec<UserCard> = User::find()
    .left_join(profile::Entity)
    .into_partial_model()
    .all(db)
    .await?;
let u = user::Entity::load()
    .filter_by_id(id)
    .with(profile::Entity)
    .one(db)
    .await?;
let posts = users.load_many(
    post::Entity::find().filter(post::Column::Published.eq(true)),
    db,
).await?;
// ✓ 进程级池；JSON 当 String；图不进静态
async fn ok(State(db): State<DatabaseConnection>, body: String) {
    payload::ActiveModel { json: Set(body), ..Default::default() }.insert(&db).await.ok();
}
```

**事务与一致性**

- SO-09 事务优先闭包式 `db.transaction(|txn| …)`（Err 自动回滚）；手动 `begin`/`commit` 需说明理由。
- SO-10 事务要短：事务内禁止外部 IO/长 await（占住池连接 = 池饥饿的头号来源；ASYNC 域精神）。嵌套走 `db.transaction(|tx| tx.transaction(|tx2| …))` 的 savepoint：内层回滚只退到 savepoint，外层仍在。不要自己 `SAVE TRANSACTION`。

**工程面**

- SO-11 复杂分析查询别硬掰查询构建器（SIMP-02：付不起解释成本的 ORM 体操）——2.0 的 `*_raw` 方法是正门；raw SQL 也要参数化。
- SO-12 迁移用 sea-orm-migration 版本化入库；实体由迁移后重新生成（schema-first）或 2.0 entity-first（要 `entity-registry` + `schema-sync`）。禁手改生成物不改迁移。已用 `sqlx::migrate!` / 纯 SQL 迁表、SeaORM 只生成实体是合法分工（X：[ccQpein](https://x.com/ccQpein/status/2051691030001422508)），不要为「更 SeaORM」再加一套 migrator。慢查询先 `EXPLAIN`（META-02）——ORM 不会替你建索引。`schema-sync` 幂等只 **建** 缺表/列/键，不 DROP 表/列/FK（可 DROP INDEX）；生产关该 feature，启动路径禁 `sync()`（全量发现）。`apply()` 不检查现有 schema，只给初始化。

**2.0 API**

- SO-14 `.eq()` / `.like()` / `.contains()` / `.add()` 必须 `use sea_orm::ExprTrait;`，否则一编译就丢方法。`Alias::new("col")` 对静态名已不需要，写 `Expr::col("col")`。
- SO-15 `execute` / `query_one` / `query_all` / `stream` 收 SeaQuery 语句；裸 SQL 走 `execute_raw` / `query_*_raw` / `stream_raw`。不要把 1.x 的 `Statement::from_sql_and_values` 塞进新 `execute`。`insert_many` 的 `last_insert_id` 是 `Option<Value>`，`exec_with_returning_many` 已弃用改 `exec_with_returning`。
- SO-16 1.x → 2.0 是破坏性迁移（ExprTrait、raw 改名、Postgres `serial` 默认改 `GENERATED BY DEFAULT AS IDENTITY`、SQLite 整数默认 i64）。先确认 MSRV/runtime/迁移表，不凭版本号自动升级。Diesel 是同步 ORM，不要和 SeaORM/sqlx 在同一 runtime 混用。`async-std` 迁移 crate 已弃用，换 tokio。

**ActiveValue 与嵌套保存**

- SO-17 `ActiveValue` 三态必须分清：`Set(v)` 写入 SQL；`Unchanged(v)` 来自库、UPDATE 时进 WHERE 不进 SET；`NotSet` 省略该列，让 DB `DEFAULT` / serial / identity 生效。`Set(None)` 是显式 NULL，不是默认值。新建 `ActiveModel` 默认全 `NotSet`；`Model.into_active_model()` 是 `Unchanged`。禁止 `id: Set(0)`、`created_at: Set(Utc::now())` 覆盖库默认——X 上「迁移写了 default 插入还要手填」就是这个坑（[PhyroKelstein](https://x.com/PhyroKelstein/status/1941030262324031845)）。`try_into_model` 遇 NotSet → `AttrNotSet`；要用 `default_values()` 或把必填列 `Set`。同值更新用 `set_if_not_equals` 保 `Unchanged`。2.0 `Update::one` 要 `.validate()`。
- SO-18 2.0 嵌套图用一次 `.save(db)`（[Nested ActiveModel](https://www.sea-ql.org/blog/2025-11-25-sea-orm-2.0/)）：走 FK 顺序、同一事务、按 `Set` 检测变更。要 `#[sea_orm::model]`，`compact_model` 没有这套。二次 `save` 应是 no-op（幂等）；`replace_all` 会删未列出的子行。不要手写「先 insert user 再循环 insert posts」。`cascade_delete` 按依赖倒序删；弱 BelongsTo 只把 FK 置 NULL。
- SO-19 按关系过滤父行用 `EXISTS`（相关实体条件进 `.filter`），不要 `all()` 再内存滤。`filter_by_id` / `filter_by_*` 是主键捷径。
- SO-20 旧迁移里不要用**当前** `ActiveModel` 做 seed（[discussion 1058](https://github.com/SeaQL/sea-orm/discussions/1058)）：实体加列后历史迁移编不过。seed 用当时的列清单或 raw SQL。Postgres 迁移默认原子；MySQL/SQLite **不是**，失败会半成品——在迁移内手开事务或接受分步。建表时 MySQL 才把 `.index()` 写进 `TableCreateStatement`；PG/SQLite 用 `SchemaManager::create_index()`。MySQL 索引无 `IF NOT EXISTS`。
- SO-21 `ActiveModel`/`Model` 不直接 `Serialize` 出 API（同 SX-08 / API-08）。handler 不堆 `Entity::find()`；查询复用或跨语句事务收到 repository。
- SO-22 生产路径不要把 `ModelEx` 整树当列表页 payload。列表用 SO-05 partial；详情页才 `load().with(...)`。

```rust
// ✗ SO-17 把 DB 默认盖掉；SO-18 手插子行
let user = user::ActiveModel {
    id: Set(0),
    created_at: Set(Utc::now()),
    name: Set("bob".into()),
    ..Default::default()
}
.insert(db)
.await?;
for title in titles {
    post::ActiveModel {
        user_id: Set(user.id),
        title: Set(title),
        ..Default::default()
    }
    .insert(db)
    .await?;
}

// ✓ NotSet 留给 identity/DEFAULT；2.0 嵌套一次 save
let user = user::ActiveModel::builder()
    .set_name("bob")
    .add_post(post::ActiveModel::builder().set_title("hi"))
    .save(db)
    .await?;
```

**upsert 与 JSON 入站**

- SO-23 冲突写入走 `on_conflict`（[Insert](https://www.sea-ql.org/SeaORM/docs/basic-crud/insert/)）：`OnConflict::column(Col).do_nothing()` / `.update_columns([...])`；打 PK 用 `on_conflict_do_nothing()`。0 行写入 = `DbErr::RecordNotInserted`，不是静默成功——要 Ok 走 `.try_insert()` → `TryInsertResult::Conflicted`。MySQL 是 `ON DUPLICATE KEY UPDATE pk = pk` polyfill。不要用单行 `save()` 当 upsert。
- SO-24 单行 `save()` 按 PK 状态分流（[Save](https://www.sea-ql.org/SeaORM/docs/basic-crud/save/)）：PK `NotSet` → insert，`Set`/`Unchanged` → update。这不是 SO-18 的 2.0 嵌套 `.save`。幂等/冲突走 SO-23。
- SO-25 `ActiveModel::from_json`：JSON 缺字段 → `NotSet`（2.0）；`set_from_json` **不改已有 PK**。入站 JSON 用 DTO 再转 ActiveModel，handler 不直接 Deserialize `Model`（SO-21）。Entity 上 `#[serde(rename_all)]` / `rename` 再 `from_json` 有字段错位先例（[issue 2257](https://github.com/SeaQL/sea-orm/issues/2257)，X：[FusionZhu](https://x.com/CoderFusionZhu/status/1909977622001619305)）——对不上就静默 `NotSet`/`None`。PK 用 `#[serde(skip_deserializing)]`。

```rust
// ✗ SO-23 冲突当成功；SO-24 用 save 当 upsert；SO-25 Entity JSON 直接入站
Entity::insert(model).on_conflict(on_conflict).exec(db).await?; // 0 行 → RecordNotInserted
model.save(db).await?; // PK 在就 UPDATE，撞 unique 不是 upsert
let am = ActiveModel::from_json(payload)?; // rename_all 错位 → 列变 NotSet

// ✓ try_insert 把冲突收成 Ok；DTO 字段显式 Set
let _ = Entity::insert(am)
    .on_conflict(OnConflict::column(Column::Email).update_columns([Column::Name]))
    .try_insert()
    .exec(db)
    .await?;
```

**测试**：单测用 `MockDatabase` 断言语句与返回；集成测真库且缺环境 fail-loud（TEST-07），禁静默跳过。

## 验证（PERF-01）

同机前后对比：查询计时（p50/p99）、往返次数（N+1 修复前后 SQL 条数）、`EXPLAIN` 计划变化。内存争议再加：SELECT 列数/行宽、结果行数 vs unique 父行、RSS 或分配器峰值（`load().all().with(1-N)` vs PartialModel）。「泄漏」用分配字节/heaptrack 跨请求是否单调涨，不要单看一次 RSS 台阶（SO-30）。

## 输出

按 [kernel/finding.md](../kernel/finding.md) 组织：一句话结论 → 范围行 → 正文 → 验证 → 置信度 → 下一步 → 写授权收尾。

只读调用：体检表 + 按收益排序候选（SO 编号 + 全局规则号）+ 验证方案。`--apply` 或明确“修/改/实现”时：再给实际改动与前后数据。残余只输出 RUST.md 债务候选，显式 `--record` 才写入。
