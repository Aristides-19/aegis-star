# PENDING

What delivery 2 still needs, taken from the assignment and checked against the
code. Nothing here changes the detection rule or the contracts in
[`CONTRACTS.md`](CONTRACTS.md).

## How the work is split

Serial, not parallel: **A finishes before B starts.** That removes the merge
risk on `sensor/main.py` and `ship/server.py`, which both sides would otherwise
touch at the same time.

The split is deliberately lopsided. B's three items are the ones that need the
least judgement: one is wiring that A writes in advance, the other two are
small additions to files that already have the shape they need. A keeps
everything that requires a design decision.

| Order | Item | Who | Files |
|---|---|---|---|
| 1st | 2. Duplicate suppression | A | `ship/matrix.py` |
| 2nd | 3. Threat prioritization | A | `ship/server.py`, `ship/config.py` |
| 3rd | 1. Shared-seed PRNG (library) | A | `common/rng.py` (new), `sensor/world.py`, `start.sh` |
| 4th | 6. Aliens | A | `ship/detector.py`, `ship/console.py`, `sensor/main.py` |
| 5th | 1. Shared-seed PRNG (wiring) | B | `sensor/main.py` |
| 6th | 5. Coverage reporting | B | `ship/registry.py`, `ship/console.py` |
| 7th | 4. Heartbeats and timeout | B | `sensor/main.py`, `ship/registry.py`, `ship/server.py`, `ship/config.py` |
| — | 7. Demo video | both | — |

**Why B's items are easy.** A lands `common/rng.py` complete with tests before B
starts, so B's PRNG work is changing one call in `world.py` and three lines in
`main.py`. Coverage is a `set` built from state `registry.py` already tracks.
Heartbeats reuse the tick A introduces for prioritization, so the timer loop
already exists.

**Why A takes aliens.** It is the only item with no recipe: the assignment says
sensors may be "controlled by aliens" and stops there. Deciding what counts as
a lie, and how much of the board one lying node can move, is a judgement call
and belongs to whoever can make it fastest.

**Dependency chain.** Prioritization introduces the tick; heartbeats expire on
that same tick; dedup keeps `seq` monotone, which is what makes a seeded replay
match. So A's three items come first, in that order.

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

**Size:** S. **Owner:** A.

### 1b. The wiring — B

A hands over `common/rng.py`, `SEED` in config, and `generate_event` taking a
`Random`. B only connects `sensor/main.py` to it.

| File | What to do |
|---|---|
| `sensor/main.py` | read the seed from the CLI (`--seed`) defaulting to `config.SEED`, call `stream_for(seed, sector)` once before the loop, pass the result into `generate_event` |

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

**Size:** S. **Owner:** A.

---

## 3. Threat prioritization — requirement 3

**What the assignment says, and nothing more.** Two mentions, no definition:

> "El Servidor Central debe procesar los eventos en paralelo, eliminar
> duplicados, **priorizar amenazas** y ejecutar maniobras de evasión."

> "Resolver condiciones de carrera, duplicación de eventos concurrentes y
> **priorización de mensajes** en el Servidor Central."

Neither the assignment nor the rubric says what is prioritized, by what
criterion, or what happens when two events conflict. This item is therefore a
design decision that has to be written down, not discovered.

**The problem it addresses.** Today every event is applied the moment its
thread takes the lock. Eight threads racing means the board depends on thread
scheduling: two sectors reporting in the same millisecond can land in either
order, and a run is not reproducible even with a fixed seed.

**Files to touch:**

| File | What to do |
|---|---|
| `ship/server.py` | workers enqueue events instead of applying them; one ticker thread drains the queue every `TICK_SECONDS`, sorts the batch deterministically, applies it, then asks the dashboard to redraw |
| `ship/config.py` | add `TICK_SECONDS` (start with 0.1) |
| `ship/matrix.py` | unchanged; it keeps its lock and stays the only mutator |

**Ordering rule to implement:** sort a tick by `(priority, sector, seq)`, where
`priority` is `1` for `DETECTION` and `0` for `HEARTBEAT`, and `sector` is the
canonical order from `SECTOR_MAP` so the result is stable. Detections are
applied before heartbeats, and within detections the sector name breaks ties.

**Done when:**

- the board for a given set of events is identical across repeated runs
- a burst of 80 events applied through the queue gives the same board as
  applying them sorted
- heartbeats never delay a detection within a tick
- the dashboard still redraws at a readable rate
- the chosen rule is written in `ARCHITECTURE.md` §10, because it is a
  judgement call the defence will ask about

**Size:** M. **Owner:** A.

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
  is the current behaviour and must not change.

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

Keep it bounded: the assignment asks the system to survive a lying sensor, not
to build Byzantine agreement.

**Size:** M. **Owner:** A.

---

## 7. Demo video — 25 points

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

## Not planned

- WebSocket dashboard (`ship/hub.py`, `ship/ws_bridge.py`). No rubric line
  mentions a browser. The TUI already satisfies "ejecución y video". Do this
  only if there is time left after the items above.
- Authentication on the landing. Not in the assignment.
