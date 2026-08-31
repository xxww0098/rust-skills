# seaorm/loader — Entity Loader 策略与内存

目的：「Entity Loader / ModelEx / Unloaded / JOIN 1-N / Loader 内存 / 切边 / 切根」或代码出现 `Entity::load().with` / `find_with_related` / `HasOne` 时加载。编号定义在 [seaorm.md](../seaorm.md)。列表 N+1 / 列裁剪走 [query.md](query.md)；RSS 当泄漏走 [leak.md](leak.md)。

## 混合策略（SO-13/26/27）

生成物概念上就是 `find_also`（1-1）+ `LoaderTrait::load_many`（1-N），不是新引擎。

- **1-1**：JOIN，最多三表一条 SQL。1-1 不爆炸行数，所以才 JOIN。
- **1-N / M-N**：data loader，`WHERE fk IN (..)`；M-N 连 junction 仍一条。JOIN 1-N 会笛卡尔复制父行。
- **嵌套**：收齐上一跳 ID 再发一条。`user JOIN profile` + `post WHERE user_id IN` + `comment WHERE post_id IN` = 3 条，不是 N+1。
- `.with(Rel)` = 根上的兄弟关系；`.with((Child, Grand))` = 沿 Child 再下一跳。要 `#[sea_orm::model]` 或 `#[sea_orm::compact_model]`；1.x compact 没有 Loader。

三条读路径按形状选，不要叠用（SO-26）：列表/API → PartialModel（SO-05）；详情整棵 `ModelEx` → `Entity::load().with`；已有 `Vec<Model>` 再过滤 → `load_many(find().filter, db)`。列表页 `load().with(posts)` = 过取（SO-22）。

`HasOne`/`HasMany` 是三态不是 `Option`（SO-27）。`Unloaded` = 没 `.with()`；`NotFound` = 加载了但没有行。钻石两 FK 指向同一表：`.with(Relation::Manager)` 不是两次 `.with(Worker)`（#3030）。深层链式 1-1 不要指望 `.with((b, (c, (d, e))))`（discussion 2840）——逐步 load 或 PartialModel join。自引用走 `load_self` / `load_self_many`。

## 内存峰值（SO-28）

峰值按**唯一行**计（官方「each model is transferred only once」），不按 JOIN 复制计。

- JOIN 1-N / `find_with_related`：线上父行 × 子行；解码后再去重。峰值 ≈ 复制后的宽行。
- data loader：峰值 ≈ unique(父) + unique(子) + `IN` 的 ID 列表；`load_many` 先给出 `Vec<Vec<T>>` 再 zip 进 `HasMany`，短时间双持有。
- 1-1 JOIN：行数 = 父行，行宽 = 最多三表全列；`HasOne::Loaded(Box<ModelEx>)` 每条 1-1 一次堆分配（递归类型 + 压 enum）。
- 「preventing over-fetching」= 不 `.with()` 的关系不取、1-N 不 JOIN 复制父行。**不是列裁剪**：`load()` 仍 SELECT 被加载实体的全列成 `ModelEx`。列表/窄 DTO 走 PartialModel。
- `load().all()` 整图物化（SO-06）；切根用 `load().paginate`（SO-07）。不要 `clone` `ModelEx` 树再 Serialize。无界 `.all().with(1-N)` 的子行和 `IN` 列表才是 RSS 主项，Loader 不会自动分块。

## 六杠杆（SO-29）

不要先调池。顺序：

1. **换路径**：列表/卡片 → PartialModel。详情才 `load().with`。这是最大一刀。
2. **切边**：只 `.with()` 响应真正用到的关系。`.with((post, comment))` 会把该页所有 post 的全部 comment 拉齐。
3. **切根**：`filter` 打在**根**上；`load().paginate` / `cursor_by` 切根。禁止无界 `.all()`，禁止 `all()` 再内存 skip。
4. **切子行**：`Entity::load().with(E).filter(child::Column)` 对 has_many **无效**（缺 FROM，[discussion 2850](https://github.com/SeaQL/sea-orm/discussions/2850)）。子行过滤走 `load_many(Entity::find().filter(..), db)`。按子条件滤父行走 EXISTS（SO-19）。
5. **切列**：Loader 没有 `select_only`。要窄列就离开 `load()`。1-1 JOIN 仍是相关表全列。
6. **切寿命**：分页循环丢掉上一页；映射 DTO 后放掉 `ModelEx`；禁 `clone` 树。`load()` 概念实现是 `all` + `load_many`，不要指望它 `stream` 整图。

假优化：JOIN 1-N 省往返、给 Loader 加更多 `.with()` 当投影、调 `max_connections` 当内存策略。

```rust
// ✗ JOIN 1-N 再 paginate；Unloaded 当 None；深层 1-1 塞进一层 tuple
User::find().find_with_related(Post).paginate(db, 10);
let u = user::Entity::load().one(db).await?.unwrap();
if u.profile.is_none() { /* Unloaded，不是没 profile */ }
user::Entity::load().with((b::Entity, (c::Entity, d::Entity))).all(db);

// ✗ 列表整图 + clone 树；用子列 filter 当切子行
let users = user::Entity::load().with(post::Entity).all(db).await?;
let _ = users.clone();
user::Entity::load().with(post::Entity).filter(post::Column::Published.eq(true)).all(db);

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
```
