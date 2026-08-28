fn first_word(s: &String) -> String {
    s.clone().split_whitespace().next().unwrap().to_string()
}

fn main() {
    println!("{}", first_word(&"a b".to_string()));
}
