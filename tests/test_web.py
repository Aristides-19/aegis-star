"""Landing: the form is served, valid addresses are stored, bad ones are not."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web import main


@pytest.fixture(autouse=True)
def temp_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the module at a throwaway file so the real one is never touched."""
    target = tmp_path / "users.csv"
    monkeypatch.setattr(main, "CSV_PATH", target)
    return target


def rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def test_landing_is_served() -> None:
    with TestClient(main.app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert 'name="email"' in response.text


def test_valid_address_is_stored(temp_csv: Path) -> None:
    with TestClient(main.app) as client:
        response = client.post("/register", data={"email": "a@b.com"})

    assert response.status_code == 200
    assert "en la lista" in response.text

    content = rows(temp_csv)
    assert content[0] == ["email", "timestamp"]
    assert content[1][0] == "a@b.com"
    assert content[1][1]


@pytest.mark.parametrize("bad", ["not-an-email", "a@", "@b.com", ""])
def test_invalid_address_is_not_stored(temp_csv: Path, bad: str) -> None:
    with TestClient(main.app) as client:
        response = client.post("/register", data={"email": bad})

    assert response.status_code == 422
    assert rows(temp_csv) == []


def test_second_row_does_not_overwrite_the_first(temp_csv: Path) -> None:
    with TestClient(main.app) as client:
        client.post("/register", data={"email": "one@a.com"})
        client.post("/register", data={"email": "two@a.com"})

    addresses = [row[0] for row in rows(temp_csv)[1:]]
    assert addresses == ["one@a.com", "two@a.com"]
