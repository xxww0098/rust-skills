// Scene 65: clap Option + default_value_t, exit in a library crate.
pub fn die() { std::process::exit(1); }

#[derive(Parser)]
struct Cli {
    #[arg(default_value_t = 8080)]
    port: Option<u16>,
}
