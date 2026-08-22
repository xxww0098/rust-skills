// Scene 10: axum state accidents.
async fn proxy() -> String {
    reqwest::Client::new().get(URL).send().await.unwrap().text().await.unwrap()
}
struct AppState {
    pool: Arc<Mutex<sqlx::PgPool>>,
}
