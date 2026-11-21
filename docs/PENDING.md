# PENDING

What delivery 2 still needs, taken from the assignment and checked against the
code. Each item says what is missing, where it goes, and how to tell it is
done. Nothing here changes the detection rule or the contracts in
[`CONTRACTS.md`](CONTRACTS.md).

Sizes: **S** is one sitting, **M** is an afternoon, **L** is a day or more.

---

## 1. Shared-seed PRNG — requirement 2

**Missing.** `common/rng.py` does not exist. `sensor/world.py` calls
`random.random()` with no seed, so two runs of the same scenario are unrelated
and no run can be replayed.

**Where:** new `common/rng.py`, used by `sensor/world.py`.

**Done when:**

- one seed is read at launch (`AEGIS_SEED`, defaulting to a random one that is
  printed once) and passed to every process by `start.sh`
- each node derives its own stream from `(seed, sector)`, so the eight nodes
  do not emit the same sequence
- the same seed produces byte-identical event sequences on a re-run
- `SENSOR_INTERVAL` and `DETECTION_PROBABILITY` stay as they are

**Size:** S. **Owner:** A.

---

## 2. Heartbeats and inactivity timeout — requirement 4

**Missing.** `SensorEvent` carries `type: "HEARTBEAT"` and `ThreatMatrix.apply`
already ignores it (a heartbeat never writes a cell), but **no sensor emits
one**, and the ship has no timer. A sensor that dies without closing the socket
is never marked offline.

**Where:** `sensor/main.py` (emit), `ship/registry.py` + `ship/server.py`
(expire), `ship/config.py` (interval).

**Done when:**

- a sensor sends `HEARTBEAT` every `HEARTBEAT_INTERVAL` seconds, including
  while it has nothing to report
- the ship records `last_seen` per sector and marks a sector offline once
  `2 x HEARTBEAT_INTERVAL` passes with no message of any kind
- a heartbeated sensor shows online again without a reconnect
- a sensor killed with `SIGKILL` (socket left open) goes offline within the
  timeout
- **a sector marked offline keeps its last cell.** Silence is not a zero.
  This is already the behaviour and must not change.

**Size:** M. **Owner:** B.

---

## 3. Duplicate suppression — requirement 3

**Missing.** `SensorEvent.seq` is on the wire and unused. A retransmitted or
duplicated event is applied twice.

**Where:** `ship/matrix.py` (track last `seq` per sector) or a small filter in
`ship/server.py`.

**Done when:**

- an event whose `seq` is `<=` the last one seen for that sector is dropped
  before it reaches the matrix
- the drop is silent and does not count as an error
- a test feeds `seq` 0, 1, 1, 2 and asserts the board only reflects 0, 1, 2

**Size:** S. **Owner:** A.

---

## 4. Threat prioritization — requirement 3

**Missing.** Every event is applied immediately in arrival order. Two
detections arriving at the same moment are handled in whatever order the
threads happen to run.

**Where:** `ship/server.py` (batch per tick), `ship/matrix.py` unchanged.

**Done when:**

- the ship applies events in a deterministic order within a tick, so the board
  does not depend on thread scheduling
- if two events for the same sector arrive in one tick, the higher `seq` wins
- the board for a given set of events is identical across repeated runs

This is the weakest requirement in the assignment: "priorizar amenazas" is
never defined beyond ordering. Document the choice made here.

**Size:** M. **Owner:** A.

---

## 5. Aliens — requirement 5

**Missing.** `origin: "alien"` is on the wire and the ship ignores it.
`grep origin ship/` returns nothing.

**Where:** `sensor/main.py` (`--alien` flag), `ship/detector.py` or
`ship/matrix.py` (discount), `ship/console.py` (show it).

**Done when:**

- a sensor can be started with `--alien`, making it occasionally report a
  value its own world did not produce
- the ship detects the injection and does not let a single alien node raise
  RED_ALERT on its own
- a legitimate detection from that sector still counts
- the dashboard marks the node as suspect instead of hiding it

Keep it bounded: the assignment asks the system to survive a lying sensor, not
to build a Byzantine-agreement protocol.

**Size:** M. **Owner:** B.

---

## 6. Coverage reconfiguration — requirement 4

**Missing.** When a sector goes offline its cell freezes, which is correct, but
nothing reports which sectors are uncovered.

**Where:** `ship/registry.py`, `ship/console.py`.

**Done when:**

- the board distinguishes "no reading" from "read 0", which it does today,
  and the dashboard shows how many sectors are currently uncovered
- the ship never treats a frozen cell as a fresh confirmation

**Size:** S. **Owner:** B.

---

## 7. Video — 25 points

Not code, but the largest single block of the rubric.

**Content, in order:**

1. `./start.sh`, ship window showing the board redrawing
2. switch to a sensor window showing `val=0/1` lines
3. force the five states from the assignment with
   `python -m sensor.main <SECTOR> --val 1 --once` and show the banner change
4. kill one sensor and show it going offline without disturbing the rest
5. one sentence on the architecture: eight clients, one server, one lock

**Size:** S to record, M to get clean. **Owner:** both.

---

## Suggested order

| # | Item | Points | Size |
|---|---|---|---|
| 1 | Shared-seed PRNG | 15 | S |
| 2 | Heartbeats + timeout | part of 20 | M |
| 3 | Duplicate suppression | part of 20 | S |
| 7 | Video | 25 | S |
| 5 | Aliens | requirement 5 | M |
| 4 | Prioritization | part of 20 | M |
| 6 | Coverage reporting | part of 20 | S |

Items 1, 2 and 3 together cover the three specific requirements that are
currently unimplemented and are all small. Start there.

## Not planned

- WebSocket dashboard (`ship/hub.py`, `ship/ws_bridge.py`). No rubric line
  mentions a browser. The TUI already satisfies "ejecución y video". Do this
  only if there is time left after the items above.
- Authentication on the landing. Not in the assignment.
