fn main() {
    // trap: fmt().init() defaults INFO; fmt::init() defaults ERROR without RUST_LOG
    tracing_subscriber::fmt().init();
    tracing_subscriber::fmt().json().init(); // second init + two fmt on stdout
}

#[tracing::instrument]
fn helper_add(a: i32, b: i32) -> i32 {
    a + b
}

async fn handle() {
    let span = tracing::info_span!("GET {}", "/users/1");
    let _g = span.enter();
    tokio::time::sleep(std::time::Duration::from_millis(1)).await;
}
