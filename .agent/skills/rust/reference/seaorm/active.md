# seaorm/active — ActiveValue、嵌套 save、upsert、JSON 入站

目的：「ActiveModel / NotSet / 嵌套保存 / upsert / on_conflict / from_json」或代码出现 `Set(0)` / `Set(None)` / 手插子行 / `save` 当冲突写入时加载。编号定义在 [seaorm.md](../seaorm.md)。读图走 [loader.md](loader.md)；迁移 seed / schema-sync 走 [pool.md](pool.md)。

## ActiveValue 三态（SO-17）

`Set(v)` 写入 SQL；`Unchanged(v)` 来自库、UPDATE 时进 WHERE 不进 SET；`NotSet` 省略该列，让 DB `DEFAULT` / serial / identity 生效。`Set(None)` 是显式 NULL，不是默认值。新建 `ActiveModel` 默认全 `NotSet`；`Model.into_active_model()` 是 `Unchanged`。禁止 `id: Set(0)`、`created_at: Set(Utc::now())` 覆盖库默认。`try_into_model` 遇 NotSet → `AttrNotSet`；要用 `default_values()` 或把必填列 `Set`。同值更新用 `set_if_not_equals` 保 `Unchanged`。2.0 `Update::one` 要 `.validate()`。

## 嵌套保存（SO-18）

2.0 嵌套图用一次 `.save(db)`：走 FK 顺序、同一事务、按 `Set` 检测变更。要 `#[sea_orm::model]`，`compact_model` 没有这套。二次 `save` 应是 no-op（幂等）；`replace_all` 会删未列出的子行。不要手写「先 insert user 再循环 insert posts」。`cascade_delete` 按依赖倒序删；弱 BelongsTo 只把 FK 置 NULL。这不是 SO-24 的单行 `save()`。

```rust
// ✗ 把 DB 默认盖掉；手插子行
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

## upsert 与 JSON（SO-23/24/25）

冲突写入走 `on_conflict`。0 行写入 = `DbErr::RecordNotInserted`，不是静默成功——要 Ok 走 `.try_insert()` → `TryInsertResult::Conflicted`。MySQL 是 `ON DUPLICATE KEY UPDATE pk = pk` polyfill。不要用单行 `save()` 当 upsert。

单行 `save()` 按 PK 状态分流：PK `NotSet` → insert，`Set`/`Unchanged` → update。幂等/冲突走 `on_conflict`。

`ActiveModel::from_json`：JSON 缺字段 → `NotSet`（2.0）；`set_from_json` **不改已有 PK**。入站 JSON 用 DTO 再转 ActiveModel，handler 不直接 Deserialize `Model`（SO-21）。Entity 上 `#[serde(rename_all)]` 再 `from_json` 有字段错位先例（issue 2257）——对不上就静默 `NotSet`/`None`。PK 用 `#[serde(skip_deserializing)]`。

```rust
// ✗ 冲突当成功；用 save 当 upsert；Entity JSON 直接入站
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
