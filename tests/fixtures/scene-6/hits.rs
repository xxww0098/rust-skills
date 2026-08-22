// Scene 6: review must see untracked tests/common.rs and undocumented pub API.
// Not a buildable crate — pattern source for eval-fixtures.py.

// tests/common.rs  (forbidden layout, TEST-03)
pub fn assert_ok<T, E: std::fmt::Debug>(r: Result<T, E>) -> T {
    r.unwrap()
}

// src/lib.rs
pub fn load_user(id: u64) -> Result<String, std::io::Error> {
    std::fs::read_to_string(format!("users/{id}"))
}
