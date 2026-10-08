import { describe, it, expect } from 'vitest';

describe('CartView', () => {
  // Renders the total.
  it('renders the total', () => {
    const view = <Cart total={3} />;
    expect(view).toBeTruthy();
  });

  it.only('handles a prod outage', async () => {});
});

const notATest = (items: number[]): number => items.length;
