import asyncio
import logging

from config import settings
from keyboards import (
    admin_order_actions_inline,
    finish_reminder_inline,
    order_card_master_actions,
)
from repositories import execute, fetch
from services import send_order_card
from utils import now_ts


logger = logging.getLogger(__name__)

STALE_ORDERS_CHECK_INTERVAL_SECONDS = 180

MASTER_REMINDER_AFTER_SECONDS = 5 * 60
ADMIN_NO_OFFER_ALERT_AFTER_SECONDS = 30 * 60
CLIENT_FINISH_REMINDER_AFTER_SECONDS = 24 * 60 * 60

BATCH_LIMIT = 20


async def _get_orders_for_master_reminder(limit: int):
    threshold_ts = now_ts() - MASTER_REMINDER_AFTER_SECONDS

    return await fetch(
        """
        SELECT o.*
        FROM orders o
        WHERE o.status='new'
          AND COALESCE(o.created_at, 0) <= $1
          AND o.master_reminder_sent_at IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM offers f
              WHERE f.order_id = o.id
          )
        ORDER BY o.created_at ASC
        LIMIT $2
        """,
        threshold_ts,
        limit,
    )


async def _get_orders_without_offers_for_admin_alert(limit: int):
    threshold_ts = now_ts() - ADMIN_NO_OFFER_ALERT_AFTER_SECONDS

    return await fetch(
        """
        SELECT o.*
        FROM orders o
        WHERE o.status='new'
          AND COALESCE(o.created_at, 0) <= $1
          AND o.admin_no_offer_alert_sent_at IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM offers f
              WHERE f.order_id = o.id
          )
        ORDER BY o.created_at ASC
        LIMIT $2
        """,
        threshold_ts,
        limit,
    )


async def _get_orders_for_client_finish_reminder(limit: int):
    threshold_ts = now_ts() - CLIENT_FINISH_REMINDER_AFTER_SECONDS

    return await fetch(
        """
        SELECT o.*
        FROM orders o
        WHERE o.status='in_progress'
          AND COALESCE(o.updated_at, o.created_at, 0) <= $1
          AND o.client_finish_reminder_sent_at IS NULL
        ORDER BY COALESCE(o.updated_at, o.created_at) ASC
        LIMIT $2
        """,
        threshold_ts,
        limit,
    )


async def _get_approved_masters_for_category(category: str):
    return await fetch(
        """
        SELECT user_id, category, status
        FROM masters
        WHERE status='approved'
          AND $1 = ANY(string_to_array(category, ','))
        """,
        category,
    )


async def _mark_master_reminder_sent(order_id: int):
    await execute(
        """
        UPDATE orders
        SET master_reminder_sent_at=$1
        WHERE id=$2
          AND master_reminder_sent_at IS NULL
        """,
        now_ts(),
        order_id,
    )


async def _mark_admin_no_offer_alert_sent(order_id: int):
    await execute(
        """
        UPDATE orders
        SET admin_no_offer_alert_sent_at=$1
        WHERE id=$2
          AND admin_no_offer_alert_sent_at IS NULL
        """,
        now_ts(),
        order_id,
    )


async def _mark_client_finish_reminder_sent(order_id: int):
    await execute(
        """
        UPDATE orders
        SET client_finish_reminder_sent_at=$1
        WHERE id=$2
          AND client_finish_reminder_sent_at IS NULL
        """,
        now_ts(),
        order_id,
    )


async def notify_masters_about_stale_order(bot, order_row):
    order_id = int(order_row["id"])
    category = order_row["category"]

    masters = await _get_approved_masters_for_category(category)
    if not masters:
        logger.info(
            "No approved masters found for reminder, order_id=%s category=%s",
            order_id,
            category,
        )
        await _mark_master_reminder_sent(order_id)
        return

    sent_count = 0

    for master in masters:
        master_user_id = master["user_id"]
        if not master_user_id:
            continue

        try:
            await send_order_card(
                bot,
                master_user_id,
                order_row,
                title="🔔 <b>Нагадування про заявку</b>",
                reply_markup=order_card_master_actions(order_id),
            )
            await bot.send_message(
                master_user_id,
                (
                    f"⏰ <b>Заявка #{order_id} все ще без відгуків</b>\n\n"
                    "Якщо можете допомогти клієнту — натисніть "
                    "<b>📨 Відгукнутись</b>."
                ),
            )
            sent_count += 1
        except Exception as e:
            logger.warning(
                "Failed to send master reminder for order_id=%s master_user_id=%s: %s",
                order_id,
                master_user_id,
                e,
            )

    await _mark_master_reminder_sent(order_id)

    logger.info(
        "Master reminder sent for order_id=%s, recipients=%s",
        order_id,
        sent_count,
    )


async def notify_admin_about_stale_orders(bot):
    if settings.admin_id <= 0:
        return

    rows = await _get_orders_without_offers_for_admin_alert(BATCH_LIMIT)
    if not rows:
        return

    for row in rows:
        order_id = int(row["id"])

        try:
            await send_order_card(
                bot,
                settings.admin_id,
                row,
                title="⚠️ <b>Заявка без оферів 30+ хв</b>",
                reply_markup=admin_order_actions_inline(order_id, row["status"]),
            )

            await bot.send_message(
                settings.admin_id,
                (
                    f"🆘 <b>Заявка #{order_id} досі без відгуків майстрів</b>\n\n"
                    "Що можна зробити:\n"
                    "• перевірити категорію заявки\n"
                    "• відкрити деталі та історію\n"
                    "• вручну зв'язатися з майстрами\n"
                    "• закрити як неактуальну, якщо потрібно"
                ),
            )

            await _mark_admin_no_offer_alert_sent(order_id)

            logger.info(
                "Admin stale-order alert sent for order_id=%s",
                order_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to send stale-order admin alert for order_id=%s: %s",
                order_id,
                e,
            )


async def notify_clients_about_finish_reminder(bot):
    rows = await _get_orders_for_client_finish_reminder(BATCH_LIMIT)
    if not rows:
        return

    for row in rows:
        order_id = int(row["id"])
        user_id = row["user_id"]

        try:
            await bot.send_message(
                user_id,
                (
                    f"⏰ <b>Заявка #{order_id} все ще активна</b>\n\n"
                    "Майстер уже виконав роботу?\n\n"
                    "Якщо так — підтвердіть завершення і залиште оцінку."
                ),
                reply_markup=finish_reminder_inline(order_id),
            )

            await _mark_client_finish_reminder_sent(order_id)

            logger.info(
                "Client finish reminder sent for order_id=%s user_id=%s",
                order_id,
                user_id,
            )
        except Exception as e:
            logger.warning(
                "Failed to send client finish reminder for order_id=%s user_id=%s: %s",
                order_id,
                user_id,
                e,
            )


async def notify_masters_about_stale_orders(bot):
    rows = await _get_orders_for_master_reminder(BATCH_LIMIT)
    if not rows:
        return

    for row in rows:
        try:
            await notify_masters_about_stale_order(bot, row)
        except Exception:
            logger.exception(
                "Failed to process master reminder for order_id=%s",
                row["id"],
            )


async def stale_orders_watcher(bot, shutdown_event: asyncio.Event):
    logger.info(
        "Stale orders watcher started: every %s sec, master reminder=%s sec, admin alert=%s sec, client finish reminder=%s sec",
        STALE_ORDERS_CHECK_INTERVAL_SECONDS,
        MASTER_REMINDER_AFTER_SECONDS,
        ADMIN_NO_OFFER_ALERT_AFTER_SECONDS,
        CLIENT_FINISH_REMINDER_AFTER_SECONDS,
    )

    while not shutdown_event.is_set():
        try:
            await notify_masters_about_stale_orders(bot)
            await notify_admin_about_stale_orders(bot)
            await notify_clients_about_finish_reminder(bot)
        except Exception:
            logger.exception("Stale orders watcher iteration failed")

        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=STALE_ORDERS_CHECK_INTERVAL_SECONDS,
            )
        except asyncio.TimeoutError:
            continue

    logger.info("Stale orders watcher stopped")
