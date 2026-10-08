"""Tests with problems, for roast mode. Every one of them passes under plain pytest.

pytest examples/roast_me.py --roast
slop-test roast examples/roast_me.py
"""

import time
from unittest import mock


def charge(amount):
    return round(amount * 1.2, 2)


def test_charge_adds_vat():
    """Charging adds 20% VAT."""
    assert charge(10) == 12.0


def test_it_works():
    charge(10)


def test_vat_is_correct():
    assert True


def test_receipt_is_eventually_emailed():
    time.sleep(1.1)
    print("did it send?")
    assert charge(5) == 6.0


def test_refund_never_crashes():
    try:
        charge(None)
    except Exception:
        pass


@mock.patch("time.time")
@mock.patch("time.sleep")
def test_checkout_with_everything_mocked(sleep, now):
    gateway = mock.Mock()
    ledger = mock.MagicMock()
    gateway.pay(charge(10))
    ledger.record(charge(10))
    # TODO: check the ledger too
    gateway.pay.assert_called_once_with(12.0)
