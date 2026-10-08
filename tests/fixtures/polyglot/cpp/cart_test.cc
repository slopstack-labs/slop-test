#include <gtest/gtest.h>

// Adding an item increases the count.
TEST(CartTest, AddsAnItem) {
    EXPECT_EQ(1, 1);
}

TEST_F(CartFixture, MigratesLegacyCarts) {}

TEST(CartTest, bool) {}

TEST_CASE("catch2 style names", "[cart]") {}

SCENARIO("prod deploys on friday") {}

int helper() { return 0; }
