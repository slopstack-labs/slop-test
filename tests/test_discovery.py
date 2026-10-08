import textwrap
from pathlib import Path

from slop_test.discovery import collect_tests, discover, find_test_files


def write(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


def test_collects_functions_and_class_methods(tmp_path):
    file = write(
        tmp_path / "test_things.py",
        '''
        def test_top_level():
            """Top-level docstring."""
            assert True


        async def test_async_too():
            pass


        class TestCart:
            def test_add_item(self):
                pass

            class TestNested:
                def test_deep(self):
                    pass
        ''',
    )

    tests = collect_tests(file)

    assert [t.qualname for t in tests] == [
        "test_top_level",
        "test_async_too",
        "TestCart::test_add_item",
        "TestCart::TestNested::test_deep",
    ]
    first = tests[0]
    assert first.file == file
    assert first.name == "test_top_level"
    assert first.docstring == "Top-level docstring."
    assert first.source.startswith("def test_top_level():")
    assert first.source.rstrip().endswith("assert True")
    assert first.lineno == 2
    assert tests[1].docstring is None
    assert tests[2].class_path == ("TestCart",)


def test_ignores_non_test_functions(tmp_path):
    file = write(
        tmp_path / "test_noise.py",
        """
        def helper():
            def test_inner():
                pass


        def testing_is_not_a_test():
            pass


        test_lambda = lambda: None


        class Helpers:
            def test_in_wrong_class(self):
                pass


        class TestReal:
            def setup_method(self):
                pass

            def test_real(self):
                pass
        """,
    )

    assert [t.qualname for t in collect_tests(file)] == ["TestReal::test_real"]


def test_does_not_execute_user_code(tmp_path):
    marker = tmp_path / "executed"
    write(
        tmp_path / "test_explosive.py",
        f"""
        import does_not_exist_anywhere

        open({str(marker)!r}, "w").close()
        raise RuntimeError("slop-test imported me")


        def test_survives():
            raise RuntimeError("slop-test ran me")
        """,
    )

    discovery = discover(tmp_path)

    assert [t.name for t in discovery.tests] == ["test_survives"]
    assert not marker.exists()


def test_finds_both_file_patterns_and_skips_junk(tmp_path):
    for name in [
        "test_alpha.py",
        "beta_test.py",
        "pkg/test_gamma.py",
        "conftest.py",
        "helpers.py",
        "test_notes.txt",
        "testing.py",
        ".venv/lib/test_vendored.py",
        "node_modules/test_js.py",
        "pkg/__pycache__/test_cached.py",
    ]:
        write(tmp_path / name, "def test_x():\n    pass\n")

    files = [p.relative_to(tmp_path).as_posix() for p in find_test_files(tmp_path)]

    assert files == ["beta_test.py", "test_alpha.py", "pkg/test_gamma.py"]


def test_explicit_file_is_always_collected(tmp_path):
    file = write(tmp_path / "checks.py", "def test_x():\n    pass\n")

    assert find_test_files(file) == [file]


def test_unparsable_files_are_reported_not_raised(tmp_path):
    write(tmp_path / "test_ok.py", "def test_fine():\n    pass\n")
    broken = write(tmp_path / "test_broken.py", "def test_oops(:\n")

    discovery = discover(tmp_path)

    assert [t.name for t in discovery.tests] == ["test_fine"]
    assert discovery.unparsable == [broken]
