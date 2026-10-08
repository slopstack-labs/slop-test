"""Every language slop-test can feel, and how to find the tests in it.

Python is read with `ast`. Everything else is parsed with tree-sitter, using two queries:

- `tests` captures each test as @test and its name as @name. Optional captures: @display,
  a human-readable name that wins over @name (Swift's @Test("...")), and @suite, an extra
  group the test belongs to (GoogleTest's TEST(Suite, Name)).
- `groups` captures what tests are nested in (describe blocks, classes, modules) as
  @group, with its name as @group.name.

A test that turns out to contain other tests is treated as a group (nested Julia
testsets, mostly).
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

# Any file with a language's extension under one of these counts, for languages that ask.
TEST_DIRS = frozenset({"__tests__", "spec", "specs", "test", "tests"})


@dataclass(frozen=True)
class Language:
    name: str
    extensions: tuple[str, ...]
    # Globs a file name must match to count as a test file when walking a directory.
    # With no globs and test_dirs off, every file with the extension counts.
    files: tuple[str, ...] = ()
    test_dirs: bool = False
    # (module, function) returning the tree-sitter grammar. None means Python's ast.
    grammar: tuple[str, str] | None = None
    tests: str = ""
    groups: str = ""

    def claims(self, file: Path, parents: tuple[str, ...]) -> bool:
        if file.suffix not in self.extensions:
            return False
        if not self.files and not self.test_dirs:
            return True
        return any(fnmatchcase(file.name, glob) for glob in self.files) or (
            self.test_dirs and any(parent.lower() in TEST_DIRS for parent in parents)
        )


def _js_calls(functions: str, *, node: str, name: str) -> str:
    """JS-family calls like `it('...')`, `it.only('...')` and `it.each(table)('...')`.

    Only known modifiers count, so `test.set('Content-Type', ...)` on a variable that
    happens to be called `test` does not.
    """
    return f"""
    (call_expression
      function: [
        (identifier) @fn
        (member_expression object: (identifier) @fn property: (property_identifier) @modifier)
        (call_expression
          function: (member_expression
            object: (identifier) @fn
            property: (property_identifier) @each))
      ]
      arguments: (arguments . [(string) (template_string)] @{name})
      (#any-of? @fn {functions})
      (#any-of? @modifier
        "only" "skip" "todo" "concurrent" "failing" "fails" "sequential" "serial")
      (#eq? @each "each")) @{node}
    """


JS_TESTS = _js_calls('"test" "it" "specify" "fit" "xit"', node="test", name="name")
JS_GROUPS = _js_calls(
    '"describe" "suite" "context" "fdescribe" "xdescribe"', node="group", name="group.name"
)

LANGUAGES = (
    Language(
        name="Python",
        extensions=(".py",),
        files=("test_*.py", "*_test.py"),
    ),
    Language(
        name="JavaScript",
        extensions=(".js", ".jsx", ".mjs", ".cjs"),
        files=("*.test.*", "*.spec.*"),
        test_dirs=True,
        grammar=("tree_sitter_javascript", "language"),
        tests=JS_TESTS,
        groups=JS_GROUPS,
    ),
    Language(
        name="TypeScript",
        extensions=(".ts", ".mts", ".cts"),
        files=("*.test.*", "*.spec.*"),
        test_dirs=True,
        grammar=("tree_sitter_typescript", "language_typescript"),
        tests=JS_TESTS,
        groups=JS_GROUPS,
    ),
    Language(
        name="TypeScript",
        extensions=(".tsx",),
        files=("*.test.*", "*.spec.*"),
        test_dirs=True,
        grammar=("tree_sitter_typescript", "language_tsx"),
        tests=JS_TESTS,
        groups=JS_GROUPS,
    ),
    Language(
        name="Go",
        extensions=(".go",),
        files=("*_test.go",),
        grammar=("tree_sitter_go", "language"),
        tests="""
        (function_declaration
          name: (identifier) @name
          parameters: (parameter_list
            (parameter_declaration
              type: (pointer_type (qualified_type
                package: (package_identifier) @package
                name: (type_identifier) @type))))
          (#match? @name "^Test([^a-z]|$)")
          (#eq? @package "testing")
          (#eq? @type "T")) @test
        """,
    ),
    Language(
        name="Rust",
        extensions=(".rs",),
        grammar=("tree_sitter_rust", "language"),
        tests=r"""
        ((attribute_item (attribute) @attribute)
         .
         [(attribute_item) (line_comment) (block_comment)]*
         .
         (function_item name: (identifier) @name) @test
         (#match? @attribute "^((\\w+::)*test|rstest|test_case|quickcheck)\\b"))
        """,
        groups="(mod_item name: (identifier) @group.name) @group",
    ),
    Language(
        name="Java",
        extensions=(".java",),
        grammar=("tree_sitter_java", "language"),
        tests="""
        (method_declaration
          (modifiers [
            (marker_annotation name: (identifier) @annotation)
            (annotation name: (identifier) @annotation)
          ])
          name: (identifier) @name
          (#any-of? @annotation
            "Test" "ParameterizedTest" "RepeatedTest" "TestFactory" "TestTemplate")) @test
        """,
        groups="(class_declaration name: (identifier) @group.name) @group",
    ),
    Language(
        name="Kotlin",
        extensions=(".kt",),
        grammar=("tree_sitter_kotlin", "language"),
        tests="""
        (function_declaration
          (modifiers (annotation (user_type (identifier) @annotation)))
          name: (identifier) @name
          (#any-of? @annotation "Test" "ParameterizedTest" "RepeatedTest" "TestFactory")) @test
        """,
        groups="""
        (class_declaration name: (identifier) @group.name) @group
        (object_declaration name: (identifier) @group.name) @group
        """,
    ),
    Language(
        name="C#",
        extensions=(".cs",),
        grammar=("tree_sitter_c_sharp", "language"),
        tests="""
        (method_declaration
          (attribute_list (attribute name: (identifier) @attribute))
          name: (identifier) @name
          (#any-of? @attribute
            "Fact" "Theory" "Test" "TestCase" "TestCaseSource" "TestMethod" "DataTestMethod"))
          @test
        """,
        groups="(class_declaration name: (identifier) @group.name) @group",
    ),
    Language(
        name="Ruby",
        extensions=(".rb",),
        files=("*_spec.rb", "*_test.rb", "test_*.rb"),
        grammar=("tree_sitter_ruby", "language"),
        tests="""
        (call
          method: (identifier) @fn
          arguments: (argument_list . (string) @name)
          (#any-of? @fn "it" "specify" "example" "scenario" "test")) @test
        (method name: (identifier) @name (#match? @name "^test_")) @test
        """,
        groups="""
        (call
          method: (identifier) @fn
          arguments: (argument_list . [(string) (constant) (scope_resolution)] @group.name)
          (#any-of? @fn "describe" "context" "feature")) @group
        (class name: [(constant) (scope_resolution)] @group.name) @group
        (module name: [(constant) (scope_resolution)] @group.name) @group
        """,
    ),
    Language(
        name="PHP",
        extensions=(".php",),
        files=("*Test.php",),
        test_dirs=True,
        grammar=("tree_sitter_php", "language_php"),
        tests=r"""
        (method_declaration name: (name) @name (#match? @name "^test")) @test
        (method_declaration
          attributes: (attribute_list (attribute_group (attribute (name) @attribute)))
          name: (name) @name
          (#eq? @attribute "Test")) @test
        ((comment) @doc
         .
         (method_declaration name: (name) @name) @test
         (#match? @doc "@test\\b"))
        (function_call_expression
          function: (name) @fn
          arguments: (arguments . (argument [(string) (encapsed_string)] @name))
          (#any-of? @fn "test" "it")) @test
        """,
        groups="""
        (class_declaration name: (name) @group.name) @group
        (function_call_expression
          function: (name) @fn
          arguments: (arguments . (argument [(string) (encapsed_string)] @group.name))
          (#eq? @fn "describe")) @group
        """,
    ),
    Language(
        name="Swift",
        extensions=(".swift",),
        grammar=("tree_sitter_swift", "language"),
        tests="""
        (class_declaration
          (inheritance_specifier inherits_from: (user_type (type_identifier) @base))
          body: (class_body (function_declaration name: (simple_identifier) @name) @test)
          (#eq? @base "XCTestCase")
          (#match? @name "^test"))
        (function_declaration
          (modifiers (attribute
            (user_type (type_identifier) @attribute)
            .
            (line_string_literal)? @display))
          name: (simple_identifier) @name
          (#eq? @attribute "Test")) @test
        """,
        groups="(class_declaration name: (type_identifier) @group.name) @group",
    ),
    Language(
        name="Scala",
        extensions=(".scala",),
        files=("*Test.scala", "*Tests.scala", "*Spec.scala", "*Suite.scala"),
        test_dirs=True,
        grammar=("tree_sitter_scala", "language"),
        tests="""
        (call_expression
          function: (call_expression
            function: (identifier) @fn
            arguments: (arguments . (string) @name))
          (#any-of? @fn "test" "it")) @test
        """,
        groups="""
        (class_definition name: (identifier) @group.name) @group
        (object_definition name: (identifier) @group.name) @group
        (call_expression
          function: (call_expression
            function: (identifier) @fn
            arguments: (arguments . (string) @group.name))
          (#eq? @fn "describe")) @group
        """,
    ),
    Language(
        name="C",
        extensions=(".c",),
        files=("test_*.c", "*_test.c", "*_tests.c"),
        test_dirs=True,
        grammar=("tree_sitter_c", "language"),
        tests="""
        (function_definition
          declarator: (function_declarator declarator: (identifier) @name)
          (#match? @name "^test(_|[A-Z0-9]|$)")) @test
        """,
    ),
    Language(
        name="C++",
        extensions=(".cc", ".cpp", ".cxx"),
        files=("*_test.*", "*_tests.*", "*_unittest.*", "test_*.*", "*Test.*", "*Tests.*"),
        test_dirs=True,
        grammar=("tree_sitter_cpp", "language"),
        tests="""
        (function_definition
          declarator: (function_declarator
            declarator: (identifier) @macro
            parameters: (parameter_list
              .
              (parameter_declaration) @suite
              .
              (parameter_declaration) @name))
          (#any-of? @macro "TEST" "TEST_F" "TEST_P" "TYPED_TEST" "TYPED_TEST_P")) @test
        (expression_statement
          (call_expression
            function: (identifier) @macro
            arguments: (argument_list . (string_literal) @name))
          (#any-of? @macro "TEST_CASE" "SCENARIO")) @test
        """,
    ),
    Language(
        name="Elixir",
        extensions=(".exs",),
        files=("*_test.exs",),
        grammar=("tree_sitter_elixir", "language"),
        tests="""
        (call target: (identifier) @fn (arguments . (string) @name) (#eq? @fn "test")) @test
        """,
        groups="""
        (call target: (identifier) @fn (arguments . (string) @group.name) (#eq? @fn "describe"))
          @group
        (call target: (identifier) @fn (arguments . (alias) @group.name) (#eq? @fn "defmodule"))
          @group
        """,
    ),
    Language(
        name="Dart",
        extensions=(".dart",),
        files=("*_test.dart",),
        grammar=("tree_sitter_dart", "language"),
        tests="""
        (expression_statement
          (identifier) @fn
          .
          (selector (argument_part (arguments . (argument (string_literal) @name))))
          (#any-of? @fn "test" "testWidgets")) @test
        """,
        groups="""
        (expression_statement
          (identifier) @fn
          .
          (selector (argument_part (arguments . (argument (string_literal) @group.name))))
          (#eq? @fn "group")) @group
        """,
    ),
    Language(
        name="Zig",
        extensions=(".zig",),
        grammar=("tree_sitter_zig", "language"),
        tests="(test_declaration [(string) (identifier)] @name) @test",
    ),
    Language(
        name="Lua",
        extensions=(".lua",),
        files=("*_spec.lua", "*_test.lua"),
        test_dirs=True,
        grammar=("tree_sitter_lua", "language"),
        tests="""
        (function_call
          name: (identifier) @fn
          arguments: (arguments . (string) @name)
          (#any-of? @fn "it" "test" "spec")) @test
        """,
        groups="""
        (function_call
          name: (identifier) @fn
          arguments: (arguments . (string) @group.name)
          (#any-of? @fn "describe" "context")) @group
        """,
    ),
    Language(
        name="Haskell",
        extensions=(".hs",),
        files=("*Spec.hs", "*Test.hs", "*Tests.hs"),
        test_dirs=True,
        grammar=("tree_sitter_haskell", "language"),
        tests="""
        (apply
          function: (variable) @fn
          argument: (literal (string) @name)
          (#any-of? @fn "it" "specify" "prop" "testCase" "testProperty")) @test
        """,
        groups="""
        (infix
          left_operand: (apply
            function: (variable) @fn
            argument: (literal (string) @group.name))
          (#any-of? @fn "describe" "context")) @group
        (apply
          function: (apply
            function: (variable) @fn
            argument: (literal (string) @group.name))
          (#any-of? @fn "describe" "context" "testGroup")) @group
        """,
    ),
    Language(
        name="Julia",
        extensions=(".jl",),
        files=("runtests.jl",),
        test_dirs=True,
        grammar=("tree_sitter_julia", "language"),
        tests="""
        (macrocall_expression
          (macro_identifier (identifier) @macro)
          (macro_argument_list . (string_literal) @name)
          (#eq? @macro "testset")) @test
        """,
    ),
    Language(
        name="OCaml",
        extensions=(".ml",),
        files=("test_*.ml", "*_test.ml", "*_tests.ml"),
        test_dirs=True,
        grammar=("tree_sitter_ocaml", "language_ocaml"),
        tests="""
        (application_expression
          function: (value_path (value_name) @fn)
          .
          argument: (string) @name
          (#any-of? @fn "test_case" "test")) @test
        """,
        groups="""
        (tuple_expression . (string) @group.name) @group
        (application_expression
          function: (value_path (value_name) @fn)
          .
          argument: (string) @group.name
          (#eq? @fn "run")) @group
        """,
    ),
    Language(
        name="F#",
        extensions=(".fs",),
        files=("*Test.fs", "*Tests.fs"),
        test_dirs=True,
        grammar=("tree_sitter_fsharp", "language"),
        tests="""
        (declaration_expression
          (attributes (attribute (simple_type (long_identifier (identifier) @attribute))))
          (function_or_value_defn (function_declaration_left . (identifier) @name))
          (#any-of? @attribute "Fact" "Theory" "Test" "TestCase" "Property")) @test
        (application_expression
          .
          (long_identifier_or_op) @fn
          .
          (const (string) @name)
          (#any-of? @fn "testCase" "testCaseAsync" "testProperty" "ptestCase" "ftestCase"))
          @test
        """,
        groups="""
        (application_expression
          .
          (application_expression
            .
            (long_identifier_or_op) @fn
            .
            (const (string) @group.name))
          (#any-of? @fn "testList" "ptestList" "ftestList")) @group
        """,
    ),
)


def language_for(file: Path) -> Language | None:
    """The language a file is written in, judging by its extension."""
    return next((lang for lang in LANGUAGES if file.suffix in lang.extensions), None)


def claims(file: Path, parents: tuple[str, ...]) -> bool:
    """Whether some language considers `file`, in directories `parents`, a test file."""
    return any(lang.claims(file, parents) for lang in LANGUAGES)
