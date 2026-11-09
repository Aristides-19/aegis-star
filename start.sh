#!/usr/bin/env bash
# Launch the ship and the eight sensors.
#
#   ./start.sh            tmux session "aegis" (9 windows)
#   ./start.sh -k         kill the running session
#   ./start.sh --plain    no tmux: ship in this terminal, sensors in background
#
# Environment (all optional, see ship/config.py):
#   AEGIS_PORT=6000 AEGIS_SENSOR_INTERVAL=0.5 AEGIS_DETECTION_PROBABILITY=0.1

set -euo pipefail

SESSION="${AEGIS_SESSION:-aegis}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${ROOT}/.venv/bin/python"
SENSORS=(NO N NE E SE S SO O)

if [[ ! -x "$PYTHON" ]]; then
  echo "No encuentro ${PYTHON}" >&2
  echo "Corre: uv sync" >&2
  exit 1
fi

kill_everything() {
  # Sessions can linger with clients still attached; detach first, then kill,
  # so tmux does not leave the panes running in the background.
  if command -v tmux >/dev/null 2>&1 && tmux has-session -t "$SESSION" 2>/dev/null; then
    tmux list-clients -t "$SESSION" 2>/dev/null \
      | awk '{print $1}' \
      | while read -r client; do tmux detach-client -t "$client" 2>/dev/null || true; done
    tmux kill-session -t "$SESSION" 2>/dev/null || true
  fi
  # Belt and braces: any stray process from a previous run, whatever the
  # session was called.
  pkill -f "[s]hip\.main" 2>/dev/null || true
  pkill -f "[s]ensor\.main" 2>/dev/null || true
}

MODE="tmux"
case "${1:-}" in
  -k|--kill)
    kill_everything
    echo "Sesión '$SESSION' y procesos detenidos."
    exit 0
    ;;
  --plain)
    MODE="plain"
    ;;
esac

# ---------------------------------------------------------------- plain mode
if [[ "$MODE" == "plain" ]]; then
  echo "Modo sin tmux: la nave corre aquí, los sensores en segundo plano."
  echo "Detener todo con Ctrl+C."
  echo

  pids=()
  cleanup() {
    echo
    echo "Deteniendo sensores..."
    for pid in "${pids[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    exit 0
  }
  trap cleanup INT TERM EXIT

  for sector in "${SENSORS[@]}"; do
    "$PYTHON" -u -m sensor.main "$sector" &
    pids+=($!)
  done
  echo "8 sensores lanzados. Sus logs: /tmp/aegis-sensor-<SECTOR>.log"
  echo

  # Sin pipe: con "| tee" stdout deja de ser un TTY y el dashboard pierde
  # el modo interactivo, cayendo al log de texto.
  "$PYTHON" -u -m ship.main 2> >(tee /tmp/aegis-ship.err.log >&2)
  exit 0
fi

# ---------------------------------------------------------------- tmux mode
if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux no está instalado." >&2
  echo >&2
  echo "  Instálalo:      sudo pacman -S tmux" >&2
  echo "  O sin tmux:     ./start.sh --plain" >&2
  exit 1
fi

# A previous run must not survive: two ships on the same port means the
# second one fails to bind and the panes silently die.
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Sesión '$SESSION' existente: reiniciando."
  kill_everything
  sleep 0.5
elif pgrep -f "[s]hip\.main" >/dev/null 2>&1; then
  # A ship from a --plain run or from a previous manual launch would make the
  # new one fail to bind the port.
  echo "Hay una nave corriendo fuera de tmux: deteniéndola."
  kill_everything
  sleep 0.5
fi

# One window per process: nine tiled panes are unreadable, and each sensor
# deserves a readable log.
tmux new-session -d -s "$SESSION" -c "$ROOT" -n ship \
  "$PYTHON -u -m ship.main 2> >(tee /tmp/aegis-ship.err.log >&2)"

for sector in "${SENSORS[@]}"; do
  tmux new-window -t "$SESSION" -c "$ROOT" -n "sensor-$sector" \
    "$PYTHON -u -m sensor.main $sector"
done

tmux select-window -t "$SESSION:ship"
tmux set-option -t "$SESSION" remain-on-exit on

echo "Sesión '$SESSION' lista."
echo "  Nave:     ventana 'ship'"
echo "  Sensores: ventanas 'sensor-NO' ... 'sensor-O'"
echo "  Adjuntar: tmux attach -t $SESSION"
echo "  Detener:  ./start.sh -k"
exec tmux attach -t "$SESSION"
