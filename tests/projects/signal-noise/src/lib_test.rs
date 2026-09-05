pub fn not_prod() {
    let _ = Result::<u8, ()>::Err(()).unwrap();
    println!("lib_test");
}
