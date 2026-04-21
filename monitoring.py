import asyncio
import logging

from config import settings
from keyboards import admin_order_actions_inline
from repositories import execute, fetch
from services import send_order_card
from utils import now_ts


logger = logging.getLogger(__name__)

# Як часто перевіряти заявки
STALE_ORDERS_CHECK_INTERVAL_SECONDS = 180

# Через скільки секунд без оферів слати алерт адміну
ADMIN_NO_OFFER_ALERT_AFTER_SECONDS = 30 * 60

# Скільки заявок максимум обробляти за один цикл
ADMIN_NO_OFFER_ALERT_BATCH_LIMIT = 20


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


async def notify_admin_about_stale_orders(bot):
    if settings.admin_id <= 0:
        return

    rows = await _get_orders_without_offers_for_admin_alert(
        ADMIN_NO_OFFER_ALERT_BATCH_LIMIT
    )

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
                "Failed to send stale-order alert for order_id=%s: %s",
                order_id,
                e,
            )


async def stale_orders_watcher(bot, shutdown_event: asyncio.Event):
    logger.info(
        "Stale orders watcher started: every %s sec, threshold=%s sec",
        STALE_ORDERS_CHECK_INTERVAL_SECONDS,
        ADMIN_NO_OFFER_ALERT_AFTER_SECONDS,
    )

    while not shutdown_event.is_set():
        try:
            await notify_admin_about_stale_orders(bot)
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
