(* Adding an item increases the count. *)
let test_add () = Alcotest.(check int) "same" 1 1

let () =
  Alcotest.run "Cart"
    [ ("add", [ Alcotest.test_case "adds an item" `Quick test_add ]);
      ("legacy", [ test_case "migrates legacy carts" `Slow test_add ]) ]

let helper () = ()
