import json
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards import client_order_actions_inline, main_menu_kb
from repositories import (
    create_notification_job,
    fetchrow,
    get_order_row,
    list_approved_masters_for_category,
    list_order_offers,
    refuse_order,
)
from security import allow_callback_action
from utils import is_admin


logger = logging.getLogger(__name__)


async def _queue_reopened_order_notifications(order_row, exclude_master_user_id: int | None = None) -> int:
    """
    Queue a new notification type after a master refused an order and the order
    became open again with no active offers.

    We intentionally use notification_type='reopened_order' instead of 'new_order'
    because new_order is protected by a unique index and should not be reused
    for the same master/order pair.
    """
    if not order_row:
        return 0

    order_id = int(order_row["id"])
    category = order_row["category"]
    district = order_row.get("district") if hasattr(order_row, "get") else order_row["district"]

    masters = await list_approved_masters_for_category(category, district)
    queued_count = 0

    payload = json.dumps(
        {
            "order_id": order_id,
            "title": "🔄 <b>Заявка знову відкрита</b>",
            "text_after_card": (
                "Майстер відмовився, тому заявка знову доступна.\n"
                "Натисніть <b>📨 Відгукнутись</b>, якщо можете допомогти клієнту."
            ),
        },
        ensure_ascii=False,
    )

    for master in masters:
        master_user_id = master["user_id"]
        if not master_user_id:
            continue

        # Не відправляємо пуш тому майстру, який щойно відмовився.
        if exclude_master_user_id and int(master_user_id) == int(exclude_master_user_id):
            continue

        try:
            job_id = await create_notification_job(
                user_id=int(master_user_id),
                order_id=order_id,
                notification_type="reopened_order",
                payload=payload,
            )
            if job_id:
                queued_count += 1
        except Exception as e:
            logger.warning(
                "Failed to create reopened_order notification job order_id=%s master_user_id=%s: %s",
                order_id,
                master_user_id,
                e,
            )

    logger.info(
        "Reopened order notifications queued: order_id=%s district=%s queued=%s",
        order_id,
        district,
        queued_count,
    )
    return queued_count


def register(dp):
    @dp.callback_query_handler(lambda c: c.data.startswith("refuse_order_confirm_"), state="*")
    async def refuse_order_confirm_reopen_notify_handler(call: types.CallbackQuery, state: FSMContext):
        """
        Replaces the default refuse_order_confirm_ handler from offers.py.

        Why:
        - After master refuses the order, order can become 'new' with no active offers.
        - In that case we must notify masters again.
        - We use notification_type='reopened_order' to avoid unique-index conflict with old new_order jobs.
        """
        allowed = await allow_callback_action(
            call,
            action_key="master_refuse_order",
            limit=8,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        order_id = int(call.data.split("_")[-1])

        order = await fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id=$1
              AND selected_master_id=$2
              AND status = ANY($3::text[])
            """,
            order_id,
            call.from_user.id,
            ["matched", "in_progress"],
        )
        if not order:
            await call.answer("Неможливо відмовитись від цієї заявки.", show_alert=True)
            return

        await refuse_order(order_id)

        try:
            await call.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await call.message.answer(
            f"❌ <b>Ви відмовились від заявки #{order_id}</b>",
            reply_markup=main_menu_kb(is_admin_user=is_admin(call.from_user.id)),
        )

        try:
            updated_order = await get_order_row(order_id)
            active_offers = await list_order_offers(order_id)

            if updated_order and updated_order["status"] == "offered":
                client_text = (
                    f"❌ <b>Майстер відмовився від заявки #{order_id}</b>\n\n"
                    "Заявка все ще активна.\n"
                    "Ви можете обрати іншого майстра з наявних пропозицій."
                )
                client_markup = client_order_actions_inline(order_id, updated_order["status"])

            else:
                actual_status = updated_order["status"] if updated_order else "new"
                client_text = (
                    f"❌ <b>Майстер відмовився від заявки #{order_id}</b>\n\n"
                    "Заявка знову відкрита для нових пропозицій майстрів.\n"
                    "Ми повторно покажемо її майстрам у вашому районі."
                )
                client_markup = client_order_actions_inline(order_id, actual_status)

            await dp.bot.send_message(order["user_id"], client_text, reply_markup=client_markup)

            if active_offers:
                await dp.bot.send_message(
                    order["user_id"],
                    f"📬 <b>Доступних пропозицій зараз:</b> {len(active_offers)}",
                )

            # Головна нова логіка:
            # якщо після відмови немає активних офферів і заявка стала new —
            # відправляємо пуш майстрам повторно.
            if updated_order and updated_order["status"] == "new" and not active_offers:
                queued = await _queue_reopened_order_notifications(
                    updated_order,
                    exclude_master_user_id=call.from_user.id,
                )

                if queued:
                    await dp.bot.send_message(
                        order["user_id"],
                        "📢 <b>Заявку повторно надіслано майстрам у вашому районі.</b>",
                        reply_markup=client_order_actions_inline(order_id, updated_order["status"]),
                    )
                else:
                    logger.info(
                        "Order reopened but no masters queued: order_id=%s district=%s",
                        order_id,
                        updated_order.get("district") if hasattr(updated_order, "get") else updated_order["district"],
                    )

        except Exception as e:
            logger.warning("Не вдалося обробити відмову/повторну розсилку по заявці %s: %s", order_id, e)

        await call.answer("Відмову збережено")
