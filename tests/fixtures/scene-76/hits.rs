pub fn nth(items: &[u8], idx: usize) -> u8 {
    items[idx]
}

pub fn ratio(a: u32, b: u32) -> u32 {
    a / b
}

pub fn sum_idx(xs: &[i32]) -> i32 {
    let mut s = 0;
    for i in 0..xs.len() {
        s += xs[i];
    }
    s
}
