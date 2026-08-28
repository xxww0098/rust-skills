// anti-pattern: Spring-style global exception + repo that speaks HTTP
.layer(HandleErrorLayer::new(|_: BoxError| async { StatusCode::INTERNAL_SERVER_ERROR }))
.layer(from_fn(|req, next| async move {
    let mut res = next.run(req).await;
    let _ = res.body_mut();
    res
}))

pub async fn find_user(db: &PgPool, id: i64) -> Result<User, AppError> {
    sqlx::query_as!(User, "select 1", id).fetch_optional(db).await?.ok_or(AppError::NotFound)
}
