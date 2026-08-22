// Scene 13: rayon on a tokio worker.
async fn handle(data: Vec<u64>) -> Vec<u64> {
    data.par_iter().map(heavy).collect()
}
