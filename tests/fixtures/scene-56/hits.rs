// Scene 56 fixture: unsafe fn still needs inner unsafe {}; ! must not flow into unsafe.
// Not a buildable crate — pattern source for eval-fixtures.py and LLM sessions.

unsafe fn get(x: &[u8], i: usize) -> u8 {
    *x.get_unchecked(i)
}

fn outer<T>(x: T) -> Result<T, ()> {
    fn f<T: Default>() -> Result<T, ()> {
        Ok(T::default())
    }
    f()?;
    Ok(x)
}
