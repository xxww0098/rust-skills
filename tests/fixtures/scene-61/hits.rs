// Scene 61: JWT literal secret + Validation::default + field.bytes() upload.
const SECRET: &str = "devkey";
fn auth(t: &str) {
    decode::<Claims>(t, &DecodingKey::from_secret(SECRET.as_bytes()), &Validation::default());
}
async fn upload(mut mp: Multipart) {
    let field = mp.next_field().await.unwrap().unwrap();
    let name = field.file_name().unwrap().to_string();
    let data = field.bytes().await.unwrap();
    std::fs::write(name, data).unwrap();
}
