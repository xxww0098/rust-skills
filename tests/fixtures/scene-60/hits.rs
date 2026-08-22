// Scene 60: with_state inside a child factory + layers before routes.
fn users(state: AppState) -> Router {
    Router::new().route("/", get(list)).with_state(state)
}
fn app(state: AppState) -> Router {
    Router::new()
        .layer(ServiceBuilder::new().layer(TraceLayer::new_for_http()).layer(TimeoutLayer::new(Duration::from_secs(5))))
        .route("/healthz", get(health))
        .route("/admin", get(admin))
        .layer(from_fn(require_user))
        .merge(users(state))
}
