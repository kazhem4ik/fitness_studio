import json
import logging
import asyncio
from pywebpush import webpush, WebPushException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from planner_service.core.config import settings
from planner_service.models.push_subscription import PushSubscription
from planner_service.core.database import async_session

logger = logging.getLogger(__name__)


async def _do_send_push_notification(title: str, body: str, url: str, trainer_id: int | None):
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        logger.warning("VAPID keys not configured, skipping push notification.")
        return

    async with async_session() as db:
        query = select(PushSubscription)
        if trainer_id is not None:
            query = query.where(PushSubscription.trainer_id == trainer_id)

        result = await db.execute(query)
        subscriptions = result.scalars().all()

        if not subscriptions:
            return

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
                # Run synchronous webpush in a thread to not block the event loop
                await asyncio.to_thread(
                    webpush,
                    subscription_info=sub_info,
                    data=payload,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims=vapid_claims
                )
                logger.info(f"Push notification sent to {sub.endpoint}")
            except WebPushException as ex:
                logger.error(f"Push failed: {repr(ex)}")
                if ex.response and ex.response.status_code == 410:
                    await db.delete(sub)
                    await db.commit()
            except Exception as e:
                logger.error(f"Unexpected error sending push: {repr(e)}")


async def send_push_notification(
    db: AsyncSession,
    title: str,
    body: str,
    url: str = "/clients/",
    trainer_id: int | None = None,
):
    """
    Отправляет Web Push уведомление асинхронно, не блокируя текущий запрос.
    db параметр оставлен для обратной совместимости, но не используется,
    так как внутри создается новая сессия для фоновой задачи.
    """
    asyncio.create_task(_do_send_push_notification(title, body, url, trainer_id))
