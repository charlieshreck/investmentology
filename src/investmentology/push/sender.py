"""Web Push notification sender.

Uses pywebpush to send notifications to subscribed clients.
VAPID keys stored in Infisical (/platform/haute-banque/VAPID_*).
"""

from __future__ import annotations

import json
import logging
import os

from investmentology.registry.db import Database

logger = logging.getLogger(__name__)


def _get_vapid_claims() -> dict:
    """Get VAPID claims from environment."""
    return {
        "sub": os.environ.get("VAPID_SUBJECT", "mailto:admin@kernow.io"),
    }


def send_notification(
    db: Database,
    title: str,
    body: str,
    url: str = "/",
) -> int:
    """Send push notification to all subscribers.

    Returns number of successful sends.
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.warning("pywebpush not installed — push notifications disabled")
        return 0

    vapid_private_key = os.environ.get("VAPID_PRIVATE_KEY")
    if not vapid_private_key:
        logger.warning("VAPID_PRIVATE_KEY not set — push notifications disabled")
        return 0

    rows = db.execute("SELECT endpoint, p256dh, auth FROM invest.push_subscriptions")
    if not rows:
        return 0

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
    })

    sent = 0
    expired_endpoints: list[str] = []

    for sub in rows:
        subscription_info = {
            "endpoint": sub["endpoint"],
            "keys": {
                "p256dh": sub["p256dh"],
                "auth": sub["auth"],
            },
        }
        try:
            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=_get_vapid_claims(),
            )
            sent += 1
        except WebPushException as e:
            if hasattr(e, "response") and e.response and e.response.status_code in (404, 410):
                expired_endpoints.append(sub["endpoint"])
                logger.info("Removing expired push subscription: %s", sub["endpoint"][:60])
            else:
                logger.warning("Push failed for %s: %s", sub["endpoint"][:60], e)
        except Exception:
            logger.exception("Push send error")

    # Clean up expired subscriptions
    for endpoint in expired_endpoints:
        try:
            db.execute(
                "DELETE FROM invest.push_subscriptions WHERE endpoint = %s",
                (endpoint,),
            )
        except Exception:
            pass

    logger.info("Push notifications sent: %d/%d", sent, len(rows))
    return sent
