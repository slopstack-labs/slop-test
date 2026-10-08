pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Adding two numbers works.
    #[test]
    fn adds_numbers() {
        assert_eq!(add(1, 2), 3);
    }

    #[test]
    #[should_panic]
    fn panics_on_legacy_input() {}

    #[tokio::test]
    async fn fetches_prod_data() {}

    #[inline]
    fn helper() {}
}
