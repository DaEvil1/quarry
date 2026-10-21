"""Sessions, recovery codes and a small rate limiter.

Sign-in itself is passkeys only (see passkeys.py); this module holds what happens around it.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .models import AuthSession, RecoveryCode

SESSION_COOKIE = "quarry_session"
SESSION_DAYS = 30
# a session is extended at most this often, so browsing does not write to the database on every request
SESSION_REFRESH = timedelta(hours=1)
RECOVERY_CODES = 10
# no 0/O/1/I/L: codes get read off paper
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def now() -> datetime:
    return datetime.now(UTC)


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def tokens_match(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# sessions ------------------------------------------------------------------------------------------------------


def start_session(db: Session, user_id: uuid.UUID, user_agent: str = "") -> str:
    """Create a session and return the cookie value (only its hash is stored)."""
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(user_id=user_id, token_hash=sha256(token), user_agent=user_agent[:300],
                       expires_at=now() + timedelta(days=SESSION_DAYS)))
    return token


def find_session(db: Session, token: str) -> AuthSession | None:
    if not token:
        return None
    s = db.scalars(select(AuthSession).where(AuthSession.token_hash == sha256(token))).first()
    if s is None or s.expires_at <= now():
        return None
    return s


def touch_session(s: AuthSession) -> bool:
    """Slide the expiry forward; returns True when it moved (the cookie should be sent again)."""
    target = now() + timedelta(days=SESSION_DAYS)
    if target - s.expires_at < SESSION_REFRESH:
        return False
    s.expires_at = target
    return True


def end_session(db: Session, token: str) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == sha256(token)))


def end_all_sessions(db: Session, user_id: uuid.UUID) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


# recovery codes ------------------------------------------------------------------------------------------------


def _normalize_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def new_recovery_codes(db: Session, user_id: uuid.UUID) -> list[str]:
    """Replace the user's recovery codes with a fresh set and return them (shown once, stored hashed)."""
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))
    codes = []
    for _ in range(RECOVERY_CODES):
        raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
        db.add(RecoveryCode(user_id=user_id, code_hash=sha256(raw)))
    return codes


def use_recovery_code(db: Session, code: str) -> uuid.UUID | None:
    """Spend a recovery code; returns its user, or None when it is unknown or already used."""
    norm = _normalize_code(code)
    if len(norm) != 10:
        return None
    row = db.execute(
        update(RecoveryCode)
        .where(RecoveryCode.code_hash == sha256(norm), RecoveryCode.used_at.is_(None))
        .values(used_at=now())
        .returning(RecoveryCode.user_id)
    ).first()
    return row[0] if row else None


def recovery_codes_left(db: Session, user_id: uuid.UUID) -> int:
    rows = db.scalars(select(RecoveryCode.id).where(RecoveryCode.user_id == user_id,
                                                    RecoveryCode.used_at.is_(None))).all()
    return len(rows)


# rate limiting -------------------------------------------------------------------------------------------------


class RateLimiter:
    """At most ``limit`` attempts per key in ``window`` seconds (kept in memory: one worker)."""

    def __init__(self, limit: int = 20, window: float = 600) -> None:
        self.limit = limit
        self.window = window
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        t = time.monotonic()
        q = self.hits[key]
        while q and t - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(t)
        if len(self.hits) > 10_000:
            self.hits.clear()
        return True

    def clear(self) -> None:
        self.hits.clear()


auth_limiter = RateLimiter()
