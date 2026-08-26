// FILE_LINES: this module was 980 lines; this PR adds ~130 lines of tenant special cases.
// (fixture is short; the contract asserts the comment + spaghetti, not a 1k-line dump.)

pub struct Request {
    pub tenant: String,
    pub path: String,
    pub skip_auth: bool,
}

pub fn handle(req: Request) -> &'static str {
    if req.tenant == "acme" && req.path.starts_with("/legacy") {
        return "legacy-acme";
    }
    if req.skip_auth {
        return "skip-auth";
    }
    core(req)
}

fn core(_req: Request) -> &'static str {
    "ok"
}

fn identity_wrap(user: String) -> String {
    user
}

pub fn count_users(users: &[String]) -> usize {
    identity_wrap(users.len().to_string()).parse().unwrap_or(0)
}
