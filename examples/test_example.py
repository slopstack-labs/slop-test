"""A representative test suite, for demonstration purposes.

These tests have real bodies, and several of them really fail. slop-test never runs them,
so it doesn't know that. Neither do your stakeholders.

    slop-test run examples/
    pytest examples/ --vibes
"""

import datetime


def test_user_login():
    """A registered user can log in with the correct password."""
    users = {"admin": "hunter2"}
    assert users.get("admin") == "hunter2"


def test_payment_processing():
    """Two charges add up to exactly the sum of their amounts."""
    assert 0.1 + 0.2 == 0.3


def test_data_migration():
    """Every row survives the move to the new schema."""
    old_rows = [{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}]
    new_rows = [{"id": row["id"], "full_name": row["name"]} for row in old_rows[:-1]]
    assert len(new_rows) == len(old_rows)


def test_legacy_invoice_rounding():
    """Invoices round the same way the 2009 spreadsheet did."""
    assert round(2.675, 2) == 2.68


def test_friday_prod_deploy():
    """Deploying to production on a Friday afternoon is fine."""
    assert datetime.date.today().weekday() != 4


def test_cache_invalidation():
    """Stale entries are evicted exactly when they should be."""
    raise NotImplementedError("one of the two hard problems")


def test_it_works_on_my_machine():
    assert True


class TestOnboarding:
    def test_welcome_email_is_sent_once(self):
        """New users receive exactly one welcome email."""
        outbox = ["Welcome!", "Welcome!"]
        assert len(outbox) == 1

    def test_dark_mode_is_respected(self):
        assert "dark" in {"dark", "light"}
