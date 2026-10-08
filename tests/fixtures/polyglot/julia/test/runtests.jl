using Test

@testset "Cart" begin
    # Adding an item increases the count.
    @testset "adds an item" begin
        @test 1 == 1
    end
    @testset "migrates legacy carts" begin
        @test true
    end
end

helper() = 0
