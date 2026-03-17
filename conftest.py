"""
Shared pytest fixtures for the Contract Risk Analyzer test suite.

Key design decisions
────────────────────
* All env-var overrides and sys.modules stubs happen at *module import time*
  (top of this file, before any app code is imported) so that:
    - database.py never tries to connect to Supabase
    - api.py never loads the GPU model from processpdf.py
* The real get_db dependency is overridden per-test with a TestClient
  dependency override that injects an isolated SQLite in-memory session.
* Tables are created fresh for every test and dropped at teardown, giving
  full isolation without needing database transactions or savepoints.
"""

import glob as _glob
import os
import sys
from unittest.mock import MagicMock, patch

# ── 1. Env-var overrides (must come before any app import) ───────────────────
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key-for-tests-only"

# ── 2. Stub processpdf so the ML model is never loaded ───────────────────────
_processpdf_stub = MagicMock()
_processpdf_stub.process_pdf.return_value = []
sys.modules.setdefault("processpdf", _processpdf_stub)

# ── 3. Normal imports (after the stubs are in place) ─────────────────────────
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from database import Base
from api import app, get_db

# ── 4. Isolated SQLite in-memory test database ───────────────────────────────
_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(
    bind=_TEST_ENGINE,
    autocommit=False,
    autoflush=False,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _fresh_tables():
    """Create all ORM tables before each test; drop them (and orphan files) after."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    yield
    Base.metadata.drop_all(bind=_TEST_ENGINE)
    # Clean up any analyzed_*.pdf / temp_*.pdf files left on disk by tests
    for pattern in ("analyzed_*.pdf", "temp_*.pdf"):
        for path in _glob.glob(pattern):
            try:
                os.remove(path)
            except OSError:
                pass


@pytest.fixture()
def db_session(_fresh_tables):
    """Yield a fresh SQLAlchemy session bound to the test database."""
    session = _TestSession()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    """
    Return a FastAPI TestClient whose get_db dependency is overridden so that
    every endpoint uses the isolated test session instead of Supabase.
    """
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def get_token(client):
    """
    Factory fixture.  Returns a helper function that registers a new user
    and gives back their JWT bearer token string.

    Usage inside a test::

        def test_something(client, get_token):
            token = get_token("alice")
    """
    def _get_token(username: str, password: str = "Password1!") -> str:
        r = client.post(
            "/signup/",
            json={"username": username, "password": password, "consent_given": True},
        )
        assert r.status_code == 200, f"Signup failed: {r.text}"
        r = client.post(
            "/login",
            json={"username": username, "password": password},
        )
        assert r.status_code == 200, f"Login failed: {r.text}"
        return r.json()["access_token"]

    return _get_token


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    with patch("slowapi.Limiter._check_request_limit"):
        yield
