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

MODE="tmux"
case "${1:-}" in
  -k|--kill)
    if command -v tmux >/dev/null 2>&1; then
      tmux kill-session -t "$SESSION" 2>/dev/null || true
    fi
    pkill -f "sensor.main" 2>/dev/null || true
    echo "Sesión '$SESSION' detenida."
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
    "$PYTHON" -u -m sensor.main "$sector" > "/tmp/aegis-sensor-$sector.log" 2>&1 &
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

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "La sesión '$SESSION' ya existe. Usa ./start.sh -k para reiniciarla." >&2
  echo "Adjuntando..."
  exec tmux attach -t "$SESSION"
fi

# One window per process: nine tiled panes are unreadable, and each sensor
# deserves a readable log.
tmux new-session -d -s "$SESSION" -c "$ROOT" -n ship \
  "$PYTHON -u -m ship.main 2> >(tee /tmp/aegis-ship.err.log >&2)"

for sector in "${SENSORS[@]}"; do
  tmux new-window -t "$SESSION" -c "$ROOT" -n "sensor-$sector" \
    "$PYTHON -u -m sensor.main $sector > /tmp/aegis-sensor-$sector.log 2>&1"
done

tmux select-window -t "$SESSION:ship"
tmux set-option -t "$SESSION" remain-on-exit on

echo "Sesión '$SESSION' lista."
echo "  Nave:     ventana 'ship'"
echo "  Sensores: ventanas 'sensor-NO' ... 'sensor-O'"
echo "  Adjuntar: tmux attach -t $SESSION"
echo "  Detener:  ./start.sh -k"
exec tmux attach -t "$SESSION"
