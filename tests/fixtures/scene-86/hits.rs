// anti-patterns for /name
fn get_name(user: &User) -> &str {
    &user.name
}

fn as_owned(s: &str) -> String {
    s.to_owned()
}

fn row_to_user(row: Row) -> User {
    User { id: row.id }
}

fn user_save(user: &User) {
    let _ = user;
}

fn check_empty(xs: &[u8]) -> bool {
    xs.is_empty()
}
