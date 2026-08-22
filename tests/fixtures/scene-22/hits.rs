// Scene 22: 2024 static mut — the binding is legal, creating &mut is not.
static mut COUNT: u64 = 0;
pub fn bump() {
    unsafe { let r = &mut COUNT; *r += 1; }
}
