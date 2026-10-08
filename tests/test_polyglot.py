import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from slop_test.backends.openai_compat import OpenAICompatBackend
from slop_test.cli import app
from slop_test.discovery import collect_tests, discover, find_test_files
from slop_test.discovery.languages import LANGUAGES, Language
from slop_test.discovery.model import UnparsableError
from slop_test.discovery.treesitter import collect

FIXTURES = Path(__file__).parent / "fixtures" / "polyglot"

EXPECTED = {
    "c/test_cart.c": ("C", ["test_adds_an_item", "test_legacy_rounding"]),
    "cpp/cart_test.cc": (
        "C++",
        [
            "CartTest::AddsAnItem",
            "CartFixture::MigratesLegacyCarts",
            "CartTest::bool",
            "catch2 style names",
            "prod deploys on friday",
        ],
    ),
    "csharp/CartTests.cs": (
        "C#",
        [
            "CartTests::AddsAnItem",
            "CartTests::HandlesLegacyQuantities",
            "CartTests::NUnitStyle",
            "CartTests::MsTestStyle",
        ],
    ),
    "dart/cart_test.dart": ("Dart", ["Cart::adds an item", "renders the legacy badge"]),
    "elixir/cart_test.exs": (
        "Elixir",
        ["CartTest::add/2::adds an item", "CartTest::migrates legacy carts"],
    ),
    "fsharp/CartTests.fs": ("F#", ["adds an item", "cart::migrates legacy carts"]),
    "go/cart_test.go": ("Go", ["TestAddItem", "TestLegacyMigration", "Test"]),
    "haskell/CartSpec.hs": ("Haskell", ["Cart::adds an item", "Cart::migrates legacy carts"]),
    "java/CartTest.java": (
        "Java",
        [
            "CartTest::addsAnItem",
            "CartTest::handlesLegacyQuantities",
            "CartTest::WhenEmpty::hasNoItems",
        ],
    ),
    "js/cart.test.js": (
        "JavaScript",
        [
            "Cart::adds an item",
            "Cart::applies legacy discounts",
            "Cart::with %i items::totals correctly",
            "works without a describe",
            "handles %i",
            "supports template names",
        ],
    ),
    "julia/test/runtests.jl": ("Julia", ["Cart::adds an item", "Cart::migrates legacy carts"]),
    "kotlin/CartTest.kt": ("Kotlin", ["CartTest::adds an item", "CartTest::migratesLegacyCarts"]),
    "lua/cart_spec.lua": ("Lua", ["cart::adds an item"]),
    "ocaml/test_cart.ml": (
        "OCaml",
        ["Cart::add::adds an item", "Cart::legacy::migrates legacy carts"],
    ),
    "php/CartTest.php": (
        "PHP",
        [
            "CartTest::testAddsAnItem",
            "CartTest::it_migrates_legacy_carts",
            "CartTest::attributeStyle",
        ],
    ),
    "php/PestTest.php": ("PHP", ["cart::adds an item", "works at the top level"]),
    "ruby/cart_spec.rb": (
        "Ruby",
        [
            "Cart::adds an item",
            "Cart::with legacy discounts::applies them",
            "Cart::with legacy discounts::supports parentheses",
        ],
    ),
    "ruby/cart_test.rb": ("Ruby", ["CartTest::test_adds_an_item", "CartTest::rails style names"]),
    "rust/cart.rs": (
        "Rust",
        ["tests::adds_numbers", "tests::panics_on_legacy_input", "tests::fetches_prod_data"],
    ),
    "scala/CartSuite.scala": (
        "Scala",
        ["CartSuite::adds an item", "CartSpec::Cart::migrates legacy carts"],
    ),
    "swift/CartTests.swift": (
        "Swift",
        [
            "CartTests::testAddsAnItem",
            "LegacyCartTests::Migrates legacy carts",
            "LegacyCartTests::plainSwiftTesting",
        ],
    ),
    "ts/cart.spec.tsx": (
        "TypeScript",
        ["CartView::renders the total", "CartView::handles a prod outage"],
    ),
    "ts/cart.test.ts": ("TypeScript", ["pricing::rounds legacy invoices", "plain node:test"]),
    "zig/cart.zig": ("Zig", ["adds an item", "identifierStyle"]),
}


def found_in(relative):
    return {t.qualname: t for t in collect_tests(FIXTURES / relative)}


@pytest.mark.parametrize("relative", EXPECTED)
def test_finds_exactly_the_tests_in_each_language(relative):
    language, expected = EXPECTED[relative]

    tests = collect_tests(FIXTURES / relative)

    assert [t.qualname for t in tests] == expected
    assert {t.language for t in tests} == {language}


def test_every_language_has_a_fixture():
    tree_sitter_languages = {lang.name for lang in LANGUAGES if lang.grammar is not None}
    covered = {language for language, _ in EXPECTED.values()}

    assert covered == tree_sitter_languages


def test_discovery_walks_into_every_fixture():
    found = {t.file.relative_to(FIXTURES).as_posix() for t in discover(FIXTURES).tests}

    assert found == set(EXPECTED)


ADDING = "Adding an item increases the count."


@pytest.mark.parametrize(
    ("relative", "qualname", "docstring"),
    [
        ("js/cart.test.js", "Cart::adds an item", ADDING),
        ("js/cart.test.js", "works without a describe", None),
        (
            "go/cart_test.go",
            "TestAddItem",
            "TestAddItem checks that adding an item increases the count.",
        ),
        ("rust/cart.rs", "tests::adds_numbers", "Adding two numbers works."),
        ("rust/cart.rs", "tests::panics_on_legacy_input", None),
        ("csharp/CartTests.cs", "CartTests::AddsAnItem", ADDING),
        ("ruby/cart_spec.rb", "Cart::adds an item", ADDING),
        ("haskell/CartSpec.hs", "Cart::adds an item", ADDING),
        ("lua/cart_spec.lua", "cart::adds an item", ADDING),
        ("fsharp/CartTests.fs", "adds an item", ADDING),
        ("julia/test/runtests.jl", "Cart::adds an item", ADDING),
        ("c/test_cart.c", "test_adds_an_item", ADDING),
    ],
)
def test_doc_comments_become_docstrings(relative, qualname, docstring):
    assert found_in(relative)[qualname].docstring == docstring


def test_source_and_line_numbers():
    test = found_in("js/cart.test.js")["Cart::adds an item"]

    assert test.lineno == 4
    assert test.source.startswith("it('adds an item', () => {")
    assert test.source.endswith("})")
    assert found_in("rust/cart.rs")["tests::adds_numbers"].source.startswith("fn adds_numbers")


@pytest.mark.parametrize(
    ("relative", "qualname", "line"),
    [
        ("java/CartTest.java", "CartTest::addsAnItem", "    void addsAnItem() {}"),
        ("rust/cart.rs", "tests::panics_on_legacy_input", "    fn panics_on_legacy_input() {}"),
        ("csharp/CartTests.cs", "CartTests::NUnitStyle", "    public void NUnitStyle() {}"),
    ],
)
def test_line_numbers_point_at_the_name_not_the_annotation(relative, qualname, line):
    lineno = found_in(relative)[qualname].lineno

    assert (FIXTURES / relative).read_text().splitlines()[lineno - 1] == line


def test_a_file_without_tests_has_no_tests(tmp_path):
    source = tmp_path / "lib.rs"
    source.write_text("pub fn add(a: i32, b: i32) -> i32 {\n    a + b\n}\n")

    assert collect_tests(source) == []


def write(root, *names):
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")


def test_which_files_count_as_test_files(tmp_path):
    write(
        tmp_path,
        "src/cart.js",
        "src/cart.test.js",
        "src/__tests__/cart.js",
        "test/checkout.js",
        "cart.go",
        "cart_test.go",
        "src/lib.rs",
        "target/debug/build.rs",
        "lib/cart.rb",
        "spec/cart_spec.rb",
        "vendor/gems/thing_spec.rb",
        "node_modules/pkg/index.test.js",
        "README.md",
    )

    files = {p.relative_to(tmp_path).as_posix() for p in find_test_files(tmp_path)}

    assert files == {
        "src/cart.test.js",
        "src/__tests__/cart.js",
        "test/checkout.js",
        "cart_test.go",
        "src/lib.rs",
        "spec/cart_spec.rb",
    }


def test_a_test_directory_passed_directly_counts(tmp_path):
    write(tmp_path, "test/checkout.js")

    assert [p.name for p in find_test_files(tmp_path / "test")] == ["checkout.js"]


def test_files_in_unknown_languages_are_unparsable(tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("test 'everything' passes")

    assert discover(notes).unparsable == [notes]


def test_a_broken_grammar_makes_files_unparsable_instead_of_crashing():
    broken = Language(
        name="Broken",
        extensions=(".js",),
        grammar=("tree_sitter_javascript", "language"),
        tests="(this_node_type_does_not_exist) @test",
    )

    with pytest.raises(UnparsableError, match="Broken grammar unavailable"):
        collect(broken, Path("x.js"), b"test('x', () => {})")


def test_run_without_a_path_uses_tests_dir_or_falls_back_to_here(tmp_path, monkeypatch):
    (tmp_path / "cart_test.go").write_text(
        textwrap.dedent(
            """
            package cart

            import "testing"

            func TestCheckout(t *testing.T) {}
            """
        )
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    assert "TestCheckout" in runner.invoke(app, ["run", "--seed", "0"]).output

    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_cart.py").write_text("def test_python_only():\n    pass\n")
    output = runner.invoke(app, ["run", "--seed", "0"]).output

    assert "test_python_only" in output
    assert "TestCheckout" not in output


def test_the_model_is_told_the_language():
    backend = OpenAICompatBackend(base_url="", api_key="", model="")
    test = found_in("go/cart_test.go")["TestAddItem"]

    prompt = backend._conversation(test)[-1]["content"]

    assert "Language: Go" in prompt
