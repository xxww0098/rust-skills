// Scene 54 fixture: 2024 unsafe syntax is not "already sound".
// Not a buildable crate — pattern source for eval-fixtures.py and LLM sessions.

extern "C" {
    fn strlen(p: *const i8) -> usize;
}

#[no_mangle]
pub extern "C" fn plugin_init() {}

pub fn spawn_tool() {
    // Unix multithreaded: wrapping set_var in unsafe does not make it sound.
    unsafe {
        std::env::set_var("KEY", "v");
    }
    let _ = std::process::Command::new("tool").status();
}
