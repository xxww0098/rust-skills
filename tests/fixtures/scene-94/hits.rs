// anti-patterns for /seaorm leak triage
use once_cell::sync::OnceCell;

static FEED: OnceCell<Vec<user::ModelEx>> = OnceCell::new();

async fn handle(url: &str, blob: serde_json::Value) -> Result<(), DbErr> {
    let db = Database::connect(url).await?;
    let rows = user::Entity::load().with(post::Entity).all(&db).await?;
    let _ = FEED.set(rows);
    let am = payload::ActiveModel {
        json: Set(blob),
        ..Default::default()
    };
    am.insert(&db).await?;
    Ok(())
}
