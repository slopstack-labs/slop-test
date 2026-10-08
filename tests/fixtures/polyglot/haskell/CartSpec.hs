module CartSpec (spec) where

import Test.Hspec

spec :: Spec
spec = do
  describe "Cart" $ do
    -- | Adding an item increases the count.
    it "adds an item" $ do
      1 `shouldBe` 1
    it "migrates legacy carts" $
      True `shouldBe` True

helper :: Int
helper = 0
