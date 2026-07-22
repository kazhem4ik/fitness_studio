import json
import logging
from pywebpush import webpush, WebPushException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.config import settings
from planner_service.models.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


async def send_push_notification(db: AsyncSession, title: str, body: str, url: str = "/clients/"):
    """Отправляет Web Push всем подписанным администраторам."""
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured, skipping push notification.")
        return

    result = await db.execute(select(PushSubscription))
    subscriptions = result.scalars().all()

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url
    })

    vapid_claims = {
        "sub": "mailto:admin@example.com"
    }

    for sub in subscriptions:
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        try:
            webpush(
                subscription_info=sub_info,
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims=vapid_claims
            )
            logger.info(f"Push notification sent to {sub.endpoint}")
        except WebPushException as ex:
            logger.error(f"Push failed: {repr(ex)}")
            # Optional: remove expired subscription if ex.response.status_code == 410
            if ex.response and ex.response.status_code == 410:
                await db.delete(sub)
                await db.commit()
