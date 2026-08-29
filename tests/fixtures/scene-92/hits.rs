// anti-patterns for /seaorm Entity Loader memory
async fn list_feed(db: &DatabaseConnection) -> Result<Vec<user::ModelEx>, DbErr> {
    let users = user::Entity::load()
        .with(post::Entity)
        .with(comment::Entity)
        .all(db)
        .await?;
    let _ = users.clone();
    let _dup = Cake::find().find_with_related(Fruit).all(db).await?;
    Ok(users)
}
