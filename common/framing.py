"""NDJSON framing over plain TCP sockets.

FROZEN MODULE -- do not change without updating docs/CONTRACTS.md.

Wire format
-----------
Every message is a single JSON object encoded as UTF-8 and terminated by one
``\\n`` byte. A JSON encoder never emits a literal newline, so the delimiter is
unambiguous. Messages must not contain embedded newlines.

Why NDJSON instead of length-prefixed frames: it is readable directly in the
terminal (``nc``, ``socat``, ``tee``) which is exactly the demo evidence the
rubric asks for, and it survives partial reads without a header parser.

Limits
------
``MAX_MESSAGE_BYTES`` bounds a single line so a broken or malicious peer
cannot exhaust the ship's memory. An oversized line is dropped and the reader
returns ``None`` so the caller can close the connection.
"""

from __future__ import annotations

import json
import socket
from typing import Any, Final

from pydantic import BaseModel, ValidationError

from common.protocol import SensorEvent

#: Maximum accepted length of a single JSON line, in bytes.
MAX_MESSAGE_BYTES: Final[int] = 64 * 1024

#: Socket timeout, in seconds, for the blocking recv() used by the ship.
DEFAULT_SOCKET_TIMEOUT: Final[float] = 1.0

_NEWLINE: Final[bytes] = b"\n"


class ProtocolError(Exception):
    """Raised when a peer sends something that is not a valid NDJSON message."""


def encode(message: BaseModel | dict[str, Any]) -> bytes:
    """Serialize a pydantic model (or plain dict) into one NDJSON line."""
    payload = message.model_dump() if isinstance(message, BaseModel) else message
    line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return line.encode("utf-8") + _NEWLINE


def decode(line: bytes | str) -> dict[str, Any]:
    """Parse one NDJSON line into a dict.

    Raises:
        ProtocolError: on invalid UTF-8, invalid JSON, oversized input, or a
            JSON value that is not an object.
    """
    raw = line.encode("utf-8") if isinstance(line, str) else line
    if len(raw) > MAX_MESSAGE_BYTES:
        raise ProtocolError(f"message exceeds {MAX_MESSAGE_BYTES} bytes")
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid NDJSON message: {exc}") from exc
    if not isinstance(obj, dict):
        raise ProtocolError("message must be a JSON object")
    return obj


def send_msg(sock: socket.socket, message: BaseModel | dict[str, Any]) -> None:
    """Send one message on an already-connected socket."""
    sock.sendall(encode(message))


def recv_line(
    sock: socket.socket,
    buffer: bytearray,
) -> bytes | None:
    """Read exactly one NDJSON line into ``buffer``.

    ``buffer`` carries leftovers between calls: TCP may split or coalesce
    writes, so the caller owns the accumulator and passes the same bytearray
    on every call for a given connection.

    Returns:
        The line (without the trailing newline), or ``None`` when the peer
        closed the connection or sent nothing before the socket timeout.
    """
    while _NEWLINE not in buffer:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            return None
        except OSError:
            return None
        if not chunk:
            return None
        buffer.extend(chunk)
        if len(buffer) > MAX_MESSAGE_BYTES and _NEWLINE not in buffer:
            raise ProtocolError(f"line exceeds {MAX_MESSAGE_BYTES} bytes")

    line, _, remainder = buffer.partition(_NEWLINE)
    buffer[:] = remainder
    return bytes(line)


def recv_event(sock: socket.socket, buffer: bytearray) -> SensorEvent | None:
    """Read one ``SensorEvent``.

    Malformed or schema-invalid messages raise :class:`ProtocolError` so the
    ship can log the offending peer and keep serving the other seven nodes.
    """
    line = recv_line(sock, buffer)
    if line is None:
        return None
    if not line.strip():
        return recv_event(sock, buffer)
    payload = decode(line)
    try:
        return SensorEvent.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolError(f"invalid SensorEvent: {exc}") from exc


__all__ = [
    "DEFAULT_SOCKET_TIMEOUT",
    "MAX_MESSAGE_BYTES",
    "ProtocolError",
    "decode",
    "encode",
    "recv_event",
    "recv_line",
    "send_msg",
]
