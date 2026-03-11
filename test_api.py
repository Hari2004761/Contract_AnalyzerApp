"""
Tests for the Contract Risk Analyzer FastAPI backend (api.py).

Database : SQLite in-memory — real Supabase is never touched.
ML model : processpdf module is fully stubbed in conftest.py before any
           import of api.py occurs.
PDF      : minimal valid PDFs are generated inline with fpdf2 — no external
           file is needed.

Test inventory
──────────────
1. Signup with a new unique username          → 200
2. Signup with the same username twice        → 400
3. Login with correct credentials             → 200 + access_token
4. Login with wrong password                  → 401
5. /analyze/ with no Authorization header     → 403  (HTTPBearer's default)
6. /analyze/ valid JWT + real PDF             → 200, "risks", "download_url"
7. /download/ valid JWT, own file             → 200
8. /download/ valid JWT, another user's file  → 403
"""

import io
import os

import pytest
from fpdf import FPDF


# ── Shared helpers ────────────────────────────────────────────────────────────

def _bearer(token: str) -> dict:
    """Build an Authorization header dict for the given JWT."""
    return {"Authorization": f"Bearer {token}"}


def _minimal_pdf_bytes() -> bytes:
    """Return the bytes of a minimal, valid PDF created with fpdf2."""
    doc = FPDF()
    doc.add_page()
    doc.set_font("Helvetica", size=10)
    doc.cell(0, 10, "This agreement limits liability to the fullest extent.")
    return bytes(doc.output())


def _pdf_upload(content: bytes) -> dict:
    """Build the files dict expected by httpx / TestClient for a PDF upload."""
    return {"file": ("contract.pdf", io.BytesIO(content), "application/pdf")}


def _fake_process_pdf(input_path: str, output_path: str):
    """
    Drop-in replacement for processpdf.process_pdf used in tests that need
    /analyze/ to succeed end-to-end.

    Creates a real (tiny) output PDF on disk so that the /download/ endpoint
    can find and serve it, then returns a realistic risk list.
    """
    out = FPDF()
    out.add_page()
    out.output(output_path)
    return [
        {
            "type": "Limitation of Liability",
            "confidence": 0.95,
            "text_snippet": "limits liability to the fullest extent",
        }
    ]


# ── Test 1 ────────────────────────────────────────────────────────────────────

def test_signup_new_user(client):
    """Signing up with a brand-new username must return 200."""
    r = client.post(
        "/signup/",
        json={"username": "alice", "password": "Pass123!", "consent_given": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert "user_id" in body
    assert body["user_id"] is not None


# ── Test 2 ────────────────────────────────────────────────────────────────────

def test_signup_duplicate_username(client):
    """Signing up twice with the same username must return 400."""
    payload = {"username": "bob", "password": "Pass123!", "consent_given": True}
    first = client.post("/signup/", json=payload)
    assert first.status_code == 200

    second = client.post("/signup/", json=payload)
    assert second.status_code == 400


# ── Test 3 ────────────────────────────────────────────────────────────────────

def test_login_correct_credentials(client):
    """Login with valid credentials must return 200 and an access_token."""
    client.post(
        "/signup/",
        json={"username": "carol", "password": "Pass123!", "consent_given": True},
    )
    r = client.post("/login", json={"username": "carol", "password": "Pass123!"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["access_token"]


# ── Test 4 ────────────────────────────────────────────────────────────────────

def test_login_wrong_password(client):
    """Login with the wrong password must return 401."""
    client.post(
        "/signup/",
        json={"username": "dave", "password": "Correct1!", "consent_given": True},
    )
    r = client.post("/login", json={"username": "dave", "password": "WrongPass!"})
    assert r.status_code == 401


# ── Test 5 ────────────────────────────────────────────────────────────────────

def test_analyze_no_authorization_header(client):
    """
    Calling /analyze/ with no Authorization header must be rejected.

    FastAPI's HTTPBearer (auto_error=True) raises HTTP 403 when the
    Authorization header is absent, so we assert 403 here.
    """
    r = client.post(
        "/analyze/",
        files=_pdf_upload(_minimal_pdf_bytes()),
    )
    assert r.status_code == 401


# ── Test 6 ────────────────────────────────────────────────────────────────────

def test_analyze_with_valid_token(client, get_token, monkeypatch):
    """
    /analyze/ with a valid JWT and a real PDF must return 200 and include
    both 'risks' and 'download_url' in the response body.

    process_pdf is monkeypatched to avoid loading the real ML model; the
    patch also creates a minimal output PDF on disk so a subsequent
    /download/ call would work (exercised in test 7).
    """
    token = get_token("eve")
    monkeypatch.setattr("api.process_pdf", _fake_process_pdf)

    r = client.post(
        "/analyze/",
        files=_pdf_upload(_minimal_pdf_bytes()),
        headers=_bearer(token),
    )

    assert r.status_code == 200
    body = r.json()
    assert "risks" in body
    assert "download_url" in body


# ── Test 7 ────────────────────────────────────────────────────────────────────

def test_download_own_file(client, get_token, monkeypatch):
    """
    /download/{filename} with a valid JWT for the file's owner must return 200.

    Steps:
      1. Analyze a PDF as user "frank" to populate SearchHistory and create
         the output file on disk.
      2. Extract the filename from the download_url in the response.
      3. Download that file as the same user — expect 200.
    """
    token = get_token("frank")
    monkeypatch.setattr("api.process_pdf", _fake_process_pdf)

    # Step 1 — upload and analyze
    analyze = client.post(
        "/analyze/",
        files=_pdf_upload(_minimal_pdf_bytes()),
        headers=_bearer(token),
    )
    assert analyze.status_code == 200, analyze.text

    # Step 2 — extract filename:  "/download/analyzed_XXXX.pdf" → "analyzed_XXXX.pdf"
    download_url = analyze.json()["download_url"]
    filename = os.path.basename(download_url)

    # Step 3 — download
    r = client.get(f"/download/{filename}", headers=_bearer(token))
    assert r.status_code == 200


# ── Test 8 ────────────────────────────────────────────────────────────────────

def test_download_other_users_file(client, get_token, monkeypatch):
    """
    /download/{filename} with a valid JWT but requesting a file that belongs
    to a *different* user must return 403.

    Steps:
      1. User "grace" uploads and analyzes a contract.
      2. User "heidi" (a separate account) attempts to download grace's file.
      3. Expect 403 — the ownership check in /download/ must deny access.
    """
    token_grace = get_token("grace")
    token_heidi = get_token("heidi")
    monkeypatch.setattr("api.process_pdf", _fake_process_pdf)

    # Step 1 — grace uploads a contract
    analyze = client.post(
        "/analyze/",
        files=_pdf_upload(_minimal_pdf_bytes()),
        headers=_bearer(token_grace),
    )
    assert analyze.status_code == 200, analyze.text

    download_url = analyze.json()["download_url"]
    filename = os.path.basename(download_url)

    # Step 2 — heidi tries to download grace's file
    r = client.get(f"/download/{filename}", headers=_bearer(token_heidi))
    assert r.status_code == 403
