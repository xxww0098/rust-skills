// Scene 63: async command borrows, double invoke_handler, emit as a firehose.
#[tauri::command]
async fn parse(input: &str) -> Result<Vec<Row>, String> { unimplemented!() }

fn setup(app: App) {
    app.invoke_handler(generate_handler![parse])
        .invoke_handler(generate_handler![export]);
    app.emit("progress", pct);
}
