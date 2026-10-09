"""CircuitBreaker: durum makinesi (gerçek kod; saat last_failure_time ile ilerletilir)."""

import pytest

from services.core.hustler.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitBreakerRejectedError,
    CircuitBreakerState,
)


async def _fail(breaker: CircuitBreaker) -> None:
    with pytest.raises(RuntimeError):
        async with breaker:
            raise RuntimeError("boom")


def _breaker(failures: int = 3, cooldown: float = 30.0) -> CircuitBreaker:
    return CircuitBreaker("t", CircuitBreakerConfig(failures, cooldown, 600))


async def test_breaker_trips_open_after_consecutive_failures() -> None:
    b = _breaker()

    for _ in range(2):
        await _fail(b)
    assert str(b.state.value) == CircuitBreakerState.CLOSED.value
    await _fail(b)

    assert b.state is CircuitBreakerState.OPEN
    assert b.failure_count == 3


async def test_open_breaker_rejects_without_running_body() -> None:
    b = _breaker(1)
    await _fail(b)
    ran = False

    with pytest.raises(CircuitBreakerOpenError):
        async with b:
            ran = True

    assert ran is False


async def test_success_resets_failure_streak() -> None:
    b = _breaker()
    await _fail(b)
    await _fail(b)

    async with b:
        pass
    await _fail(b)

    assert b.state is CircuitBreakerState.CLOSED
    assert b.failure_count == 1


async def test_half_open_success_closes_circuit() -> None:
    b = _breaker(1, cooldown=30)
    await _fail(b)
    b.last_failure_time -= 31

    async with b:
        assert b.state is CircuitBreakerState.HALF_OPEN

    assert b.state is CircuitBreakerState.CLOSED
    assert b.failure_count == 0


async def test_half_open_failure_reopens_circuit_immediately() -> None:
    b = _breaker(1, cooldown=30)
    await _fail(b)
    b.last_failure_time -= 31

    await _fail(b)

    assert b.state is CircuitBreakerState.OPEN
    with pytest.raises(CircuitBreakerOpenError):
        async with b:
            pass


async def test_budget_rejection_does_not_count_as_failure() -> None:
    b = _breaker(1)

    with pytest.raises(CircuitBreakerRejectedError):
        async with b:
            raise CircuitBreakerRejectedError("x")

    assert b.failure_count == 0
    assert b.state is CircuitBreakerState.CLOSED


@pytest.mark.parametrize(
    ("seconds", "ok"), [(0, True), (1, True), (600, True), (601, False), (10**6, False)]
)
def test_check_budget_boundary(seconds: int, ok: bool) -> None:
    b = CircuitBreaker("t")

    if ok:
        b.check_budget(seconds)
    else:
        with pytest.raises(CircuitBreakerRejectedError, match="bütçeyi aşıyor"):
            b.check_budget(seconds)


async def test_exception_from_body_is_not_swallowed() -> None:
    b = CircuitBreaker("t")

    with pytest.raises(KeyError):
        async with b:
            raise KeyError("k")
