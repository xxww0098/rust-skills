
async fn create(body: String) -> String {
    let v: serde_json::Value = serde_json::from_str(&body).unwrap();
    let id = v["id"].as_str().unwrap();
    #[derive(serde::Serialize)]
    struct Out { password: String }
    serde_json::to_string(&Out { password: id.into() }).unwrap()
}

#[derive(serde::Deserialize)]
#[serde(untagged)]
enum Ev { A(String), B(u64) }
