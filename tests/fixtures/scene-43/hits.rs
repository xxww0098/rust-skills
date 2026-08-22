// Scene 43: sqlx string-concat + FromRow+Serialize leak + f64 money.
#[derive(sqlx::FromRow, serde::Serialize)]
struct UserRow {
    id: i64,
    email: String,
    password_hash: String,
    balance: f64,
}

async fn list(ids: &[i64], pool: &sqlx::PgPool) -> Vec<UserRow> {
    let mut out = Vec::new();
    for id in ids {
        let q = format!("SELECT * FROM users WHERE id = '{}'", id);
        out.push(sqlx::query_as(&q).fetch_one(pool).await.unwrap());
    }
    out
}
