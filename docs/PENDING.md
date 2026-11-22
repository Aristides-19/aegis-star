# PENDING

What is left for the final delivery. Nothing here changes the detection rule
or the contracts in [`CONTRACTS.md`](CONTRACTS.md).

## How the work is split

Serial: **A finishes before B starts.** `sensor/main.py` and `ship/server.py`
appear in both halves, so parallel work would mean two people in one file.

B's three items need the least judgement: one is wiring, the other two add to
files that already have the shape they need.

| Order | Item | Who | Status |
|---|---|---|---|
| 1st | 2. Duplicate suppression | A | **done** |
| 2nd | 3. Threat prioritization | A | **done** |
| 3rd | 1. Shared-seed PRNG (library) | A | **done** |
| 4th | 6. Aliens | A | **done** |
| 5th | 1. Shared-seed PRNG (wiring) | B | **next** |
| 6th | 5. Coverage reporting | B | pending |
| 7th | 4. Heartbeats and timeout | B | pending |
| — | 7. Demo video | both | pending |

A's half is done: 68 tests, `basedpyright` clean.

**B's items.** `common/rng.py` is already written and tested, so the PRNG work
is a call in `main.py`. Coverage is a `set` over state `registry.py` already
keeps. Heartbeats reuse the tick that prioritization introduces.

**Why A takes aliens.** It is the only item with no recipe: "controlled by
aliens" is as far as the requirement goes. What counts as a lie is a
judgement call.

**Order.** Prioritization introduces the tick, heartbeats expire on that tick,
and dedup keeps `seq` monotone so a seeded replay matches.

Sizes: **XS** is minutes, **S** is one sitting, **M** is an afternoon, **L** is a day.

---

## 1. Shared-seed PRNG — requirement 2

> "Aplicar el algoritmo de número pseudoaleatorio (PRNG con Semilla
> Compartida) para la generación distribuida y determinista del entorno."

**Missing.** `common/rng.py` does not exist. `sensor/world.py` calls
`random.random()` with no seed, so two runs of the same scenario are unrelated
and no run can be replayed.

This item has two halves, done by different people.

### 1a. The library — A

| File | What to do |
|---|---|
| `common/rng.py` | new. `stream_for(seed, sector) -> Random` via `hashlib.blake2b(f"{seed}:{sector}")` narrowed to 8 bytes, fed into `random.Random(int)`. Same seed and sector always give the same stream. |
| `ship/config.py` | add `SEED` read from `AEGIS_SEED`; when unset, draw one at startup and keep it in the process |
| `sensor/world.py` | take a `random.Random` parameter instead of calling module-level `random`; the rest of the function does not change |
| `start.sh` | generate one seed, export it for every window, print it so the recording shows it |

A also lands `tests/test_rng.py` covering the three invariants below, so B
inherits a module that is already proven.

**Done when:**

- the same seed replays an identical event sequence, checked by a test
- two sectors with the same seed produce different sequences
- a different seed produces a different sequence
- `AEGIS_SEED=42 ./start.sh` twice gives the same board at the same tick
- the seed is visible in the ship header so the video can prove it

**Size:** S. **Owner:** A. **Status:** done.

Landed: `common/rng.py` (`stream_for`, `new_seed`), `SEED` and
`ALIEN_LIE_PROBABILITY` in config, `generate_event(stream=...)`,
`start.sh` generating one seed and exporting it for all nine processes, and
the seed shown in the dashboard header so the video can prove it.

`tests/test_rng.py` covers replay, per-sector divergence, independence of
neighbouring seeds, and that each call starts from the beginning.

The eight sensors do **not** use the seed yet: that is 1b below.

### 1b. The wiring — B

A hands over `common/rng.py`, `SEED` in config, and `generate_event` taking a
`Random`. B only connects `sensor/main.py` to it.

| File | What to do |
|---|---|
| `sensor/main.py` | add `--seed`. When it is given, or when `config.SEED` is set, build `stream = stream_for(seed, sector)` once before the loop and pass `stream=stream` to `generate_event`. When neither is set, pass nothing and the module-level generator is used |
| `start.sh` | nothing: it already exports `AEGIS_SEED` to every window |

That is the whole item. The signature is already `generate_event(sector, seq,
stream=..., force_val=...)`, so nothing else changes.

Three lines. No design decisions left.

**Done when:** `python -m sensor.main N --seed 42` emits the same sequence on
every run, and two sectors under the same seed differ.

**Size:** XS. **Owner:** B.

---

## 2. Duplicate suppression — requirement 3

> "Resolver condiciones de carrera, duplicación de eventos concurrentes y
> priorización de mensajes en el Servidor Central."

**Missing.** `SensorEvent.seq` is on the wire and unused. A retransmitted or
duplicated event is applied twice, which is harmless with today's binary cells
but wrong in principle and trivially checkable.

**Files to touch:**

| File | What to do |
|---|---|
| `ship/matrix.py` | keep `_last_seq: dict[SectorType, int]`; `apply()` returns `False` when `seq <= _last_seq[sector]`, before touching the board. `reset()` clears it. |
| `ship/server.py` | already ignores the return value; nothing to change unless a counter is wanted |

**Done when:**

- an event whose `seq` is `<=` the last one seen for that sector never reaches
  the board
- the drop is silent: no exception, no log line per event
- a test feeds `seq` 0, 1, 1, 2 and asserts the board reflects only 0, 1, 2
- a sector that reconnects and restarts at `seq` 0 is not silently frozen;
  decide this explicitly (recommendation: reset the counter when the socket for
  that sector closes, see `NodeRegistry`)

**Size:** S. **Owner:** A. **Status:** done.

Landed: `ThreatMatrix` tracks `_last_seq` per sector, `apply` returns `False`
for a stale or repeated `seq` before touching a cell, heartbeats advance the
sequence without writing, `forget()` clears one sector and `reset()` clears
all. Nine cases in `tests/test_matrix.py`, including the `seq` 0,1,1,2 walk.

---

## 3. Threat prioritization — requirement 3

Two mentions, no definition:

> "El Servidor Central debe procesar los eventos en paralelo, eliminar
> duplicados, **priorizar amenazas** y ejecutar maniobras de evasión."

> "Resolver condiciones de carrera, duplicación de eventos concurrentes y
> **priorización de mensajes** en el Servidor Central."

Neither source says what is prioritized or what happens when two events
conflict, so the ordering is a decision, not a discovery.

Without it, every event is applied the moment its thread takes the lock: eight
threads racing means two reports in the same millisecond land in either order,
and a run stops being reproducible even with a fixed seed.

**Files to touch:**

| File | What to do |
|---|---|
| `ship/server.py` | workers enqueue events instead of applying them; one ticker thread drains the queue every `TICK_SECONDS`, sorts the batch deterministically, applies it, then asks the dashboard to redraw |
| `ship/config.py` | add `TICK_SECONDS` (start with 0.1) |
| `ship/matrix.py` | unchanged; it keeps its lock and stays the only mutator |

**Ordering rule:** `(type, cell, seq)` — detections before heartbeats, then
grid order from `SECTOR_MAP`, then the sector's own sequence.

**Done when:**

- the board for a given set of events is identical across repeated runs
- a burst of 80 events applied through the queue gives the same board as
  applying them sorted
- heartbeats never delay a detection within a tick
- the dashboard still redraws at a readable rate
- the rule is recorded in `ARCHITECTURE.md` §10

**Size:** M. **Owner:** A. **Status:** done.

Landed: workers push to a `queue.Queue`, one ticker thread drains it every
`TICK_SECONDS`, sorts by `order_key` and applies the batch, then repaints once.
`ShipServer.drain()` is callable directly, which is what the tests use.
`order_key` is exported so tests can assert the ordering itself.

`tests/test_prioritization.py` shuffles the same batch ten ways and asserts the
board never changes, plus one refresh per tick rather than one per event.

---

## 4. Heartbeats and inactivity timeout — requirement 4

> "Garantizar tolerancia a fallas mediante detección de desconexiones
> (heartbeats) y reconfiguración dinámica de cobertura."

**Missing.** `SensorEvent` carries `type: "HEARTBEAT"` and `ThreatMatrix.apply`
already ignores it, but **no sensor emits one** and the ship has no timer. A
sensor that dies without closing the socket is never marked offline.

**Files to touch:**

| File | What to do |
|---|---|
| `sensor/main.py` | send a `HEARTBEAT` every `HEARTBEAT_INTERVAL`, whether or not it has a detection to report. Do not use `time.sleep(delay)` alone; wake up for whichever comes first. |
| `ship/config.py` | add `HEARTBEAT_INTERVAL` and `NODE_TIMEOUT` (`3 x HEARTBEAT_INTERVAL`) |
| `ship/registry.py` | record `last_seen` per sector on every message of any type; add `expire(now) -> set[SectorType]` |
| `ship/server.py` | call `registry.expire()` on the tick from item 3; drop expired sectors from `online` and tell the dashboard |

**Done when:**

- a sensor sends a heartbeat every interval even with no detection
- a sector is marked offline after `NODE_TIMEOUT` with no message of any kind
- a heartbeated sector returns online without reconnecting
- a sensor killed with `SIGKILL`, socket left open, goes offline within the
  timeout
- **a sector marked offline keeps its last cell.** Silence is not a zero. This
  is the current behaviour.

**Size:** M. **Owner:** B.

---

## 5. Coverage reporting — requirement 4

> "…reconfiguración dinámica de cobertura."

**Missing.** When a sector goes offline its cell freezes, which is right, but
nothing reports which sectors are uncovered.

**Files to touch:**

| File | What to do |
|---|---|
| `ship/registry.py` | `uncovered() -> set[SectorType]` alongside `online()` |
| `ship/console.py` | show the count in the sensor panel header and mark the cell of an offline sector differently from a fresh `0` |

**Done when:**

- the board distinguishes "no reading" from "read 0", which the matrix already
  does by keeping the value
- the dashboard shows how many sectors are uncovered
- the ship never treats a frozen cell as a fresh confirmation
- the demo can kill a sensor and show the coverage count drop by one

**Size:** S. **Owner:** B.

---

## 6. Aliens — requirement 5

> "Suponer que los sensores pueden ser controlados por aliens y pueden fallar."

**Missing.** `origin: "alien"` is on the wire and the ship ignores it.
`grep origin ship/` returns nothing.

**Files to touch:**

| File | What to do |
|---|---|
| `sensor/main.py` | `--alien` flag; with it the sensor occasionally reports a value its own world did not produce, and sets `origin="alien"` on those. A writes this too, since it pairs with the detector side. |
| `ship/detector.py` | ignore or down-weight sectors whose events arrived with `origin="alien"`; a single alien sector must not raise RED_ALERT alone |
| `ship/console.py` | mark the node as suspect rather than hiding it |

**Done when:**

- a sensor started with `--alien` injects wrong values
- the ship does not let one alien sector raise RED_ALERT on its own
- a legitimate detection from that same sector still counts
- the dashboard shows the node as suspect
- honest nodes are unaffected with no alien present

Scope: survive a lying sensor, not reach Byzantine agreement.

**Size:** M. **Owner:** A. **Status:** done.

Landed: `ThreatMatrix` records alien-flagged sectors in `_suspect` and never
writes their cell; `suspect()` exposes the set; `forget()` clears it on
reconnect. `sensor/main.py` grew `--alien`, which flips the value with
`ALIEN_LIE_PROBABILITY` and tags the event `origin="alien"`. The dashboard
marks a suspect node with a magenta `▲` and counts them in the panel title,
and `ShipServer.drain()` pushes the suspect set alongside the online set.

`tests/test_aliens.py` proves a single captured node cannot raise RED_ALERT,
that an honest event from a suspect sector still counts, and that the sequence
still advances so a discarded lie cannot be replaced by a stale replay.

---

## 7. Demo video — 25 points

Not code, but the largest single block of the grade.

**Content, in order:**

1. `./start.sh`, ship window showing the board redrawing
2. switch to a sensor window showing `val=0/1` lines
3. force the five given states with
   `python -m sensor.main <SECTOR> --val 1 --once` and show the banner change
4. kill one sensor and show it going offline without disturbing the rest
5. one sentence on the architecture: eight clients, one server, one lock

**Size:** S to record, M to get clean. **Owner:** both.

---

## Not planned

- WebSocket dashboard (`ship/hub.py`, `ship/ws_bridge.py`). No rubric line
  mentions a browser. The TUI already satisfies "ejecución y video". Do this
  only if there is time left after the items above.
- Authentication on the landing. Not required.
