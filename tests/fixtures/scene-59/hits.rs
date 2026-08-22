// Scene 59 fixture: axum 0.8 custom extractors kept the 0.7 shape.
// Not a buildable crate — pattern source for eval-fixtures.py and LLM sessions.
// Cargo.toml: axum = "0.8", async-trait = "0.1"

#[async_trait]
impl<S: Send + Sync> FromRequestParts<S> for ApiKey {
    type Rejection = StatusCode;
    async fn from_request_parts(parts: &mut Parts, _state: &S) -> Result<Self, Self::Rejection> {
        let raw = parts.headers.get("x-api-key").ok_or(StatusCode::UNAUTHORIZED)?;
        Ok(ApiKey(raw.to_str().unwrap().to_owned()))
    }
}

// same concrete type also implements FromRequest, and reads the body by hand
#[async_trait]
impl<S: Send + Sync> FromRequest<S> for ApiKey {
    type Rejection = StatusCode;
    async fn from_request(req: Request, _state: &S) -> Result<Self, Self::Rejection> {
        let body = to_bytes(req.into_body(), usize::MAX).await.unwrap();
        Ok(ApiKey(String::from_utf8(body.to_vec()).unwrap()))
    }
}

// 0.7 habit: "missing or broken -> None"
async fn show(key: Option<ApiKey>, id: Option<Path<u32>>) -> StatusCode {
    let _ = (key, id);
    StatusCode::OK
}
