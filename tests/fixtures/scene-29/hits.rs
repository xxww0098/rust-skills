// Scene 29: distill a single-impl Parser trait + builder.
pub trait Parser<T> {
    fn parse(&self, input: &str) -> T;
}
pub struct ParserBuilder;
impl ParserBuilder {
    pub fn new() -> Self { Self }
    pub fn build(self) -> JsonParser { JsonParser }
}
pub struct JsonParser;
impl Parser<Value> for JsonParser {
    fn parse(&self, input: &str) -> Value { unimplemented!() }
}
