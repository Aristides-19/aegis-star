"""Landing page for Aegis-Star 8-Sector.

Two routes: the page, and the POST that records a visitor's email in
``users.csv``. Pydantic validates the address before anything is written, so
an invalid one never reaches the file.
"""

from __future__ import annotations

import csv
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, ValidationError

ROOT = Path(__file__).parent
CSV_PATH = ROOT / "users.csv"
CSV_HEADER = ("email", "timestamp")

#: Serializes appends: two requests can land in the same millisecond.
_CSV_LOCK = threading.Lock()

app = FastAPI(title="Aegis-Star 8-Sector")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")


class Subscriber(BaseModel):
    """One visitor. ``EmailStr`` rejects anything that is not an address."""

    email: EmailStr
    timestamp: datetime

    @classmethod
    def now(cls, email: str) -> Subscriber:
        return cls(email=email, timestamp=datetime.now(UTC))


def append_row(subscriber: Subscriber) -> None:
    """Append one row, writing the header if the file is new or empty."""
    with _CSV_LOCK:
        is_new = not CSV_PATH.exists() or CSV_PATH.stat().st_size == 0
        with CSV_PATH.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            if is_new:
                writer.writerow(CSV_HEADER)
            writer.writerow((subscriber.email, subscriber.timestamp.isoformat()))


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    return templates.TemplateResponse(request, "index.html", {"message": None})


@app.post("/register", response_class=HTMLResponse)
def register(request: Request, email: Annotated[str, Form()]) -> Response:
    try:
        subscriber = Subscriber.now(email)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"message": "Ese correo no parece válido."},
            status_code=422,
        )
    append_row(subscriber)
    return RedirectResponse("/thanks", status_code=303)


@app.get("/thanks", response_class=HTMLResponse)
def thanks(request: Request) -> Response:
    return templates.TemplateResponse(request, "thanks.html", {})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("web.main:app", host="127.0.0.1", port=8080, reload=True)


__all__ = ["app"]
