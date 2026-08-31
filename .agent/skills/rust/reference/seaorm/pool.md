# seaorm/pool — 连接、事务、迁移、schema-sync

目的：「连接池 / ConnectOptions / 事务占连接 / schema-sync / 迁移原子性」或代码出现 `Arc<DatabaseConnection>` / 每请求 `connect` / 启动 `sync()` 时加载。编号定义在 [seaorm.md](../seaorm.md)。活图 / RSS 分诊走 [leak.md](leak.md)；历史迁移 seed 的 ActiveModel 坑与本文件 SO-20 一起看。

## 连接即池（SO-01/02/03）

`DatabaseConnection` 内部就是 `sqlx::Pool`，廉价 clone——禁止 `Arc`/`Arc<Mutex<>>` 包裹（同 AX-02）。`ConnectOptions` 显式调优并注释依据：`max_connections` 按 DB 实测，不是越大越好；再加 `min_connections`、`acquire_timeout`/`connect_timeout`、`idle_timeout`/`max_lifetime`。缺省裸连 = 未做容量设计。启动 `db.ping()`；关停 `db.close().await`（sqlx 无 async Drop，最后一把 handle 丢了未必立刻拆连接）。SQLite URL 钉 `mode=rwc` 或 `mode=ro`，不要默认可写内存库当生产。生产热路径 `sqlx_logging(false)`；慢查询观测交给 DB 侧/OBS 管道。进程级该复用的是**池**，不是查询结果。每请求 `Database::connect` 是连接没还（SO-30 桶 3），不是容量调优。

## 事务要短（SO-09/10）

优先闭包式 `db.transaction(|txn| …)`（Err 自动回滚）；手动 `begin`/`commit` 需说明理由。事务内禁止外部 IO/长 await（占住池连接 = 池饥饿的头号来源）。嵌套走 `db.transaction(|tx| tx.transaction(|tx2| …))` 的 savepoint：内层回滚只退到 savepoint，外层仍在。不要自己 `SAVE TRANSACTION`。`idle_timeout`/`max_lifetime` 回收闲连接，不是治泄漏，也不是内存策略。

## 迁移与 schema-sync（SO-12/20）

用 sea-orm-migration 版本化入库；实体由迁移后重新生成（schema-first）或 2.0 entity-first（要 `entity-registry` + `schema-sync`）。禁手改生成物不改迁移。已用 `sqlx::migrate!` / 纯 SQL 迁表、SeaORM 只生成实体是合法分工，不要为「更 SeaORM」再加一套 migrator。慢查询先 `EXPLAIN`（META-02）——ORM 不会替你建索引。

`schema-sync` 幂等只 **建** 缺表/列/键，不 DROP 表/列/FK（可 DROP INDEX）；生产关该 feature，启动路径禁 `sync()`（全量发现）。`apply()` 不检查现有 schema，只给初始化。

旧迁移里不要用**当前** `ActiveModel` 做 seed（discussion 1058）：实体加列后历史迁移编不过。seed 用当时的列清单或 raw SQL。Postgres 迁移默认原子；MySQL/SQLite **不是**，失败会半成品——在迁移内手开事务或接受分步。建表时 MySQL 才把 `.index()` 写进 `TableCreateStatement`；PG/SQLite 用 `SchemaManager::create_index()`。MySQL 索引无 `IF NOT EXISTS`。
