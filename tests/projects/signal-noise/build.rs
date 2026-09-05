fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    let _ = std::env::var("OUT_DIR").unwrap();
}
