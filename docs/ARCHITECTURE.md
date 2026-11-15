# ARCHITECTURE

What we are building, how the pieces fit, and what is left. For the exact
field-level interfaces, read [`CONTRACTS.md`](CONTRACTS.md). This document is
about intent and shape.

---

## 1. The product in one paragraph

A ship sits in space surrounded by eight radar sensors, one per direction. A
meteor approaches. Each sensor that sees it reports to the ship over TCP. The
ship builds a 3x3 threat matrix from those reports and decides whether the
meteor is heading for it or merely passing by. A dashboard shows the board and
the current alert level in real time.

The interesting part is not the rule; it is that eight independent processes,
each possibly lying or dying, must agree on one board without races, without
duplicates and without a global clock.

## 2. Topology

```text
   sensor/N ─┐
  sensor/NE ─┤
   sensor/E ─┤           ┌──────────────┐          ┌───────────┐
  sensor/SE ─┼── TCP ───▶│  SHIP        │── WS ───▶│  BROWSE   │
   sensor/S ─┤  :5000    │  server      │  :8080   │  dashboard│
  sensor/SO ─┤           │  matrix      │          │           │
   sensor/O ─┤           │  detector    │          └───────────┘
  sensor/NO ─┘           └──────────────┘
   (8 clients,             (1 server,
    write-only)             read+write)
```

Three kinds of process, three directions of data:

| Link | Direction | Protocol | Who initiates |
|---|---|---|---|
| sensor → ship | events | TCP, NDJSON | sensor (client) |
| ship → dashboard | state snapshots | WebSocket, JSON | ship pushes |
| ship → ship | none | — | — |

The ship never connects out to the sensors. It only accepts. That is what
makes the topology a star: remove any sensor and the rest keep working.

## 3. Process model

### Sensors (`sensor/`, one process each)

Each sensor is a dumb loop. It:

1. generates meteors for its own direction (see §5),
2. sleeps a random interval,
3. connects to the ship, sends events, and reconnects if the link drops.

A sensor holds **no** board state and **no** knowledge of the other sectors.
It does not know what the alert level is. It only knows "I see something" or
"I do not".

### Ship (`ship/`, one process)

The ship is the only place with global state. Internally it has four
responsibilities, each in its own module:

| Module | Responsibility | Owner |
|---|---|---|
| `ship/server.py` | accept connections, one thread per sensor, own the socket loop | B |
| `ship/registry.py` | which of the 8 sectors are currently connected | B |
| `ship/matrix.py` | the 3x3 board, guarded by a lock | A |
| `ship/detector.py` | board → alert level, pure function | A |

The split matters: `detector.py` and `matrix.py` never touch a socket, and
`server.py` never touches the decision rule. That is what
`docs/CONTRACTS.md` freezes and what the concurrency tests pin down.

### Dashboard (`ui/`, one process)

A browser page. Talks to the ship over a WebSocket bridge (`ship/hub.py` +
`ship/ws_bridge.py`, delivery 2). It never talks to the sensors.

## 4. Data flow, end to end

```text
1. sensor generates a meteor          sensor/world.py
2. sensor connects                    TCP :5000
3. sensor sends SensorEvent           {"type":"DETECTION","sector":"N","val":1,...}
4. ship thread reads the line         framing.recv_event(sock, buffer)
5. ship writes the board under lock   ThreatMatrix.apply(event)
6. ship re-evaluates the rule         detector.classify(cells)
7. ship broadcasts a snapshot         UIStateUpdate(matrix, alert_level, seq)
8. dashboard replaces its state       (no diffing: every frame is complete)
```

Step 5 is the only mutation in the system. Everything before it is I/O,
everything after it is a read. That is why one lock is enough.

## 5. Random generation

The assignment requires a shared-seed PRNG so the environment is
**distributed and deterministic**: all nodes derive the same meteor sequence
from the same seed, and a re-run with the same seed replays identically.

Design (not built yet, entry point `common/rng.py`):

- One seed is chosen at launch and passed to every process.
- Each node derives its own stream: `stream(sector) = PRNG(seed, sector)`.
  Two nodes with the same seed but different sector names produce different
  sequences. A node with a different seed produces a different world.
- Determinism is the debugging feature: a run that raises `RED_ALERT` at
  `t=4.2` can be replayed exactly.

This is delivery-2 work. Nothing in the delivery-1 code depends on it: sensors
can use plain `random` today, and the swap is local to `sensor/world.py`.

## 6. Fault model

Three failure modes are in scope, in increasing order of difficulty:

| Mode | Symptom | Handling |
|---|---|---|
| node crashes / unplugs | socket closes | ship marks the sector offline, keeps the other seven |
| node is slow or silent | no traffic on the socket | heartbeat timer expires, sector marked offline |
| node lies | valid JSON, wrong data | `origin: "alien"` marks the source; deliveries-2 discards or down-weights it |

Delivery 1 covers the first partly (the ship tolerates a dropped connection
because each sensor runs in its own thread) and reserves the field for the
third. The heartbeat timer is delivery 2.

Important: **a dead sensor does not clear its cell.** A `0` from the sensor is
a real reading; silence is not. Losing `N` means the board keeps whatever `N`
last said, which is why a lost sensor is shown separately in
`offline_nodes` rather than as an empty cell.

## 7. What "done" means for delivery 1 (the avance)

The avance is the architectural base, not the finished product. It is done
when these are true:

- [x] Board geometry and adjacency are defined and tested.
- [x] The decision rule is implemented and matches all five reference states.
- [x] The wire protocol is defined and framed (NDJSON over TCP).
- [x] The shared board is concurrency-safe and proves it under 8 threads.
- [x] A sensor process connects and sends real events.
- [x] The ship accepts 8 connections and builds the board from them.
- [x] `start.sh` brings up the ship and all eight sensors (tmux, or `--plain`).
- [x] The five reference states are reproducible from the running system.

Out of scope for delivery 1: heartbeats, reconnection with backoff beyond a
simple retry, alien nodes, deduplication, message prioritisation, the PRNG,
the WebSocket bridge, and the dashboard UI.

## 8. Repository layout

```text
common/            frozen shared contracts, imported by both sides
  sectors.py       SectorType, SECTOR_MAP, SHIP, Matrix, neighbors()
  protocol.py      SensorEvent, NodeStatus, UIStateUpdate (pydantic)
  framing.py       NDJSON encode/decode, send_msg, recv_event

ship/              the server process
  detector.py      classify(matrix) -> AlertLevel        (pure, no I/O)
  matrix.py        ThreatMatrix: cells + Lock + snapshot
  server.py        (B) accept loop, one thread per sensor
  registry.py      (B) which sectors are online
  main.py          (A) wire registry + matrix + server together

sensor/            the sensor process
  main.py          (B) connect, loop, send
  world.py         (B) generate meteors for one direction

tools/
  fake_sensor.py   (A) a bare sensor for testing without the sensor module

tests/             detector rule + matrix concurrency
docs/              CONTRACTS.md (interfaces), ARCHITECTURE.md (this file)
```

## 9. Division of work

Split by responsibility layer, not by folder, so neither side blocks the
other.

**A (me):** `common/`, `ship/detector.py`, `ship/matrix.py`, `ship/config.py`,
`ship/main.py`, `tools/fake_sensor.py`, `start.sh`, tests for the rule and the
board. Delivery 2: `ship/hub.py`, `common/rng.py`, alien nodes,
deduplication.

**B (partner):** `ship/server.py`, `ship/registry.py`, `sensor/main.py`,
`sensor/world.py`, tests for the sensor. Delivery 2: `ship/ws_bridge.py`,
`ui/`, video.

The handoff point is `CONTRACTS.md`. B can start `server.py` on day one
because `framing.recv_event()` and `ThreatMatrix.apply()` already exist and
are tested.

## 10. Decisions worth knowing

| Decision | Why |
|---|---|
| NDJSON instead of length-prefixed frames | readable in a terminal, which is the demo evidence the rubric asks for |
| 8-connectivity adjacency | matches what the eye sees on the grid; the statement never defines "adyacente" |
| `detector` is a pure function | fast unit tests, no sockets or clocks in the rule |
| one lock, held only for memory writes | no deadlock possible if no I/O happens inside it |
| `Sequence` for `Matrix` | callers only read; writing is `ThreatMatrix`'s job |
| `type` and `origin` ship in the protocol now | the JSON never changes shape when delivery 2 adds them |
| dead sensor does not clear its cell | silence is not a reading |
