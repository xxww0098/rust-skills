// anti-patterns for /seaorm upsert + from_json + schema-sync
use sea_orm::{ActiveModelTrait, EntityTrait, OnConflict};

async fn boot(db: &DatabaseConnection, payload: serde_json::Value) -> Result<(), DbErr> {
    db.get_schema_registry("my_crate::entity::*").sync(db).await?;

    let model = fruit::ActiveModel::from_json(payload)?;
    model.save(db).await?;

    Entity::insert(model)
        .on_conflict(OnConflict::column(Column::Id).do_nothing())
        .exec(db)
        .await?;
    Ok(())
}
