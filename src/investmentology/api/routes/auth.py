"""Authentication endpoints: login, logout, session check."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Request, Response
from pydantic import BaseModel

from investmentology.api.auth import create_token, verify_password, verify_token
from investmentology.api.deps import app_state

router = APIRouter()

COOKIE_NAME = "session"


class LoginRequest(BaseModel):
    password: str


@router.post("/auth/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    """Verify password and set a session cookie."""
    config = app_state.config
    if not config or not config.auth_password_hash:
        return {"ok": False, "error": "Auth not configured"}

    if not verify_password(body.password, config.auth_password_hash):
        response.status_code = 401
        return {"ok": False, "error": "Invalid password"}

    token = create_token(config.auth_secret_key, config.auth_token_expiry_hours)
    max_age = config.auth_token_expiry_hours * 3600
    # Secure cookie only over HTTPS (Cloudflare tunnel sets X-Forwarded-Proto)
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
    return {"ok": True}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/auth/check")
def check_auth(session: str | None = Cookie(None)) -> dict:
    """Check whether the caller has a valid session cookie."""
    config = app_state.config
    if not config or not config.auth_secret_key:
        # Auth not configured — treat as authenticated (dev mode)
        return {"authenticated": True}

    if not session or not verify_token(session, config.auth_secret_key):
        return {"authenticated": False}

    return {"authenticated": True}
