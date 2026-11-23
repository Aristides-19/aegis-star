# Aegis-Star 8-Sector

Sistema distribuido en estrella: 8 sensores (clientes TCP) → nave (servidor) → dashboard.
Universidad Metropolitana · Sistemas Distribuidos.

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Instalar

```bash
uv sync
```

## Correr los tests

```bash
uv run pytest -q
```

## Arrancar

```bash
./start.sh --plain                      # nave + 8 sensores, sin tmux
./start.sh                              # lo mismo en 9 ventanas de tmux
uv run python -m sensor.main N          # un sensor suelto
```

El puerto es `5000`: la nave escucha, los sensores conectan.

### Windows (sin tmux)

Desde PowerShell, despues de `uv sync`:

```powershell
.\start.ps1                 # nave y ocho sensores en una ventana con nueve pestanas
.\start.ps1 -Stop           # detener la sesion completa (tambien admite -k)
$env:AEGIS_SEED = '42'       # opcional: repetir las secuencias de lecturas
.\start.ps1
```

Si Windows bloquea la ejecucion del script, puede ejecutarse sin cambiar la
politica permanente del equipo:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Stop
```

Requiere Windows Terminal (wt.exe), pero no tmux, WSL ni permisos de administrador. Cada pestana muestra un
proceso; cerrar una no detiene las otras. Usa `-Stop` antes de cerrar las
pestanas para detener todos sus procesos. Volver a ejecutar el lanzador
reinicia su sesion anterior. El archivo local `.aegis-processes.json` registra
los procesos de esta copia del proyecto; no se sube a Git. No borres ese archivo
mientras la sesion este activa. Las variables `AEGIS_*` se heredan en todos
los procesos, incluida la misma semilla.

## Estructura

```text
common/   contratos congelados (protocolo, sectores, framing)
ship/     nave: servidor TCP, matriz 3x3, lógica de alertas
sensor/   clientes: generan y envían detecciones
tests/    regla de decisión + concurrencia
```

Reglas del protocolo y de la matriz: [`docs/CONTRACTS.md`](docs/CONTRACTS.md).
Visión general y reparto de trabajo: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
