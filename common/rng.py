"""Per-sector pseudo-random streams derived from one shared seed.

Each node needs its own sequence, but all of them must come from the same
seed: sharing a stream would make the eight nodes report the same value at
the same tick.

The value is taken from a digest of ``"<seed>:<sector>"``, so neither
neighbouring sector names nor neighbouring seeds give neighbouring streams.
"""

from __future__ import annotations

import hashlib
import random

from common.sectors import SectorType

#: Bytes taken from the digest; 8 is enough entropy for a 32-bit MT seed.
_DIGEST_BYTES = 8


def stream_for(seed: int | str, sector: SectorType) -> random.Random:
    """Stream for one sector. Same ``(seed, sector)``, same sequence.

    Every call returns a fresh object, so callers never share state.
    """
    material = f"{seed}:{sector}".encode()
    digest = hashlib.blake2b(material, digest_size=_DIGEST_BYTES).digest()
    return random.Random(int.from_bytes(digest, "big"))


def new_seed() -> str:
    """A fresh seed for a run that did not specify one.

    Text, so it can be printed and pasted back into ``AEGIS_SEED`` unchanged.
    """
    return str(random.SystemRandom().randrange(10**12))


__all__ = ["new_seed", "stream_for"]
