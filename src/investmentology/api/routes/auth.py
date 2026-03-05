"""Authentication endpoints: login, logout, session check, registration."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Cookie, Request, Response
from pydantic import BaseModel

from investmentology.api.auth import (
    create_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
    verify_token,
)
from investmentology.api.deps import app_state

logger = logging.getLogger(__name__)

router = APIRouter()

COOKIE_NAME = "session"


class LoginRequest(BaseModel):
    password: str
    email: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = ""


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    """Verify credentials and set a session cookie."""
    config = app_state.config
    db = app_state.db

    if not db:
        return {"ok": False, "error": "Database not available"}

    email = body.email.lower().strip()
    if not email or "@" not in email:
        response.status_code = 400
        return {"ok": False, "error": "Email required"}

    rows = db.execute(
        "SELECT id, password_hash, is_active FROM invest.users WHERE email = %s",
        (email,),
    )
    if not rows:
        response.status_code = 401
        return {"ok": False, "error": "Invalid email or password"}

    user = rows[0]
    if not user.get("is_active", True):
        response.status_code = 401
        return {"ok": False, "error": "Account disabled"}

    if not verify_password(body.password, user["password_hash"]):
        response.status_code = 401
        return {"ok": False, "error": "Invalid email or password"}

    user_id = user["id"]

    if not config or not config.auth_secret_key:
        return {"ok": False, "error": "Auth not configured"}

    token = create_token(config.auth_secret_key, config.auth_token_expiry_hours, user_id=user_id)
    max_age = config.auth_token_expiry_hours * 3600
    is_https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto") == "https"
    )
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=is_https,
        samesite="lax",
        max_age=max_age,
        path="/",
    )
    return {"ok": True, "userId": user_id}


@router.post("/auth/register")
def register(body: RegisterRequest, request: Request, response: Response) -> dict:
    """Create a new user account."""
    config = app_state.config
    db = app_state.db
    if not db:
        return {"ok": False, "error": "Database not available"}

    email = body.email.lower().strip()
    if not email or "@" not in email:
        response.status_code = 400
        return {"ok": False, "error": "Valid email required"}
    if len(body.password) < 8:
        response.status_code = 400
        return {"ok": False, "error": "Password must be at least 8 characters"}

    # Check if email already exists
    existing = db.execute(
        "SELECT id FROM invest.users WHERE email = %s", (email,)
    )
    if existing:
        response.status_code = 409
        return {"ok": False, "error": "Email already registered"}

    pw_hash = hash_password(body.password)
    display = body.display_name or email.split("@")[0]

    rows = db.execute(
        "INSERT INTO invest.users (email, password_hash, display_name) "
        "VALUES (%s, %s, %s) RETURNING id",
        (email, pw_hash, display),
    )
    user_id = rows[0]["id"] if rows else None
    if not user_id:
        response.status_code = 500
        return {"ok": False, "error": "Failed to create account"}

    # Create user's portfolio budget
    db.execute(
        "INSERT INTO invest.portfolio_budget (user_id, total_capital, cash_reserve) "
        "VALUES (%s, 100000, 100000)",
        (user_id,),
    )

    # Auto-login after registration
    if config and config.auth_secret_key:
        token = create_token(config.auth_secret_key, config.auth_token_expiry_hours, user_id=user_id)
        is_https = (
            request.url.scheme == "https"
            or request.headers.get("x-forwarded-proto") == "https"
        )
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            secure=is_https,
            samesite="lax",
            max_age=config.auth_token_expiry_hours * 3600,
            path="/",
        )

    logger.info("New user registered: %s (id=%s)", email, user_id)
    return {"ok": True, "userId": user_id}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/auth/check")
def check_auth(session: str | None = Cookie(None)) -> dict:
    """Check whether the caller has a valid session cookie."""
    config = app_state.config
    if config and config.auth_disabled:
        return {"authenticated": True}
    if not config or not config.auth_secret_key:
        return {"authenticated": False}

    if not session or not verify_token(session, config.auth_secret_key):
        return {"authenticated": False}

    user_id = get_user_id_from_token(session, config.auth_secret_key)
    return {"authenticated": True, "userId": user_id}


@router.get("/auth/me")
def get_me(session: str | None = Cookie(None)) -> dict:
    """Return the current user's profile."""
    config = app_state.config
    if not config or not config.auth_secret_key:
        return {"user": None}
    if not session:
        return {"user": None}

    user_id = get_user_id_from_token(session, config.auth_secret_key)
    if not user_id or not app_state.db:
        return {"user": None}

    rows = app_state.db.execute(
        "SELECT id, email, display_name, created_at FROM invest.users WHERE id = %s",
        (user_id,),
    )
    if not rows:
        return {"user": None}

    u = rows[0]
    return {
        "user": {
            "id": u["id"],
            "email": u["email"],
            "displayName": u["display_name"],
            "createdAt": u["created_at"].isoformat() if u["created_at"] else None,
        }
    }
