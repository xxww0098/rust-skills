# seaorm/query — N+1、列裁剪、流式与分页

目的：循环里 `find_related`、列表页慢、宽表 SELECT *、`.all()` 收大 `Vec`、深 offset 分页、`ExprTrait` 丢方法、1.x `execute` 塞裸 SQL 时加载。编号定义在 [seaorm.md](../seaorm.md)。详情整棵 `ModelEx` 走 [loader.md](loader.md)；`ActiveModel` 写入走 [active.md](active.md)。

## N+1（SO-04）

循环里 `find_related` = 1+N 条 SQL。批量用 `load_many` / `load_many_to_many`（可带过滤器）。仅两实体、小结果才 `find_with_related`；join 会复制「一」侧。≥3 实体只能 loader。2.0 详情图走 SO-13，不要两条都写。

```rust
// ✗ 1 + N 条 SQL
for cake in Cake::find().all(db).await? {
    let fruits = cake.find_related(Fruit).all(db).await?;
}

// ✓ 2 条 SQL，内存合并；可带过滤
let cakes = Cake::find().all(db).await?;
let fruits = cakes.load_many(Fruit, db).await?;
```

按子条件滤父行走 EXISTS（SO-19），不要先 `all()` 再内存滤。已有 `Vec<Model>` 再过滤相关行走 `load_many(Entity::find().filter(..), db)`，不要为此改走 `Entity::load().with`。

## 列、流、页（SO-05/06/07）

宽表禁默认全列：`DerivePartialModel` / `into_partial_model`。跨表投影用 `#[sea_orm(nested)]`，不要 join 完再丢全实体。大结果 `.stream()`，不 `.all()` 收全量 `Vec`。深分页 `cursor_by`，不用大 offset 的 `paginate`。`Entity::load().paginate` 先切根再按页 load 关系——禁止在 1-N JOIN 结果上 paginate（按子行切片）。

## 构建器与 2.0 API（SO-08/11/14/15/16）

批量写入 `insert_many` 按 DB 参数上限分块；`exec_with_returning()` **仅 PG/SQLite**。空迭代返回空/`None`，不要 `on_empty_do_nothing`。复杂分析走 `*_raw`，仍要参数化。`.eq()` / `.like()` / `.contains()` / `.add()` 必须 `use sea_orm::ExprTrait;`。裸 SQL 走 `execute_raw` / `query_*_raw` / `stream_raw`，不要把 1.x 的 `Statement::from_sql_and_values` 塞进新 `execute`。1.x → 2.0 是破坏性迁移，不凭版本号自动升级。
