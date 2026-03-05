"""Authentication utilities: password verification and JWT token management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from jose import JWTError, jwt

ALGORITHM = "HS256"


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against one or more bcrypt hashes (comma-separated)."""
    plain_bytes = plain.encode()
    for h in hashed.split(","):
        h = h.strip()
        if h and _bcrypt.checkpw(plain_bytes, h.encode()):
            return True
    return False


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def create_token(secret: str, expiry_hours: int, user_id: int | None = None) -> str:
    """Create a signed JWT with an expiration claim and optional user_id."""
    payload: dict = {"exp": datetime.now(timezone.utc) + timedelta(hours=expiry_hours)}
    if user_id is not None:
        payload["sub"] = str(user_id)
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_token(token: str, secret: str) -> bool:
    """Return True if the token is valid and not expired."""
    try:
        jwt.decode(token, secret, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False


def get_user_id_from_token(token: str, secret: str) -> int | None:
    """Extract user_id from a valid JWT token. Returns None if no sub claim or invalid."""
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
        sub = payload.get("sub")
        return int(sub) if sub else None
    except (JWTError, ValueError, TypeError):
        return None
