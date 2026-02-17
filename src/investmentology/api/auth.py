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


def create_token(secret: str, expiry_hours: int) -> str:
    """Create a signed JWT with an expiration claim."""
    exp = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    return jwt.encode({"exp": exp}, secret, algorithm=ALGORITHM)


def verify_token(token: str, secret: str) -> bool:
    """Return True if the token is valid and not expired."""
    try:
        jwt.decode(token, secret, algorithms=[ALGORITHM])
        return True
    except JWTError:
        return False
