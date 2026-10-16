import random
import time


def _fib(n: int) -> int:
    return n if n < 2 else _fib(n - 1) + _fib(n - 2)


def fibonacci(payload: dict) -> dict:
    """CPU-bound. Naive recursion on purpose, so it burns CPU."""
    n = min(int(payload.get("n", 30)), 35)
    return {"n": n, "value": _fib(n)}


def fake_io(payload: dict) -> dict:
    """Simulates I/O-bound work (network call, file upload...)."""
    seconds = float(payload.get("seconds", 2))
    time.sleep(seconds)
    return {"slept": seconds}


def flaky(payload: dict) -> dict:
    """Fails randomly. Used for failure-injection tests."""
    failure_rate = float(payload.get("failure_rate", 0.5))
    if random.random() < failure_rate:
        raise RuntimeError("Simulated failure")
    return {"ok": True}


HANDLERS = {
    "fibonacci": fibonacci,
    "fake_io": fake_io,
    "flaky": flaky,
}
