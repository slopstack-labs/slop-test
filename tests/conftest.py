import pytest

pytest_plugins = ["pytester"]


@pytest.fixture(autouse=True)
def no_model_configured(monkeypatch):
    """llm is the default backend, so keep a developer's own model out of the tests."""
    for name in ("SLOP_TEST_BASE_URL", "SLOP_TEST_MODEL", "SLOP_TEST_API_KEY"):
        monkeypatch.delenv(name, raising=False)
