// anti-patterns for /seaorm Entity Loader strategy
async fn list_users(db: &DatabaseConnection) -> Result<Vec<user::ModelEx>, DbErr> {
    User::find().find_with_related(Post).paginate(db, 10);
    let users = user::Entity::load()
        .with((profile::Entity, (post::Entity, comment::Entity)))
        .all(db)
        .await?;
    for u in &users {
        if u.profile.is_none() {
            // Unloaded, not missing
        }
    }
    Ok(users)
}
