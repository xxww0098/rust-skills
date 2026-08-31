# seaorm/leak — 内存「泄漏」四类分诊

目的：「内存泄漏 / RSS / 不释放 / 泄漏分诊」或代码出现 `OnceCell<Vec<ModelEx>>`、每请求 `Database::connect`、大 JSON `Set(Value)` 时加载。编号定义在 [seaorm.md](../seaorm.md)。Loader 峰值与六杠杆走 [loader.md](loader.md)；池参数走 [pool.md](pool.md)。

## 先分四类（SO-30）

不要对着 RSS 开治（[discussion 2901](https://github.com/SeaQL/sea-orm/discussions/2901) · [Connection](https://www.sea-ql.org/SeaORM/docs/install-and-config/connection/)）。官方：SeaORM 无缓存、无特殊 `Drop`；默认分配器不立刻把页还给 OS；RSS 不是单条语句的细粒度指标。

1. **分配器/碎片（不是泄漏）**：大 JSON/`Value`/`ActiveModel::insert` 后 RSS 台阶、raw SQL 却平稳。指纹（2901）：~10MB JSON，`ActiveModel` RSS 10→121MB，同内容 raw SQL ~13MB——ORM 堆分配更多，不是缓存。换 mimalloc/jemalloc 复测；JSON 列当 `String` + `jsonb`，不要把 10MB `serde_json::Value` 推进 `Set`。
2. **活图没放**：`OnceCell`/`lazy_static`/`app state` 里堆 `Vec<ModelEx>`、clone 树、无界 `.all()`（SO-28/29）。进程级该复用的是**池**，不是查询结果。
3. **连接没还**：事务跨外部 IO（SO-10）；`stream` 没消费完就丢任务；每请求 `Database::connect`（[608](https://github.com/SeaQL/sea-orm/discussions/608) 要复用池）；`Arc<Mutex<DatabaseConnection>>`（SO-01）。关停 `close().await`（sqlx 无 async Drop，最后一把 handle 丢了未必立刻拆连接）。`idle_timeout`/`max_lifetime` 回收闲连接，不是治泄漏。
4. **真泄漏**：换分配器 + 图已 Drop + 连接已还，heaptrack/dhat 仍跨请求单调涨 → 再查依赖。禁止把 2901 那种 RSS 当 SeaORM 泄漏修代码。

## 分诊顺序（不要跳）

一次语句后 RSS 上台阶、后续请求不再涨 → 桶 1。作用域结束、分配字节回落但 RSS 不还 OS → 仍桶 1。分配字节跨请求单调涨 → 桶 2（静态图）。连接数一起涨 → 桶 3。1–4 排除后再 heaptrack → 桶 4。假优化：调 `max_connections`/`idle_timeout` 当治泄漏。

```rust
// ✗ 静态堆图；每请求 connect；10MB Value 进 Set
static FEED: OnceCell<Vec<user::ModelEx>> = OnceCell::new();
let db = Database::connect(url).await?;
FEED.set(user::Entity::load().all(&db).await?).ok();
ActiveModel { json: Set(blob), ..Default::default() }.insert(&db).await?;

// ✓ 进程级池；JSON 当 String；图不进静态
async fn ok(State(db): State<DatabaseConnection>, body: String) {
    payload::ActiveModel { json: Set(body), ..Default::default() }.insert(&db).await.ok();
}
```
