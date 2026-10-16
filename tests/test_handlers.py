from unittest.mock import patch

import pytest

from app.tasks.handlers import fake_io, fibonacci, flaky


def test_fibonacci_value():
    assert fibonacci({"n": 10}) == {"n": 10, "value": 55}


def test_fibonacci_caps_n_at_35():
    with patch("app.tasks.handlers._fib", return_value=1):
        assert fibonacci({"n": 100})["n"] == 35


def test_fake_io_sleeps_requested_seconds():
    with patch("app.tasks.handlers.time.sleep") as sleep_mock:
        assert fake_io({"seconds": 3}) == {"slept": 3.0}
    sleep_mock.assert_called_once_with(3.0)


def test_flaky_never_fails_at_zero_rate():
    assert flaky({"failure_rate": 0}) == {"ok": True}


def test_flaky_always_fails_at_full_rate():
    with pytest.raises(RuntimeError):
        flaky({"failure_rate": 1.0})
