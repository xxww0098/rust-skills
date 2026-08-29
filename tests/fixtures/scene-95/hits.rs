// anti-patterns for /bench high-level profiling (hotpath layers)
async fn dashboard(db: &Db, client: &Client, lock: &RwLock<State>) -> Result<Feed, Error> {
    let posts = Post::all(db).await?;
    for p in &posts {
        let _ = comments(db, p.id).await?;
    }
    let users = client.get("https://a.example/users").send().await?;
    let ads = client.get("https://a.example/ads").send().await?;
    let mut g = lock.write().await;
    let body = client.get("https://a.example/quote").send().await?;
    g.quote = body.text().await?;
    let _ = cargo_flamegraph_first();
    Ok(Feed { posts, users, ads })
}

fn cargo_flamegraph_first() {}
