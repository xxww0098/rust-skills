// Scene 57 fixture: axum 0.8 path params are {id}, not :id.
// Not a buildable crate — pattern source for eval-fixtures.py and LLM sessions.

fn routes() {
    Router::new()
        .route("/users/:id", get(get_user))
        .route("/*path", get(fallback));
}
