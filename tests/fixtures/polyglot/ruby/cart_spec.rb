# Cart behaviour.
RSpec.describe Cart do
  # Adding an item increases the count.
  it "adds an item" do
    expect(cart.add(item).count).to eq(1)
  end

  context "with legacy discounts" do
    specify "applies them" do
    end

    it("supports parentheses") { }
  end

  def helper; end
end
