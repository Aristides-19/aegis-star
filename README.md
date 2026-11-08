# Aegis-Star 8-Sector

Sistema distribuido en estrella: 8 sensores (clientes TCP) → nave (servidor) → dashboard.
Universidad Metropolitana · Sistemas Distribuidos.

## Requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Instalar

```bash
uv venv                # crea .venv
uv pip install -r requirements.txt
```

## Correr los tests

```bash
uv run pytest -q
```

## Arrancar

```bash
./start.sh             # nave + 8 sensores en tmux
```

O a mano, en terminales separadas:

```bash
uv run python -m ship.main
uv run python -m sensor.main --sector N
```

## Estructura

```text
common/   contratos congelados (protocolo, sectores, framing)
ship/     nave: servidor TCP, matriz 3x3, lógica de alertas
sensor/   clientes: generan y envían detecciones
tests/    regla de decisión + concurrencia
```

Reglas del protocolo y de la matriz: [`docs/CONTRACTS.md`](docs/CONTRACTS.md).
