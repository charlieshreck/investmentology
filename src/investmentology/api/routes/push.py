"""Push notification endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from investmentology.api.deps import get_registry
from investmentology.push.sender import send_notification
from investmentology.registry.queries import Registry

logger = logging.getLogger(__name__)
router = APIRouter()


class PushSubscription(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": str, "auth": str}


@router.post("/push/subscribe")
def subscribe(body: PushSubscription, registry: Registry = Depends(get_registry)) -> dict:
    """Register a push notification subscription."""
    p256dh = body.keys.get("p256dh")
    auth = body.keys.get("auth")
    if not p256dh or not auth:
        raise HTTPException(status_code=422, detail="keys.p256dh and keys.auth required")

    registry._db.execute(
        "INSERT INTO invest.push_subscriptions (endpoint, p256dh, auth) "
        "VALUES (%s, %s, %s) "
        "ON CONFLICT (endpoint) DO UPDATE SET p256dh = %s, auth = %s",
        (body.endpoint, p256dh, auth, p256dh, auth),
    )
    return {"status": "subscribed"}


@router.post("/push/unsubscribe")
def unsubscribe(body: PushSubscription, registry: Registry = Depends(get_registry)) -> dict:
    """Remove a push notification subscription."""
    registry._db.execute(
        "DELETE FROM invest.push_subscriptions WHERE endpoint = %s",
        (body.endpoint,),
    )
    return {"status": "unsubscribed"}


@router.post("/push/test")
def test_push(registry: Registry = Depends(get_registry)) -> dict:
    """Send a test push notification to all subscribers."""
    count = send_notification(
        registry._db,
        title="Haute Banque",
        body="Push notifications are working!",
        url="/",
    )
    return {"sent": count}
