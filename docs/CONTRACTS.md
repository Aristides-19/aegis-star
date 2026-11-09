# CONTRACTS

Interfaces shared by the ship and the eight sensors. Code in `common/` is
**frozen**: if a change here is needed, update `common/`, this file and the
tests in the same commit.

Everything below is implemented and passing tests. Nothing is aspirational.

---

## 1. The board

A 3x3 matrix. Each peripheral cell is one sector (`0` = nothing, `1` =
detection). The centre is the ship and is never written or evaluated.

```text
        col 0    col 1    col 2
      +--------+--------+--------+
row 0 |   NO   |   N    |   NE   |
      +--------+--------+--------+
row 1 |   O    |  SHIP  |   E    |
      +--------+--------+--------+
row 2 |   SO   |   S    |   SE   |
      +--------+--------+--------+
```

Source of truth: `common/sectors.py`.

```python
SectorType = Literal["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
SECTOR_MAP: dict[SectorType, tuple[int, int]]   # sector -> (row, col)
SHIP: tuple[int, int]                           # (1, 1)
Matrix = Sequence[Sequence[int]]                # the board, read-only
```

**Coordinate conventions:**
- `row` grows downwards, `col` grows rightwards, both 0-based.
- `SECTOR_MAP` is the only place a sector name maps to a coordinate. Never
  hardcode `matrix[0][1]`; write `SECTOR_MAP["N"]`.
- `Matrix` is `Sequence`, not `list`, because callers only read it. Writing
  into a matrix is the job of `ThreatMatrix`, which holds a lock.

### 1.1 Adjacency

Two sectors are adjacent if their cells **share an edge or a corner** on the
grid. The ship cell is not a sector, so it never connects anything.

```python
neighbors("N")  -> frozenset({"NO", "NE", "O", "E"})
neighbors("NO") -> frozenset({"N", "O"})
neighbors("N") & neighbors("S")  == frozenset()   # opposite edges never touch
```

Consequence worth knowing: `N` and `E` **are** adjacent, because their cells
meet at the corner of the ship cell. Conversely `N`/`S` and `O`/`E` are not:
they are opposite edges with the ship cell between them.

---

## 2. The decision rule

> Is there a sector reporting `1` that has **no adjacent sector reporting 1**?

| Answer | Result |
|---|---|
| Yes — some detection stands alone | `RED_ALERT`: the object is alone and heading for the ship |
| No — every detection touches another | `NORMAL`: consecutive detections, safe transit |
| Empty matrix | `NORMAL` |

This is the entire algorithm. No grouping, no trajectory inference, no
tie-breaking, no special cases:

```python
# ship/detector.py
def classify(matrix: Matrix) -> AlertLevel:
    active = detected_sectors(matrix)
    for sector in active:
        if not active & neighbors(sector):
            return "RED_ALERT"
    return "NORMAL"
```

Adjacency is **local**: two independent pairs of touching detections are both
in transit, so `{NO, N}` + `{S, SE}` → `NORMAL`, even though they are far
apart. That is the literal reading of the rule above and is covered by
`tests/test_detector.py::test_adjacency_cases`.

### 2.1 Reference cases

From the assignment statement:

| Cells | Result |
|---|---|
| *(nothing)* | `NORMAL` |
| `N` | `RED_ALERT` |
| `NE, E` | `NORMAL` |
| `O` | `RED_ALERT` |
| `NO` | `RED_ALERT` |

Boundary and adjacency cases (in `tests/test_detector.py`):

| Cells | Result | Why |
|---|---|---|
| `NO, N` | `NORMAL` | touching |
| `NO, N, NE` | `NORMAL` | every detection has a neighbour |
| `NO, N, E, SE` | `NORMAL` | connected through the ship corner |
| `NO, N, S, SE` | `NORMAL` | two separate touching pairs; rule is local |
| `NE, E, SO` | `RED_ALERT` | the pair does not protect the lone `SO` |
| `NE, SO` | `RED_ALERT` | opposite corners never touch |
| `NO, SE` | `RED_ALERT` | opposite corners never touch |
| `N, S` | `RED_ALERT` | opposite edges, ship between them |
| `O, E` | `RED_ALERT` | opposite edges |
| `NO, NE` | `RED_ALERT` | share neighbour `N` but are not adjacent |

---

## 3. Transport

Plain TCP, ship listens on port **5000**, one connection per sensor, sensor is
the client. The ship reads and writes; it never initiates.

### 3.1 Message framing: NDJSON

Every message is one JSON object, UTF-8, terminated by a single `\n` byte.

```text
{"type":"DETECTION","sector":"N","val":1,"timestamp":1737000000.0,"seq":3,"origin":"astro"}\n
```

Rules:
- JSON encoding never emits a literal newline, so `\n` is an unambiguous
  delimiter. Messages must not contain embedded newlines.
- **Never assume one `recv()` equals one message.** TCP may split a message
  across packets or coalesce several into one. Always read through
  `common.framing.recv_line`, which accumulates into a caller-owned
  `bytearray`.
- A single line is capped at `MAX_MESSAGE_BYTES` (64 KiB). An oversized line
  raises `ProtocolError`; the caller should drop that connection and keep
  serving the others.
- An empty line is skipped, not treated as an error: `recv_event` reads the
  next one.
- No handshake. The first line a sensor sends is its first event.

### 3.2 Framing API

```python
from common.framing import ProtocolError, recv_event, recv_line, send_msg

send_msg(sock, model)                 # model: pydantic BaseModel or dict
recv_event(sock, buffer) -> SensorEvent | None
```

`recv_event` returns:
- a `SensorEvent` on success,
- `None` when the peer closed the connection or the socket timed out
  (`DEFAULT_SOCKET_TIMEOUT`, 1 s) with nothing to read,
- raises `ProtocolError` on malformed JSON, an oversized line, or a payload
  that fails `SensorEvent` validation.

Note the asymmetry: `None` means "nothing to read right now", so a server loop
can just `continue`. It is **not** an error signal, and it does not mean the
message was invalid. Invalid content always raises.

`buffer` is a `bytearray` **owned by the caller** and passed on every call for
that connection. It carries leftovers between calls; reusing one buffer for two
connections would mix their bytes.

---

## 4. Messages

All messages are pydantic v2 models in `common/protocol.py`.

### 4.1 `SensorEvent` — sensor → ship

| Field | Type | Default | Meaning |
|---|---|---|---|
| `type` | `"DETECTION"` \| `"HEARTBEAT"` | `"DETECTION"` | kind of message |
| `sector` | `SectorType` | required | which sector this reading is about |
| `val` | `0` \| `1` | `0` | detection state, only meaningful for `DETECTION` |
| `timestamp` | `float` | `time.time()` | producer clock, unix seconds, must be finite |
| `seq` | `int` | `0` | per-sensor monotonic counter, used to drop duplicates |
| `origin` | `"astro"` \| `"alien"` | `"astro"` | `alien` marks a faulty/compromised node |

- **`DETECTION`** writes `val` into `sector`.
- **`HEARTBEAT`** never changes the matrix. It exists to prove the node is
  alive; `val` repeats the last reading so the ship can repair state after a
  brief dropout.
- `origin` ships now so the JSON shape never changes: the alien-detection work
  only fills in the value.

### 4.2 `NodeStatus` — internal, ship → ship

Tracks whether a sensor is connected. Not serialized over the wire yet.

| Field | Type | Default |
|---|---|---|
| `sector` | `SectorType` | required |
| `online` | `bool` | `True` |
| `last_seen` | `float` | `time.time()` |
| `origin` | `"astro"` \| `"alien"` | `"astro"` |

### 4.3 `UIStateUpdate` — ship → dashboard

The dashboard is a separate process connected over a future WebSocket bridge.
The model is implemented and validated; the bridge is not written yet.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `matrix` | `list[list[int]]` | required | full 3x3 board, validated 3x3 and binary |
| `alert_level` | `AlertLevel` | `"NORMAL"` | `NORMAL` \| `RED_ALERT` |
| `active_nodes` | `list[str]` | `[]` | sectors currently connected |
| `offline_nodes` | `list[str]` | `[]` | sectors currently lost |
| `seq` | `int` | `0` | monotonically increasing frame counter |
| `ts` | `float` | `time.time()` | ship clock at emission |

Two guarantees the UI relies on:
- Every frame is **self-contained**. The UI never reconstructs state by
  diffing; it just replaces what it holds.
- `seq` increases monotonically, so a late-arriving frame can be discarded by
  comparing `seq` against the last one applied.

### 4.4 JSON shape summary

```jsonc
// SensorEvent
{"type":"DETECTION","sector":"NE","val":1,"timestamp":1737000000.0,"seq":7,"origin":"astro"}

// UIStateUpdate
{"matrix":[[0,0,1],[0,0,1],[0,0,0]],"alert_level":"NORMAL",
 "active_nodes":["N","NE","E","SE","S","SO","O","NO"],"offline_nodes":[],
 "seq":42,"ts":1737000001.0}
```

---

## 5. Concurrency

`ship/matrix.py::ThreatMatrix` is the only component holding board state.

Contract:
- One `threading.Lock` guards the cells. Every write happens inside it.
- **Nothing slow runs while the lock is held**: no sockets, no logging I/O, no
  callbacks. Inside the lock there is only assignment plus a pure
  `detector.classify()` call.
- Readers never take the raw cells. They call `snapshot()`, which returns
  `(matrix_copy, alert_level)` **from inside the same lock**, so the pair is
  always from one instant. A reader can never see `RED_ALERT` attached to an
  empty matrix.
- Writes are idempotent: `set_sector` returns `False` if the cell already had
  that value, and `apply` ignores every non-`DETECTION` event.

```python
matrix.apply(event)              # sensor event in
matrix.snapshot()                # (cells, alert_level) out
matrix.reset()                   # back to all zeros
```

---

## 6. Who owns what

| Area | Owner | Files |
|---|---|---|
| Shared contracts | both, frozen | `common/sectors.py`, `common/protocol.py`, `common/framing.py` |
| Decision rule, board state | A | `ship/detector.py`, `ship/matrix.py` |
| Sockets, node registry | B | `ship/server.py`, `ship/registry.py` |
| Sensor process | B | `sensor/main.py`, `sensor/world.py` |
| Tooling, launcher | A | `tools/fake_sensor.py`, `start.sh` |

B can build `ship/server.py` today against `framing.recv_event()` and
`ThreatMatrix.apply()` without waiting for anything else.

Not yet built: `tools/fake_sensor.py`, `start.sh`, `ship/server.py`,
`ship/registry.py`, `sensor/`, the WebSocket bridge, and the dashboard.
