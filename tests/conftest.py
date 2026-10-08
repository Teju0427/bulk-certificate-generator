"""Test setup: SQLite database + temp storage; production uses PostgreSQL."""
import os
import tempfile
from pathlib import Path

# Must run BEFORE the app is imported, because the engine is created at import time.
_TEST_DIR = Path(tempfile.mkdtemp())
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'test.db'}"
os.environ["STORAGE_DIR"] = str(_TEST_DIR / "storage")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def temp_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", tmp_path / "certificates")
    return tmp_path / "certificates"


@pytest.fixture
def client() -> TestClient:
    # TestClient finishes BackgroundTasks before returning, so generation is done after POST.
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def make_payload():
    def _make(count: int = 2) -> dict:
        names = ["Alice Johnson", "Bob Smith", "Carol White", "David Brown", "Eve Davis"]
        recipients = [
            {"name": names[i % len(names)] + ("" if i < len(names) else f" {i}"), "email": f"user{i}@example.com"}
            for i in range(count)
        ]
        return {
            "event_name": "Python Workshop 2026",
            "certificate_title": "Certificate of Participation",
            "organization_name": "Aereo",
            "issue_date": "2026-10-08",
            "recipients": recipients,
        }

    return _make
