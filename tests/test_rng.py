"""Shared-seed PRNG: same seed replays, different sectors diverge."""

from __future__ import annotations

from common.rng import new_seed, stream_for
from common.sectors import SECTORS


def draw(seed: str, sector: str, count: int = 20) -> list[float]:
    stream = stream_for(seed, sector)  # type: ignore[arg-type]
    return [stream.random() for _ in range(count)]


def test_same_seed_and_sector_replay_identically() -> None:
    assert draw("42", "N") == draw("42", "N")


def test_different_seeds_diverge() -> None:
    assert draw("42", "N") != draw("43", "N")


def test_sectors_have_independent_streams() -> None:
    streams = {sector: draw("42", sector) for sector in SECTORS}
    assert len({tuple(values) for values in streams.values()}) == len(SECTORS)


def test_neighbouring_seeds_are_not_neighbouring_streams() -> None:
    """Seeds 42 and 43 do not give shifted streams."""
    first = draw("42", "N", 5)
    second = draw("43", "N", 5)
    assert first != second
    assert not all(abs(a - b) < 1e-9 for a, b in zip(first, second))


def test_streams_are_independent_objects() -> None:
    """Drawing from one does not advance another."""
    a = stream_for("42", "N")
    a.random()
    fresh = stream_for("42", "N")
    assert a.random() != fresh.random()


def test_each_call_starts_from_the_beginning() -> None:
    first = stream_for("42", "E").random()
    _ = stream_for("42", "E").random()
    assert stream_for("42", "E").random() == first


def test_new_seed_is_a_numeric_string() -> None:
    seed = new_seed()
    assert seed.isdigit()
    assert len(seed) <= 12


def test_new_seed_varies() -> None:
    assert len({new_seed() for _ in range(20)}) > 1


def test_stream_reproduces_a_detection_sequence() -> None:
    """Same seed, same val sequence."""

    def values(seed: str, sector: str) -> list[int]:
        stream = stream_for(seed, sector)  # type: ignore[arg-type]
        return [1 if stream.random() < 0.2 else 0 for _ in range(30)]

    assert values("7", "SO") == values("7", "SO")
    assert values("7", "SO") != values("8", "SO")
