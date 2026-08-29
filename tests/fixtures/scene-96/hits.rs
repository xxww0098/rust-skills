// anti-patterns for /bench hotpath modes + alloc
#[hotpath::main]
#[tokio::main]
async fn main() {}

#[global_allocator]
static G: tikv_jemallocator::Jemalloc = tikv_jemallocator::Jemalloc;

// HOTPATH_ALLOC_CUMULATIVE=true on recursive fn — counts twice
fn rec(n: u32) {
    if n > 0 {
        rec(n - 1);
    }
}
