import asyncio
import json
import logging

from aiogram.utils.exceptions import BotBlocked, ChatNotFound, RetryAfter, TelegramAPIError

from keyboards import order_card_master_actions
from repositories import (
    claim_notification_jobs,
    get_order_row,
    mark_notification_job_failed,
    mark_notification_job_retry,
    mark_notification_job_sent,
)
from services import send_order_card
from utils import now_ts


logger = logging.getLogger(__name__)

DEFAULT_BATCH_LIMIT = 10
MAX_ATTEMPTS = 3
SEND_DELAY_SECONDS = 0.12


def _safe_payload(raw_payload):
    if not raw_payload:
        return {}
    try:
        return json.loads(raw_payload)
    except Exception:
        return {}


async def _send_new_order_job(bot, job):
    payload = _safe_payload(job.get("payload") if hasattr(job, "get") else job["payload"])
    order_id = int(job["order_id"] or payload.get("order_id") or 0)
    if order_id <= 0:
        raise ValueError("new_order job without valid order_id")

    order = await get_order_row(order_id)
    if not order:
        raise ValueError(f"order {order_id} not found")

    user_id = int(job["user_id"])
    title = payload.get("title") or "🔔 <b>Нова заявка</b>"
    text_after_card = payload.get("text_after_card") or (
        "Натисніть <b>📨 Відгукнутись</b>, якщо хочете взяти цю заявку в роботу."
    )

    await send_order_card(
        bot,
        user_id,
        order,
        title=title,
        reply_markup=order_card_master_actions(order_id),
    )
    await bot.send_message(user_id, text_after_card)


async def process_notification_jobs(bot, batch_limit: int = DEFAULT_BATCH_LIMIT):
    """
    Sends pending notification jobs gradually.

    This protects the bot from Telegram flood limits and makes delivery durable:
    pending jobs stay in PostgreSQL if Render restarts.
    """
    jobs = await claim_notification_jobs(batch_limit)
    if not jobs:
        return 0

    processed = 0

    for job in jobs:
        job_id = int(job["id"])
        attempts = int(job["attempts"] or 1)
        notification_type = job["notification_type"]

        try:
            if notification_type == "new_order":
                await _send_new_order_job(bot, job)
            else:
                raise ValueError(f"unsupported notification_type={notification_type}")

            await mark_notification_job_sent(job_id)
            processed += 1

        except RetryAfter as e:
            retry_after = int(getattr(e, "timeout", None) or getattr(e, "retry_after", None) or 30)
            await mark_notification_job_retry(
                job_id,
                f"RetryAfter: {retry_after}",
                now_ts() + max(5, retry_after),
            )
            logger.warning("Notification job %s delayed by Telegram RetryAfter=%s", job_id, retry_after)

        except (BotBlocked, ChatNotFound) as e:
            await mark_notification_job_failed(job_id, str(e))
            logger.warning("Notification job %s permanently failed: %s", job_id, e)

        except TelegramAPIError as e:
            if attempts >= MAX_ATTEMPTS:
                await mark_notification_job_failed(job_id, str(e))
            else:
                await mark_notification_job_retry(job_id, str(e), now_ts() + 60 * attempts)
            logger.warning("Notification job %s TelegramAPIError attempts=%s: %s", job_id, attempts, e)

        except Exception as e:
            if attempts >= MAX_ATTEMPTS:
                await mark_notification_job_failed(job_id, str(e))
            else:
                await mark_notification_job_retry(job_id, str(e), now_ts() + 60 * attempts)
            logger.exception("Notification job %s failed attempts=%s: %s", job_id, attempts, e)

        await asyncio.sleep(SEND_DELAY_SECONDS)

    return processed
