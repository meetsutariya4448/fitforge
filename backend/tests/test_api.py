"""
Integration tests for the FitForge REST API.

Each test runs against a real PostgreSQL database. In CI the database is
provided as a Postgres 16 service container and the schema is applied via
  alembic upgrade head
before pytest runs.

Required environment variables (set automatically in CI):
  DATABASE_URL  — test Postgres connection string
  SECRET_KEY    — for JWT signing/verification
  GROQ_API_KEY  — placeholder; the Groq client is monkeypatched in every
                   test that touches /api/workout/generate

Isolation strategy: every test registers a fresh user with a unique email
(uuid4 suffix) so tests are independent and order-insensitive regardless of
whether database rows accumulate across tests.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from app.config import settings


# ── Helpers ───────────────────────────────────────────────────────────────────

def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _register(client, *, email: str = None, password: str = "Password1!", name: str = "Test User"):
    """Register a fresh account; return (access_token, refresh_token, email)."""
    email = email or f"user_{_uid()}@test.com"
    r = client.post(
        "/api/auth/register",
        json={"email": email, "name": name, "password": password},
    )
    assert r.status_code == 201, r.text
    data = r.json()
    return data["access_token"], data["refresh_token"], email


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _expired_token(user_id: int = 1) -> str:
    """Craft a syntactically valid JWT whose expiry is in the past."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        "iat": datetime.now(timezone.utc) - timedelta(hours=1),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


# Reusable payloads ────────────────────────────────────────────────────────────

_ONBOARDING = {
    "name": "CI Tester",
    "age": 28,
    "fitness_goal": "build_muscle",
    "fitness_level": "beginner",
    "available_equipment": ["dumbbells"],
    "days_per_week": 3,
}

_SESSION = {
    "day_name": "Day 1",
    "notes": "CI test session",
    "plan_id": None,
    "exercise_logs": [
        {
            "exercise_name": "Squat",
            "sets_completed": 3,
            "reps_completed": 10,
            "weight_kg": 80.0,
        }
    ],
}


# ── GET /health ───────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_ok(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ── POST /api/auth/register ───────────────────────────────────────────────────

class TestRegister:
    def test_success_returns_tokens_and_user(self, client):
        email = f"reg_{_uid()}@test.com"
        r = client.post(
            "/api/auth/register",
            json={"email": email, "name": "Alice", "password": "Password1!"},
        )
        assert r.status_code == 201
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["user"]["email"] == email

    def test_duplicate_email_returns_409(self, client):
        email = f"dup_{_uid()}@test.com"
        client.post("/api/auth/register", json={"email": email, "name": "A", "password": "Password1!"})
        r = client.post("/api/auth/register", json={"email": email, "name": "B", "password": "Password1!"})
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "CONFLICT"

    def test_short_password_returns_422(self, client):
        r = client.post("/api/auth/register", json={
            "email": f"p_{_uid()}@test.com", "name": "X", "password": "abc",
        })
        assert r.status_code == 422

    def test_missing_name_returns_422(self, client):
        r = client.post("/api/auth/register", json={
            "email": f"n_{_uid()}@test.com", "password": "Password1!",
        })
        assert r.status_code == 422


# ── POST /api/auth/login ──────────────────────────────────────────────────────

class TestLogin:
    def test_success_returns_tokens(self, client):
        _, _, email = _register(client)
        r = client.post("/api/auth/login", json={"email": email, "password": "Password1!"})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_wrong_password_returns_401(self, client):
        _, _, email = _register(client)
        r = client.post("/api/auth/login", json={"email": email, "password": "WrongPass1!"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHORIZED"

    def test_unknown_email_returns_401(self, client):
        r = client.post("/api/auth/login", json={
            "email": f"nobody_{_uid()}@test.com", "password": "Password1!",
        })
        assert r.status_code == 401


# ── GET /api/auth/me ──────────────────────────────────────────────────────────

class TestMe:
    def test_valid_token_returns_user(self, client):
        token, _, email = _register(client)
        r = client.get("/api/auth/me", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["email"] == email

    def test_no_token_returns_401(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401

    def test_malformed_token_returns_401(self, client):
        r = client.get("/api/auth/me", headers=_auth("this.is.not.a.jwt"))
        assert r.status_code == 401

    def test_expired_token_returns_401(self, client):
        # _decode_token raises JWTError for expired tokens → 401 before DB lookup
        r = client.get("/api/auth/me", headers=_auth(_expired_token()))
        assert r.status_code == 401


# ── POST /api/auth/refresh ────────────────────────────────────────────────────

class TestRefresh:
    def test_valid_refresh_returns_new_tokens(self, client):
        _, refresh, _ = _register(client)
        r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "refresh_token" in body

    def test_replayed_token_returns_401(self, client):
        _, refresh, _ = _register(client)
        # First rotation succeeds
        r1 = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r1.status_code == 200
        # Replaying the old (now-revoked) token must fail — strict rotation
        r2 = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r2.status_code == 401

    def test_garbage_token_returns_401(self, client):
        r = client.post("/api/auth/refresh", json={"refresh_token": "not-a-real-token"})
        assert r.status_code == 401


# ── POST /api/auth/logout ─────────────────────────────────────────────────────

class TestLogout:
    def test_revokes_refresh_token(self, client):
        _, refresh, _ = _register(client)
        r = client.post("/api/auth/logout", json={"refresh_token": refresh})
        assert r.status_code == 204
        # Revoked token must no longer rotate
        r2 = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert r2.status_code == 401


# ── DELETE /api/auth/me ───────────────────────────────────────────────────────

class TestDeleteAccount:
    def test_correct_password_deletes_account(self, client):
        token, _, _ = _register(client)
        r = client.request(
            "DELETE", "/api/auth/me",
            json={"password": "Password1!"},
            headers=_auth(token),
        )
        assert r.status_code == 204
        # The deleted user's token should no longer authenticate
        r2 = client.get("/api/auth/me", headers=_auth(token))
        assert r2.status_code == 401

    def test_wrong_password_does_not_delete(self, client):
        token, _, _ = _register(client)
        r = client.request(
            "DELETE", "/api/auth/me",
            json={"password": "WrongPassword!"},
            headers=_auth(token),
        )
        assert r.status_code == 401
        # Account should still exist
        r2 = client.get("/api/auth/me", headers=_auth(token))
        assert r2.status_code == 200


# ── POST /api/workout/generate ────────────────────────────────────────────────

class TestGenerate:
    def test_success_returns_plan(self, client, mock_groq):
        token, _, _ = _register(client)
        r = client.post("/api/workout/generate", json=_ONBOARDING, headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True
        assert "title" in body["plan"]

    def test_unauthenticated_returns_401(self, client, mock_groq):
        r = client.post("/api/workout/generate", json=_ONBOARDING)
        assert r.status_code == 401

    def test_groq_error_returns_5xx(self, client, monkeypatch):
        """When the Groq client raises, the route must return 500 or 502 gracefully."""
        from app.services.retrieval_service import RetrievalResult

        class _FailCompletions:
            def create(self, **kw):
                raise Exception("Groq API unavailable")

        class _FailChat:
            completions = _FailCompletions()

        class _FailClient:
            chat = _FailChat()

        monkeypatch.setattr("app.services.ai_service._client", _FailClient())
        monkeypatch.setattr(
            "app.services.retrieval_service.retrieve",
            lambda *a, **kw: RetrievalResult(
                chunks=[], scores=[], low_confidence=True, retrieval_mode="hybrid"
            ),
        )
        token, _, _ = _register(client)
        r = client.post("/api/workout/generate", json=_ONBOARDING, headers=_auth(token))
        assert r.status_code in (500, 502)


# ── GET /api/workout/history ──────────────────────────────────────────────────

class TestHistory:
    def test_empty_history(self, client):
        token, _, _ = _register(client)
        r = client.get("/api/workout/history", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["plans"] == []
        assert body["next_cursor"] is None

    def test_cursor_pagination(self, client, mock_groq):
        token, _, _ = _register(client)
        for _ in range(3):
            client.post("/api/workout/generate", json=_ONBOARDING, headers=_auth(token))

        # Page 1: limit=2
        r1 = client.get("/api/workout/history?limit=2", headers=_auth(token))
        assert r1.status_code == 200
        page1 = r1.json()
        assert len(page1["plans"]) == 2
        assert page1["next_cursor"] is not None

        # Page 2: must be the remaining 1 plan with no further cursor
        cursor = page1["next_cursor"]
        r2 = client.get(f"/api/workout/history?limit=2&cursor={cursor}", headers=_auth(token))
        assert r2.status_code == 200
        page2 = r2.json()
        assert len(page2["plans"]) == 1
        assert page2["next_cursor"] is None


# ── POST /api/sessions ────────────────────────────────────────────────────────

class TestSessions:
    def test_create_session_returns_201(self, client):
        token, _, _ = _register(client)
        r = client.post("/api/sessions", json=_SESSION, headers=_auth(token))
        assert r.status_code == 201
        body = r.json()
        assert "id" in body
        assert len(body["exercise_logs"]) == 1

    def test_first_log_creates_pr(self, client):
        token, _, _ = _register(client)
        client.post("/api/sessions", json=_SESSION, headers=_auth(token))
        prs = client.get("/api/prs", headers=_auth(token)).json()
        assert len(prs) == 1
        assert prs[0]["exercise_name"] == "Squat"
        assert prs[0]["max_weight_kg"] == 80.0
        assert prs[0]["max_reps"] == 10

    def test_higher_weight_updates_pr(self, client):
        token, _, _ = _register(client)
        client.post("/api/sessions", json=_SESSION, headers=_auth(token))
        heavy = {**_SESSION, "exercise_logs": [
            {"exercise_name": "Squat", "sets_completed": 3, "reps_completed": 10, "weight_kg": 100.0}
        ]}
        client.post("/api/sessions", json=heavy, headers=_auth(token))
        prs = client.get("/api/prs", headers=_auth(token)).json()
        squat = next(p for p in prs if p["exercise_name"] == "Squat")
        assert squat["max_weight_kg"] == 100.0

    def test_equal_weight_does_not_update_pr(self, client):
        """PR uses strict greater-than — an equal weight must NOT update the record."""
        token, _, _ = _register(client)
        client.post("/api/sessions", json=_SESSION, headers=_auth(token))  # sets PR at 80 kg
        same = {**_SESSION, "exercise_logs": [
            {"exercise_name": "Squat", "sets_completed": 3, "reps_completed": 10, "weight_kg": 80.0}
        ]}
        client.post("/api/sessions", json=same, headers=_auth(token))
        prs = client.get("/api/prs", headers=_auth(token)).json()
        squat = next(p for p in prs if p["exercise_name"] == "Squat")
        assert squat["max_weight_kg"] == 80.0  # unchanged

    def test_missing_exercise_logs_returns_422(self, client):
        token, _, _ = _register(client)
        r = client.post("/api/sessions", json={"day_name": "Day 1"}, headers=_auth(token))
        assert r.status_code == 422

    def test_list_sessions_returns_only_own(self, client):
        """User B must see an empty list; user A's sessions are not leaked."""
        token_a, _, _ = _register(client)
        token_b, _, _ = _register(client)
        client.post("/api/sessions", json=_SESSION, headers=_auth(token_a))
        r = client.get("/api/sessions", headers=_auth(token_b))
        assert r.status_code == 200
        assert r.json() == []

    def test_get_session_by_id(self, client):
        token, _, _ = _register(client)
        created = client.post("/api/sessions", json=_SESSION, headers=_auth(token)).json()
        r = client.get(f"/api/sessions/{created['id']}", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_nonexistent_session_returns_404(self, client):
        token, _, _ = _register(client)
        r = client.get("/api/sessions/999999999", headers=_auth(token))
        assert r.status_code == 404

    def test_other_users_session_returns_403(self, client):
        """Authorization boundary: user B cannot read user A's session."""
        token_a, _, _ = _register(client)
        token_b, _, _ = _register(client)
        session_a = client.post("/api/sessions", json=_SESSION, headers=_auth(token_a)).json()
        r = client.get(f"/api/sessions/{session_a['id']}", headers=_auth(token_b))
        assert r.status_code == 403


# ── GET /api/sessions/exercise/{name} ─────────────────────────────────────────

class TestExerciseTrend:
    def test_returns_trend_after_logging(self, client):
        token, _, _ = _register(client)
        client.post("/api/sessions", json=_SESSION, headers=_auth(token))
        r = client.get("/api/sessions/exercise/Squat", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["exercise_name"] == "Squat"
        assert len(body["data"]) == 1
        assert body["data"][0]["max_weight_kg"] == 80.0

    def test_unknown_exercise_returns_empty(self, client):
        token, _, _ = _register(client)
        r = client.get("/api/sessions/exercise/DoesNotExist", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["data"] == []


# ── GET /api/prs ──────────────────────────────────────────────────────────────

class TestPRs:
    def test_returns_only_own_prs(self, client):
        """Authorization boundary: user B must not see user A's personal records."""
        token_a, _, _ = _register(client)
        token_b, _, _ = _register(client)
        client.post("/api/sessions", json=_SESSION, headers=_auth(token_a))
        r = client.get("/api/prs", headers=_auth(token_b))
        assert r.status_code == 200
        assert r.json() == []
