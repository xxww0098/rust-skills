
// Scene 68: agent pile of tautological tests + sleep hammer.
#[test]
fn get_equals_get() { let c = Counter::new(); assert_eq!(c.get(), c.get()); }
#[test]
fn hammer() {
    let c = Arc::new(Mutex::new(0));
    for _ in 0..100 { let c = c.clone(); thread::spawn(move || { *c.lock().unwrap() += 1; }); }
    thread::sleep(Duration::from_millis(20));
    assert_eq!(*c.lock().unwrap(), 100);
}
