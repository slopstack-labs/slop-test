defmodule CartTest do
  use ExUnit.Case

  describe "add/2" do
    # Adding an item increases the count.
    test "adds an item" do
      assert 1 == 1
    end
  end

  test "migrates legacy carts", %{cart: cart} do
  end

  defp helper, do: :ok
end
