import XCTest
import Testing

final class CartTests: XCTestCase {
    /// Adding an item increases the count.
    func testAddsAnItem() {}

    func helper() {}
}

@Suite struct LegacyCartTests {
    @Test("Migrates legacy carts") func migrates() {}

    @Test func plainSwiftTesting() async throws {}
}

func testNotInATestCase() {}
