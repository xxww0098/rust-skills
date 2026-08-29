// anti-patterns for /seaorm ActiveValue + nested save
use sea_orm::ActiveValue::Set;
use chrono::Utc;

async fn create_user(db: &DatabaseConnection, titles: Vec<String>) -> Result<(), DbErr> {
    let user = user::ActiveModel {
        id: Set(0),
        created_at: Set(Utc::now()),
        name: Set("bob".into()),
        email: Set(None),
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
    Ok(())
}
