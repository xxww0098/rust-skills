
// Scene 67: LOCALAPPDATA vs app_data_dir, blocking rfd in async command, no Reopen.
fn control_root() -> PathBuf {
    PathBuf::from(std::env::var_os("LOCALAPPDATA").unwrap())
}
#[tauri::command]
async fn pick() {
    let _ = rfd::FileDialog::new().pick_file();
}
fn listen() { std::net::TcpListener::bind("127.0.0.1:17892").unwrap(); }
