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

## Estructura

```text
common/   contratos congelados (protocolo, sectores, framing)
ship/     nave: servidor TCP, matriz 3x3, lógica de alertas
sensor/   clientes: generan y envían detecciones
tests/    regla de decisión + concurrencia
```

Reglas del protocolo y de la matriz: [`docs/CONTRACTS.md`](docs/CONTRACTS.md).
Visión general y reparto de trabajo: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
