// Scene 15: String storm + untagged enum.
#[derive(Deserialize)]
#[serde(untagged)]
enum Event {
    A { ty: String, payload: String },
    B { ty: String, payload: String },
    C { ty: String, payload: String },
    D { ty: String, payload: String },
}
