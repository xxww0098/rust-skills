/// Example in docs: value.unwrap()
pub fn live_unwrap(value: Result<u8, ()>) -> u8 {
    // reviewers mention .unwrap() here
    /* block also says println!("nope") and value.expect("x") */
    let _hint = "call .unwrap() in tests only";
    let _raw = r#"dbg!(value)"#;
    value.unwrap()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hidden() {
        let _ = live_unwrap(Ok(1)).clone();
        println!("test noise");
        let _ = Result::<u8, ()>::Err(()).unwrap();
    }
}

pub fn share(value: std::sync::Arc<String>) -> std::sync::Arc<String> {
    value.clone()
}
