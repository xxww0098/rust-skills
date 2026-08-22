// Scene 64: plugin order, sidecar name, v1 leftovers.
Builder::default()
    .plugin(tauri_plugin_log::init())
    .plugin(tauri_plugin_single_instance::init(..));
// tauri.conf.json: "externalBin": ["binaries/ffmpeg"], "tauri": { "allowlist": {..} }
window.emit_all("done", ());
