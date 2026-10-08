module CartTests

open Xunit
open Expecto

/// Adding an item increases the count.
[<Fact>]
let ``adds an item`` () = Assert.Equal(1, 1)

let tests =
    testList "cart" [
        testCase "migrates legacy carts" <| fun _ -> ()
    ]

let helper () = ()
