// Scene 11: 200MB video through a Tauri command as Vec<u8>.
#[tauri::command]
async fn read_video(p: PathBuf) -> Result<Vec<u8>, String> {
    std::fs::read(p).map_err(|e| e.to_string())
}
