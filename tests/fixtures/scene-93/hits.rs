// anti-patterns for /seaorm Entity Loader memory optimize
async fn feed(db: &DatabaseConnection) -> Result<Vec<user::ModelEx>, DbErr> {
    user::Entity::load()
        .with(post::Entity)
        .filter(post::Column::Published.eq(true))
        .all(db)
        .await
}
