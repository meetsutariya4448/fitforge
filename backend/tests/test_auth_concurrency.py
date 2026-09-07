"""
Concurrency and replay tests for refresh-token rotation.

The property under test: redeeming a refresh token N times simultaneously
must leave the user with exactly ONE live replacement token, never N.

Before the atomic-claim fix, rotate_refresh_token read the row, checked
`revoked_at is None`, then wrote — so every racer passed the check before any
of them committed, and 8 concurrent redemptions of one token produced 5
successes and 5 independent live branches.

These tests need real PostgreSQL (row locking is the mechanism being tested);
they skip automatically when DATABASE_URL is unset, like the rest of the
integration suite.
"""

import threading
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services import auth_service
from app.services.auth_service import RefreshError, rotate_refresh_token


CONCURRENCY = 8


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sessions(_api_engine):
    """Factory for independent DB sessions — one per simulated request.

    The shared-session `db` fixture cannot express this test: a race between
    two requests requires two connections, since the race is resolved by
    PostgreSQL row locks.
    """
    factory = sessionmaker(bind=_api_engine)
    opened = []

    def _make():
        s = factory()
        opened.append(s)
        return s

    yield _make
    for s in opened:
        s.close()


@pytest.fixture
def user(sessions):
    s = sessions()
    u = User(
        name="Race Tester",
        email=f"race_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="not-a-real-hash",
    )
    s.add(u)
    s.commit()
    s.refresh(u)
    return u


def _live_tokens(session, user_id: int) -> list[RefreshToken]:
    return (
        session.query(RefreshToken)
        .filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .all()
    )


# ── The regression test ───────────────────────────────────────────────────────

class TestConcurrentRotation:
    def test_simultaneous_redemption_mints_exactly_one_replacement(self, sessions, user):
        """N threads redeem the same token at once → 1 winner, 1 live token.

        A threading.Barrier releases all workers at the same instant so they
        overlap inside rotate_refresh_token rather than running end to end.
        """
        setup = sessions()
        raw = auth_service.create_refresh_token(user.id, setup)

        # Each worker gets its own session, opened and warmed BEFORE the barrier.
        # Connecting after the barrier would stagger the threads by however long
        # the TCP handshake takes — enough to serialise them and hide the race.
        factory = sessionmaker(bind=setup.get_bind())
        worker_sessions = [factory() for _ in range(CONCURRENCY)]
        for s in worker_sessions:
            s.execute(text("SELECT 1"))  # force the connection open

        barrier = threading.Barrier(CONCURRENCY)
        winners: list[str] = []
        rejections: list[str] = []
        lock = threading.Lock()

        def redeem(session):
            try:
                barrier.wait(timeout=10)
                new_raw, _ = rotate_refresh_token(raw, session)
                with lock:
                    winners.append(new_raw)
            except RefreshError as exc:
                with lock:
                    rejections.append(exc.code)
            finally:
                session.close()

        threads = [threading.Thread(target=redeem, args=(s,)) for s in worker_sessions]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(winners) == 1, (
            f"expected exactly 1 successful rotation, got {len(winners)} — "
            "the parent token minted multiple replacement branches"
        )
        assert len(rejections) == CONCURRENCY - 1
        # Losers raced; none of them is a thief.
        assert set(rejections) == {"race"}, f"unexpected rejection codes: {set(rejections)}"

        check = sessions()
        live = _live_tokens(check, user.id)
        assert len(live) == 1, f"expected 1 live token after the race, found {len(live)}"
        # The survivor is the winner's replacement, and it stayed in the family.
        assert live[0].token_hash == auth_service._hash_token(winners[0])

    def test_sequential_redemption_still_rotates(self, sessions, user):
        """Guard against 'fixing' the race by breaking ordinary rotation."""
        s = sessions()
        raw = auth_service.create_refresh_token(user.id, s)

        second, uid = rotate_refresh_token(raw, sessions())
        assert uid == user.id
        third, _ = rotate_refresh_token(second, sessions())
        assert third not in (raw, second)
        assert len(_live_tokens(sessions(), user.id)) == 1

    def test_rotation_preserves_family_device_and_links_parent(self, sessions, user):
        """The replacement inherits the parent's identity fields, unswapped.

        family_id and device_info are adjacent same-typed columns, and an
        earlier implementation using an ORM update().returning() delivered them
        transposed under concurrency — family_id arrived as the device string.
        Asserting on a distinctive device_info value pins that down.
        """
        s = sessions()
        raw = auth_service.create_refresh_token(user.id, s, device_info="Firefox/Android")
        parent = s.query(RefreshToken).filter_by(token_hash=auth_service._hash_token(raw)).one()
        parent_id, family = parent.id, parent.family_id
        assert len(family) == 36, "family_id should be a UUID string"

        new_raw, _ = rotate_refresh_token(raw, sessions())

        check = sessions()
        parent = check.get(RefreshToken, parent_id)
        child = check.query(RefreshToken).filter_by(
            token_hash=auth_service._hash_token(new_raw)
        ).one()
        assert child.family_id == family, "replacement must stay in the parent's family"
        assert child.device_info == "Firefox/Android", "device_info must carry over intact"
        assert parent.replaced_by == child.id, "parent must record what replaced it"
        assert parent.revoked_at is not None


# ── Replay: benign race vs. theft ─────────────────────────────────────────────

class TestReplayHandling:
    def test_replay_inside_grace_window_is_a_race_not_a_breach(self, sessions, user):
        """A double-submit moments after rotation must not kill the session."""
        s = sessions()
        raw = auth_service.create_refresh_token(user.id, s)
        good, _ = rotate_refresh_token(raw, sessions())

        with pytest.raises(RefreshError) as exc:
            rotate_refresh_token(raw, sessions())
        assert exc.value.code == "race"

        # The replacement the winner got is untouched and still usable.
        assert len(_live_tokens(sessions(), user.id)) == 1
        rotate_refresh_token(good, sessions())

    def test_replay_after_grace_window_revokes_the_whole_family(self, sessions, user, monkeypatch):
        """A replay long after redemption is treated as theft: family revoked.

        Rather than sleeping out the real grace window, the parent's revoked_at
        is backdated past it — the code branches on that timestamp.
        """
        s = sessions()
        raw = auth_service.create_refresh_token(user.id, s)
        good, _ = rotate_refresh_token(raw, sessions())

        backdate = sessions()
        parent = backdate.query(RefreshToken).filter_by(
            token_hash=auth_service._hash_token(raw)
        ).one()
        parent.revoked_at = datetime.now(timezone.utc) - timedelta(
            seconds=auth_service.REFRESH_RACE_GRACE_SECONDS + 60
        )
        backdate.commit()

        with pytest.raises(RefreshError) as exc:
            rotate_refresh_token(raw, sessions())
        assert exc.value.code == "reuse"

        # The descendant token is collateral damage by design — we cannot tell
        # the thief from the user, so both are cut off.
        assert _live_tokens(sessions(), user.id) == []
        with pytest.raises(RefreshError):
            rotate_refresh_token(good, sessions())

    def test_unknown_token_is_rejected_without_touching_other_sessions(self, sessions, user):
        s = sessions()
        raw = auth_service.create_refresh_token(user.id, s)

        with pytest.raises(RefreshError) as exc:
            rotate_refresh_token("not-a-real-token", sessions())
        assert exc.value.code == "invalid"
        assert len(_live_tokens(sessions(), user.id)) == 1

    def test_expired_token_is_rejected(self, sessions, user):
        s = sessions()
        raw = auth_service.create_refresh_token(user.id, s)
        row = s.query(RefreshToken).filter_by(token_hash=auth_service._hash_token(raw)).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        s.commit()

        with pytest.raises(RefreshError) as exc:
            rotate_refresh_token(raw, sessions())
        assert exc.value.code == "expired"

    def test_revoked_by_logout_then_replayed_revokes_family(self, sessions, user):
        """Logout revokes without setting replaced_by, so a later replay of that
        token is theft-shaped, not race-shaped, even inside the grace window."""
        s = sessions()
        raw = auth_service.create_refresh_token(user.id, s)
        auth_service.revoke_refresh_token(raw, sessions())

        with pytest.raises(RefreshError) as exc:
            rotate_refresh_token(raw, sessions())
        assert exc.value.code == "reuse"


# ── HTTP surface ──────────────────────────────────────────────────────────────

class TestRefreshEndpointContract:
    def _register(self, client):
        r = client.post("/api/auth/register", json={
            "email": f"hdr_{uuid.uuid4().hex[:8]}@test.com",
            "name": "Contract Test",
            "password": "Password1!",
        })
        assert r.status_code == 201, r.text
        return r.json()["refresh_token"]

    def test_race_reason_reaches_the_client_in_the_error_body(self, client):
        """The frontend has to tell 'someone else rotated' from 'log out'."""
        refresh = self._register(client)
        assert client.post("/api/auth/refresh", json={"refresh_token": refresh}).status_code == 200

        replay = client.post("/api/auth/refresh", json={"refresh_token": refresh})
        assert replay.status_code == 401
        assert replay.json()["error"]["code"] == "REFRESH_RACE"

    def test_unauthorized_responses_carry_www_authenticate(self, client):
        """RFC 7235 requires it on 401; the error handler used to drop it."""
        replay = client.post("/api/auth/refresh", json={"refresh_token": "nope"})
        assert replay.status_code == 401
        assert replay.headers.get("WWW-Authenticate") == "Bearer"
        assert replay.json()["error"]["code"] == "REFRESH_INVALID"

    def test_successful_refresh_returns_a_usable_new_pair(self, client):
        refresh = self._register(client)
        body = client.post("/api/auth/refresh", json={"refresh_token": refresh}).json()
        assert body["refresh_token"] != refresh
        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
        assert me.status_code == 200


# ── Rate limiting ─────────────────────────────────────────────────────────────

class TestRateLimit:
    """The limiter is disabled suite-wide (see conftest._no_rate_limit) because
    every test registers an account and the 10/minute cap counts them all as one
    caller.  This class opts back in so the protection stays covered."""

    def test_register_is_capped_per_client(self, client, rate_limited):
        statuses = []
        for _ in range(12):
            r = client.post("/api/auth/register", json={
                "email": f"rl_{uuid.uuid4().hex[:8]}@test.com",
                "name": "Rate Limited",
                "password": "Password1!",
            })
            statuses.append(r.status_code)

        assert 429 in statuses, f"expected the limiter to kick in, saw {set(statuses)}"
        assert statuses.index(429) >= 10, "limiter fired earlier than the 10/minute cap"

    def test_rate_limited_response_uses_the_structured_error_shape(self, client, rate_limited):
        last = None
        for _ in range(12):
            last = client.post("/api/auth/login", json={
                "email": "nobody@test.com", "password": "Password1!",
            })
            if last.status_code == 429:
                break
        assert last.status_code == 429
        assert last.json()["error"]["code"] == "RATE_LIMITED"
