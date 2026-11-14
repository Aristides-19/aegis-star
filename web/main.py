"""Landing page for Aegis-Star 8-Sector."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

ROOT = Path(__file__).parent

app = FastAPI(title="Aegis-Star 8-Sector")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.main:app", host="127.0.0.1", port=8080, reload=True)


__all__ = ["app"]
