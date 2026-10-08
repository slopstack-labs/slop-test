namespace Cart.Tests;

public class CartTests
{
    /// <summary>Adding an item increases the count.</summary>
    [Fact]
    public void AddsAnItem() {}

    [Theory]
    [InlineData(1)]
    public void HandlesLegacyQuantities(int n) {}

    [Test, Category("prod")]
    public void NUnitStyle() {}

    [TestMethod]
    public async Task MsTestStyle() {}

    public void Helper() {}
}
