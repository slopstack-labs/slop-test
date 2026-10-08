package cart;

import org.junit.jupiter.api.Test;

class CartTest {
    /** Adding an item increases the count. */
    @Test
    void addsAnItem() {}

    @ParameterizedTest
    @ValueSource(ints = {1, 2})
    void handlesLegacyQuantities(int n) {}

    @Nested
    class WhenEmpty {
        @Test
        void hasNoItems() {}
    }

    void helper() {}
}
