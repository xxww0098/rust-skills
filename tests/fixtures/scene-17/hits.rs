// Scene 17: Windows share_mode(0) blocks rename of a live handle.
use std::os::windows::fs::OpenOptionsExt;
let f = OpenOptions::new().read(true).share_mode(0).open(&path)?;
std::fs::rename(&path, &tmp)?;
