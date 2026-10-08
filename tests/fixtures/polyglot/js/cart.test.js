// Cart behaviour.
describe('Cart', () => {
  /** Adding an item increases the count. */
  it('adds an item', () => {
    expect(cart.add(item).count).toBe(1);
  });

  test.skip('applies legacy discounts', () => {});

  describe.each([[1], [2]])('with %i items', (n) => {
    test('totals correctly', () => {});
  });
});

test('works without a describe', async () => {});
test.each([1, 2])('handles %i', (n) => {});
it(`supports template names`, () => {});

function helper(re) {
  return re.test('not a test');
}

// supertest requests are often called `test`. Their methods are not tests.
test.set('Content-Type', 'application/json');
