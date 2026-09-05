use std::sync::Arc;

pub fn share(value: Arc<String>) -> Arc<String> {
    value.clone()
}
