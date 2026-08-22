
// Scene 70: library inits subscriber; drops WorkerGuard; dynamic span name; test uses init().
pub fn boot() {
    tracing_subscriber::fmt().init();
    let _ = tracing_appender::non_blocking(std::io::stdout());
    let _span = tracing::info_span!("GET {}", req.uri());
}
#[test]
fn t() { tracing_subscriber::fmt().init(); }
