// Scene 66: two global loggers + println interpolation + instrumented secrets.
fn main() {
    tracing_subscriber::fmt().init();
    env_logger::init();
}

#[instrument]
async fn login(Json(body): Json<Login>) {
    println!("user {} fetched", body.id);
}
