// Scene 55 fixture: child env must not mutate the parent; large output must not wait_with_output.
// Not a buildable crate — pattern source for eval-fixtures.py and LLM sessions.

use std::process::Command;

pub async fn run_ffmpeg(p: String, file: &str) {
    std::env::set_var("FFMPEG_PATH", &p);
    let _out = Command::new("ffmpeg").arg(file).output();
}
