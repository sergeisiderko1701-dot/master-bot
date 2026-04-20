import asyncio
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import settings
from constants import status_label
from keyboards import main_menu_kb
from repositories import (
    admin_stats,
    close_chat,
    delete_master_by_id,
    execute,
    fetch,
    fetchrow,
    get_master_by_id,
    get_order_row,
    list_admin_masters,
    list_admin_orders,
    list_order_offers,
    list_pending_masters,
    set_master_status_by_id,
    set_order_status,
)
from services import send_admin_order_detail, send_master_card, send_order_card
from utils import is_admin, now_ts


logger = logging.getLogger(__name__)
PAGE_SIZE = settings.page_size
BROADCAST_DELAY_SECONDS = 0.05


class AdminPanelState(StatesGroup):
    order_id = State()
    user_id = State()
    master_user_id = State()
    support_reply = State()
    broadcast_compose = State()


STATUS_FILTER_MAP = {
    "📋 Усі заявки": None,
    "🆕 Нові": "new",
    "📬 Є пропозиції": "offered",
    "🤝 Обрано майстра": "matched",
    "🛠 В роботі": "in_progress",
    "✅ Завершені": "done",
    "❌ Скасовані": "cancelled",
    "⌛ Прострочені": "expired",
}


def _reply_kb(rows):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for row in rows:
        kb.row(*[KeyboardButton(text) for text in row])
    return kb


def admin_menu_kb():
    return _reply_kb([
        ["📊 Статистика", "📦 Заявки"],
        ["🔎 Пошук заявки", "🔎 Пошук користувача"],
        ["🔎 Пошук майстра", "📦 Завислі заявки"],
        ["📝 Модерація майстрів", "👷 Майстри"],
        ["⚠️ Скарги", "📣 СМС розсилка"],
        ["⬅️ Назад", "🏠 У меню"],
    ])


def admin_orders_filter_kb():
    return _reply_kb([
        ["📋 Усі заявки"],
        ["🆕 Нові", "📬 Є пропозиції"],
        ["🤝 Обрано майстра", "🛠 В роботі"],
        ["✅ Завершені", "❌ Скасовані"],
        ["⌛ Прострочені"],
        ["⬅️ Назад", "🏠 У меню"],
    ])


def admin_broadcast_menu_kb():
    return _reply_kb([
        ["📣 Всім"],
        ["📣 Майстрам", "📣 Клієнтам"],
        ["⬅️ Назад", "🏠 У меню"],
    ])


def pagination_inline(prefix: str, page: int, has_prev: bool, has_next: bool):
    kb = InlineKeyboardMarkup(row_width=2)
    row = []

    if has_prev:
        row.append(InlineKeyboardButton("⬅️ Попередня", callback_data=f"{prefix}_{page-1}"))
    if has_next:
        row.append(InlineKeyboardButton("Наступна ➡️", callback_data=f"{prefix}_{page+1}"))

    if row:
        kb.add(*row)
        return kb

    return None


def admin_pending_master_inline(master_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Підтвердити", callback_data=f"admin_approve_master_{master_id}"))
    kb.add(InlineKeyboardButton("❌ Відхилити", callback_data=f"admin_reject_master_{master_id}"))
    return kb


def admin_master_card_inline(master_id: int, status: str):
    kb = InlineKeyboardMarkup(row_width=1)

    if status == "approved":
        kb.add(InlineKeyboardButton("🚫 Заблокувати", callback_data=f"admin_block_master_{master_id}"))
    elif status == "blocked":
        kb.add(InlineKeyboardButton("✅ Розблокувати", callback_data=f"admin_unblock_master_{master_id}"))

    kb.add(InlineKeyboardButton("🗑 Видалити майстра", callback_data=f"admin_delete_master_{master_id}"))
    return kb


def admin_order_actions_inline(order_id: int, status: str):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📄 Деталі заявки", callback_data=f"admin_order_detail_{order_id}"))
    kb.add(InlineKeyboardButton("🧾 Історія заявки", callback_data=f"admin_order_history_{order_id}"))
    kb.add(InlineKeyboardButton("📜 Історія діалогу", callback_data=f"chat_history_{order_id}"))

    if status in {"new", "offered", "matched", "in_progress"}:
        kb.add(InlineKeyboardButton("❌ Закрити як неактуальну", callback_data=f"admin_expire_order_{order_id}"))

    if status == "matched":
        kb.add(InlineKeyboardButton("🛠 Позначити 'в роботі'", callback_data=f"admin_progress_order_{order_id}"))

    if status in {"matched", "in_progress"}:
        kb.add(InlineKeyboardButton("🏁 Завершити", callback_data=f"admin_done_order_{order_id}"))

    if status in {"offered", "matched", "in_progress"}:
        kb.add(InlineKeyboardButton("🔄 Повернути в нові", callback_data=f"admin_reset_order_{order_id}"))

    return kb


def admin_complaint_actions_inline(complaint_id: int, order_id: int, against_user_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📄 Відкрити заявку", callback_data=f"admin_order_detail_{order_id}"))
    kb.add(InlineKeyboardButton("👷 Відкрити майстра", callback_data=f"admin_open_master_by_user_{against_user_id}"))
    kb.add(InlineKeyboardButton("🗑 Видалити скаргу", callback_data=f"admin_delete_complaint_{complaint_id}"))
    return kb


def support_reply_inline(user_id: int):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("↩️ Відповісти", callback_data=f"support_reply_{user_id}"))
    return kb


def broadcast_confirm_inline():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Підтвердити", callback_data="admin_broadcast_confirm"),
        InlineKeyboardButton("❌ Скасувати", callback_data="admin_broadcast_cancel"),
    )
    return kb


def _master_summary_text(master_row, stats: dict) -> str:
    return (
        "📈 <b>Коротка статистика майстра</b>\n\n"
        f"📦 Всього обраних заявок: <b>{stats['total_selected']}</b>\n"
        f"✅ Завершених: <b>{stats['done']}</b>\n"
        f"❌ Скасованих/прострочених: <b>{stats['closed_bad']}</b>\n"
        f"🛠 Активних: <b>{stats['active']}</b>\n"
        f"⚠️ Скарг: <b>{stats['complaints']}</b>\n"
        f"⭐ Рейтинг: <b>{float(master_row['rating'] or 0):.2f}</b>\n"
        f"💬 Відгуків: <b>{master_row['reviews_count']}</b>"
    )


def _broadcast_mode_label(mode: str) -> str:
    if mode == "all":
        return "всім користувачам"
    if mode == "masters":
        return "майстрам"
    if mode == "clients":
        return "клієнтам"
    return mode


async def _get_unique_recipient_ids(mode: str):
    if mode == "masters":
        rows = await fetch("SELECT DISTINCT user_id FROM masters WHERE user_id IS NOT NULL")
        ids = [int(r["user_id"]) for r in rows if r["user_id"]]
    elif mode == "clients":
        rows = await fetch("SELECT DISTINCT user_id FROM orders WHERE user_id IS NOT NULL")
        ids = [int(r["user_id"]) for r in rows if r["user_id"]]
    else:
        rows = await fetch(
            """
            SELECT DISTINCT user_id
            FROM (
                SELECT user_id FROM masters WHERE user_id IS NOT NULL
                UNION
                SELECT user_id FROM orders WHERE user_id IS NOT NULL
            ) t
            """
        )
        ids = [int(r["user_id"]) for r in rows if r["user_id"]]

    ids = [uid for uid in ids if uid != settings.admin_id]
    return sorted(set(ids))


async def _user_statistics():
    total_users_row = await fetchrow(
        """
        SELECT COUNT(*) AS c
        FROM (
            SELECT user_id FROM masters WHERE user_id IS NOT NULL
            UNION
            SELECT user_id FROM orders WHERE user_id IS NOT NULL
        ) t
        """
    )
    clients_row = await fetchrow("SELECT COUNT(DISTINCT user_id) AS c FROM orders WHERE user_id IS NOT NULL")
    masters_row = await fetchrow("SELECT COUNT(DISTINCT user_id) AS c FROM masters WHERE user_id IS NOT NULL")
    approved_masters_row = await fetchrow(
        "SELECT COUNT(DISTINCT user_id) AS c FROM masters WHERE status='approved' AND user_id IS NOT NULL"
    )
    pending_masters_row = await fetchrow(
        "SELECT COUNT(DISTINCT user_id) AS c FROM masters WHERE status='pending' AND user_id IS NOT NULL"
    )
    blocked_masters_row = await fetchrow(
        "SELECT COUNT(DISTINCT user_id) AS c FROM masters WHERE status='blocked' AND user_id IS NOT NULL"
    )

    return {
        "users_total": int(total_users_row["c"] or 0),
        "clients_total": int(clients_row["c"] or 0),
        "masters_total_users": int(masters_row["c"] or 0),
        "masters_approved_users": int(approved_masters_row["c"] or 0),
        "masters_pending_users": int(pending_masters_row["c"] or 0),
        "masters_blocked_users": int(blocked_masters_row["c"] or 0),
    }


def register(dp):
    async def _show_pending_masters(chat_id: int, page: int, bot):
        offset = page * PAGE_SIZE
        rows, total = await list_pending_masters(PAGE_SIZE, offset)

        if not rows:
            await bot.send_message(chat_id, "Немає майстрів на перевірці.", reply_markup=admin_menu_kb())
            return

        await bot.send_message(chat_id, "📝 <b>Модерація майстрів</b>", reply_markup=admin_menu_kb())

        for row in rows:
            await send_master_card(
                bot,
                chat_id,
                row,
                title="📝 Анкета майстра",
                reply_markup=admin_pending_master_inline(row["id"]),
            )

        has_prev = page > 0
        has_next = offset + PAGE_SIZE < total
        nav = pagination_inline("pending_masters", page, has_prev, has_next)
        if nav:
            await bot.send_message(chat_id, "Навігація:", reply_markup=nav)

    async def _show_admin_masters(chat_id: int, page: int, bot):
        offset = page * PAGE_SIZE
        rows, total = await list_admin_masters(PAGE_SIZE, offset)

        if not rows:
            await bot.send_message(chat_id, "Майстрів не знайдено.", reply_markup=admin_menu_kb())
            return

        await bot.send_message(chat_id, "👷 <b>Майстри</b>", reply_markup=admin_menu_kb())

        for row in rows:
            await send_master_card(
                bot,
                chat_id,
                row,
                title="👷 Картка майстра",
                reply_markup=admin_master_card_inline(row["id"], row["status"]),
            )

        has_prev = page > 0
        has_next = offset + PAGE_SIZE < total
        nav = pagination_inline("admin_masters", page, has_prev, has_next)
        if nav:
            await bot.send_message(chat_id, "Навігація:", reply_markup=nav)

    async def _show_admin_orders(chat_id: int, page: int, bot, status_filter=None):
        offset = page * PAGE_SIZE
        rows, total = await list_admin_orders(PAGE_SIZE, offset, status_filter)

        if not rows:
            await bot.send_message(chat_id, "Заявок не знайдено.", reply_markup=admin_menu_kb())
            return

        title = "📦 <b>Заявки</b>"
        if status_filter:
            title += f"\nФільтр: <b>{status_label(status_filter)}</b>"
        await bot.send_message(chat_id, title, reply_markup=admin_menu_kb())

        for row in rows:
            await send_order_card(
                bot,
                chat_id,
                row,
                title="📄 Заявка",
                reply_markup=admin_order_actions_inline(row["id"], row["status"]),
            )

        has_prev = page > 0
        has_next = offset + PAGE_SIZE < total
        prefix = f"admin_orders_{status_filter}" if status_filter else "admin_orders_all"
        nav = pagination_inline(prefix, page, has_prev, has_next)
        if nav:
            await bot.send_message(chat_id, "Навігація:", reply_markup=nav)

    async def _show_order_history(chat_id: int, order_id: int, bot):
        order = await get_order_row(order_id)
        if not order:
            await bot.send_message(chat_id, "Заявку не знайдено.", reply_markup=admin_menu_kb())
            return

        events = await fetch(
            """
            SELECT *
            FROM order_events
            WHERE order_id=$1
            ORDER BY created_at ASC, id ASC
            """,
            order_id,
        )

        offers_count = await fetchrow(
            "SELECT COUNT(*) AS c FROM offers WHERE order_id=$1",
            order_id,
        )
        complaints_count = await fetchrow(
            "SELECT COUNT(*) AS c FROM complaints WHERE order_id=$1",
            order_id,
        )
        chat_count = await fetchrow(
            "SELECT COUNT(*) AS c FROM chat_messages WHERE order_id=$1",
            order_id,
        )

        lines = [
            f"🧾 <b>Історія заявки #{order_id}</b>",
            "",
            f"📌 Поточний статус: <b>{status_label(order['status'])}</b>",
            f"📬 Пропозицій: <b>{int(offers_count['c'])}</b>",
            f"💬 Повідомлень у чаті: <b>{int(chat_count['c'])}</b>",
            f"⚠️ Скарг: <b>{int(complaints_count['c'])}</b>",
            "",
        ]

        if events:
            lines.append("<b>Події:</b>")
            for ev in events:
                lines.append(
                    f"• {ev['event_type'] or 'event'} | "
                    f"{ev['from_status'] or '—'} → {ev['to_status'] or '—'} | "
                    f"actor={ev['actor_role'] or '—'}:{ev['actor_user_id'] or '—'}"
                )
        else:
            lines.append("<b>Події:</b>")
            lines.append("• Історія подій ще не накопичується окремо.")
            lines.append("• Можна орієнтуватися по статусу, офферах, чатах і скаргах.")

        await bot.send_message(
            chat_id,
            "\n".join(lines),
            reply_markup=admin_order_actions_inline(order_id, order["status"]),
        )

    async def _show_stale_orders(chat_id: int, bot):
        now = now_ts()

        new_without_offers = await fetch(
            """
            SELECT o.*
            FROM orders o
            WHERE o.status='new'
              AND COALESCE(o.created_at, 0) <= $1
              AND NOT EXISTS (
                  SELECT 1 FROM offers f WHERE f.order_id=o.id
              )
            ORDER BY o.created_at ASC
            LIMIT 20
            """,
            now - 30 * 60,
        )

        matched_stale = await fetch(
            """
            SELECT *
            FROM orders
            WHERE status='matched'
              AND COALESCE(updated_at, created_at, 0) <= $1
            ORDER BY updated_at ASC NULLS FIRST, created_at ASC NULLS FIRST
            LIMIT 20
            """,
            now - 2 * 60 * 60,
        )

        in_progress_stale = await fetch(
            """
            SELECT *
            FROM orders
            WHERE status='in_progress'
              AND COALESCE(updated_at, created_at, 0) <= $1
            ORDER BY updated_at ASC NULLS FIRST, created_at ASC NULLS FIRST
            LIMIT 20
            """,
            now - 24 * 60 * 60,
        )

        await bot.send_message(
            chat_id,
            "📦 <b>Завислі заявки</b>\n\n"
            f"🆕 Без офферів 30+ хв: <b>{len(new_without_offers)}</b>\n"
            f"🤝 Matched без руху 2+ год: <b>{len(matched_stale)}</b>\n"
            f"🛠 In progress без руху 24+ год: <b>{len(in_progress_stale)}</b>",
            reply_markup=admin_menu_kb(),
        )

        sections = [
            ("🆕 <b>Без офферів 30+ хв</b>", new_without_offers),
            ("🤝 <b>Matched без руху 2+ год</b>", matched_stale),
            ("🛠 <b>In progress без руху 24+ год</b>", in_progress_stale),
        ]

        for title, rows in sections:
            await bot.send_message(chat_id, title)
            if not rows:
                await bot.send_message(chat_id, "Немає.")
                continue

            for row in rows[:10]:
                await send_order_card(
                    bot,
                    chat_id,
                    row,
                    title="📄 Заявка",
                    reply_markup=admin_order_actions_inline(row["id"], row["status"]),
                )

    async def _show_master_by_user_id(chat_id: int, master_user_id: int, bot):
        row = await fetchrow("SELECT * FROM masters WHERE user_id=$1", master_user_id)
        if not row:
            await bot.send_message(chat_id, "Майстра не знайдено.", reply_markup=admin_menu_kb())
            return

        stats_row = await fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE selected_master_id=$1) AS total_selected,
                COUNT(*) FILTER (WHERE selected_master_id=$1 AND status='done') AS done,
                COUNT(*) FILTER (WHERE selected_master_id=$1 AND status IN ('cancelled','expired')) AS closed_bad,
                COUNT(*) FILTER (WHERE selected_master_id=$1 AND status IN ('matched','in_progress')) AS active
            FROM orders
            """,
            master_user_id,
        )
        complaints_row = await fetchrow(
            "SELECT COUNT(*) AS c FROM complaints WHERE against_user_id=$1 AND against_role='master'",
            master_user_id,
        )

        stats = {
            "total_selected": int(stats_row["total_selected"] or 0),
            "done": int(stats_row["done"] or 0),
            "closed_bad": int(stats_row["closed_bad"] or 0),
            "active": int(stats_row["active"] or 0),
            "complaints": int(complaints_row["c"] or 0),
        }

        await send_master_card(
            bot,
            chat_id,
            row,
            title="👷 Картка майстра",
            reply_markup=admin_master_card_inline(row["id"], row["status"]),
        )
        await bot.send_message(chat_id, _master_summary_text(row, stats), reply_markup=admin_menu_kb())

    async def _preview_broadcast(call_or_message, state: FSMContext, content_type: str, text: str = None, file_id: str = None):
        data = await state.get_data()
        mode = data.get("broadcast_mode")
        recipients_count = int(data.get("broadcast_recipients_count") or 0)

        await state.update_data(
            broadcast_content_type=content_type,
            broadcast_text=text,
            broadcast_file_id=file_id,
        )

        preview_text = (
            "📣 <b>Підтвердження розсилки</b>\n\n"
            f"👥 Одержувачі: <b>{_broadcast_mode_label(mode)}</b>\n"
            f"📊 Кількість: <b>{recipients_count}</b>\n"
            f"🧾 Тип: <b>{content_type}</b>\n\n"
            "Підтвердити відправку?"
        )

        if isinstance(call_or_message, types.Message):
            if content_type == "text":
                await call_or_message.answer(
                    f"{preview_text}\n\n💬 <b>Текст:</b>\n{text}",
                    reply_markup=broadcast_confirm_inline(),
                )
            elif content_type == "photo":
                await call_or_message.answer_photo(
                    file_id,
                    caption=f"{preview_text}\n\n💬 <b>Підпис:</b>\n{text or '—'}",
                    reply_markup=broadcast_confirm_inline(),
                )
            elif content_type == "video":
                await call_or_message.answer_video(
                    file_id,
                    caption=f"{preview_text}\n\n💬 <b>Підпис:</b>\n{text or '—'}",
                    reply_markup=broadcast_confirm_inline(),
                )
        else:
            await call_or_message.message.answer(
                preview_text,
                reply_markup=broadcast_confirm_inline(),
            )

    async def _run_broadcast(bot, admin_chat_id: int, mode: str, content_type: str, text: str = None, file_id: str = None):
        recipient_ids = await _get_unique_recipient_ids(mode)
        sent_count = 0
        failed_count = 0

        for uid in recipient_ids:
            try:
                if content_type == "text":
                    await bot.send_message(uid, text or "")
                elif content_type == "photo":
                    await bot.send_photo(uid, file_id, caption=text or None)
                elif content_type == "video":
                    await bot.send_video(uid, file_id, caption=text or None)
                else:
                    failed_count += 1
                    continue

                sent_count += 1
                await asyncio.sleep(BROADCAST_DELAY_SECONDS)
            except Exception:
                failed_count += 1

        await bot.send_message(
            admin_chat_id,
            "✅ <b>Розсилку завершено</b>\n\n"
            f"👥 Аудиторія: <b>{_broadcast_mode_label(mode)}</b>\n"
            f"📤 Надіслано: <b>{sent_count}</b>\n"
            f"⚠️ Помилок: <b>{failed_count}</b>",
            reply_markup=admin_menu_kb(),
        )

    # =========================
    # ADMIN ROOT
    # =========================

    @dp.message_handler(lambda m: m.text == "👑 Адмін", state="*")
    async def admin_root(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        await state.finish()

        stats = await admin_stats()
        user_stats = await _user_statistics()

        text = (
            "👑 <b>Адмін-панель 2.0</b>\n\n"
            f"📝 На модерації майстрів: <b>{stats['masters_pending']}</b>\n"
            f"🆕 Нових заявок: <b>{stats['orders_new']}</b>\n"
            f"📬 Заявок з пропозиціями: <b>{stats['orders_offered']}</b>\n"
            f"🛠 В роботі: <b>{stats['orders_progress']}</b>\n\n"
            f"👥 Унікальних користувачів: <b>{user_stats['users_total']}</b>\n"
            f"👤 Клієнтів: <b>{user_stats['clients_total']}</b>\n"
            f"👷 Майстрів: <b>{user_stats['masters_total_users']}</b>\n\n"
            "Оберіть розділ нижче 👇"
        )
        await message.answer(text, reply_markup=admin_menu_kb())

    @dp.message_handler(commands=["stats"], state="*")
    async def admin_statistics_command(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        stats = await admin_stats()
        user_stats = await _user_statistics()

        text = (
            "📊 <b>Статистика</b>\n\n"
            f"👥 Всього унікальних користувачів: <b>{user_stats['users_total']}</b>\n"
            f"👤 Клієнтів: <b>{user_stats['clients_total']}</b>\n"
            f"👷 Майстрів: <b>{user_stats['masters_total_users']}</b>\n"
            f"✅ Підтверджених майстрів: <b>{user_stats['masters_approved_users']}</b>\n"
            f"⏳ На перевірці: <b>{user_stats['masters_pending_users']}</b>\n"
            f"🚫 Заблокованих майстрів: <b>{user_stats['masters_blocked_users']}</b>\n\n"
            f"👷 Всього записів майстрів: <b>{stats['masters_total']}</b>\n"
            f"✅ Підтверджених: <b>{stats['masters_approved']}</b>\n"
            f"⏳ На перевірці: <b>{stats['masters_pending']}</b>\n"
            f"🚫 Заблокованих: <b>{stats['masters_blocked']}</b>\n\n"
            f"📦 Всього заявок: <b>{stats['orders_total']}</b>\n"
            f"🆕 Нові: <b>{stats['orders_new']}</b>\n"
            f"📬 Є пропозиції: <b>{stats['orders_offered']}</b>\n"
            f"🤝 Обрано майстра: <b>{stats['orders_matched']}</b>\n"
            f"🛠 В роботі: <b>{stats['orders_progress']}</b>\n"
            f"✅ Завершені: <b>{stats['orders_done']}</b>\n"
            f"❌ Скасовані: <b>{stats['orders_cancelled']}</b>\n"
            f"⌛ Прострочені: <b>{stats['orders_expired']}</b>"
        )
        await message.answer(text, reply_markup=admin_menu_kb())

    @dp.message_handler(lambda m: m.text == "📊 Статистика", state="*")
    async def admin_statistics(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await admin_statistics_command(message, state)

    # =========================
    # BROADCAST
    # =========================

    @dp.message_handler(lambda m: m.text == "📣 СМС розсилка", state="*")
    async def broadcast_menu(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await state.finish()
        await message.answer(
            "📣 <b>СМС розсилка</b>\n\n"
            "Оберіть аудиторію для розсилки.",
            reply_markup=admin_broadcast_menu_kb(),
        )

    @dp.message_handler(lambda m: m.text in {"📣 Всім", "📣 Майстрам", "📣 Клієнтам"}, state="*")
    async def broadcast_choose_audience(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        mode_map = {
            "📣 Всім": "all",
            "📣 Майстрам": "masters",
            "📣 Клієнтам": "clients",
        }
        mode = mode_map[message.text]
        recipient_ids = await _get_unique_recipient_ids(mode)

        await state.finish()
        await state.update_data(
            broadcast_mode=mode,
            broadcast_recipients_count=len(recipient_ids),
        )
        await AdminPanelState.broadcast_compose.set()

        await message.answer(
            "📣 <b>Створення розсилки</b>\n\n"
            f"👥 Аудиторія: <b>{_broadcast_mode_label(mode)}</b>\n"
            f"📊 Одержувачів: <b>{len(recipient_ids)}</b>\n\n"
            "Надішліть одним повідомленням:\n"
            "• текст\n"
            "• або фото з підписом\n"
            "• або відео з підписом",
            reply_markup=admin_broadcast_menu_kb(),
        )

    @dp.message_handler(state=AdminPanelState.broadcast_compose, content_types=types.ContentTypes.TEXT)
    async def broadcast_compose_text(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await state.finish()
            return

        text = (message.text or "").strip()
        if not text or text.startswith("📣 "):
            await message.answer("Надішліть текст розсилки одним повідомленням.")
            return

        await _preview_broadcast(message, state, content_type="text", text=text)

    @dp.message_handler(state=AdminPanelState.broadcast_compose, content_types=types.ContentTypes.PHOTO)
    async def broadcast_compose_photo(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await state.finish()
            return

        file_id = message.photo[-1].file_id if message.photo else None
        caption = message.caption or ""
        if not file_id:
            await message.answer("Не вдалося прочитати фото. Спробуйте ще раз.")
            return

        await _preview_broadcast(message, state, content_type="photo", text=caption, file_id=file_id)

    @dp.message_handler(state=AdminPanelState.broadcast_compose, content_types=types.ContentTypes.VIDEO)
    async def broadcast_compose_video(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await state.finish()
            return

        file_id = message.video.file_id if message.video else None
        caption = message.caption or ""
        if not file_id:
            await message.answer("Не вдалося прочитати відео. Спробуйте ще раз.")
            return

        await _preview_broadcast(message, state, content_type="video", text=caption, file_id=file_id)

    @dp.callback_query_handler(lambda c: c.data == "admin_broadcast_confirm", state="*")
    async def broadcast_confirm(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        data = await state.get_data()
        mode = data.get("broadcast_mode")
        content_type = data.get("broadcast_content_type")
        text = data.get("broadcast_text")
        file_id = data.get("broadcast_file_id")

        if not mode or not content_type:
            await state.finish()
            await call.message.answer(
                "Не вдалося підготувати розсилку.",
                reply_markup=admin_menu_kb(),
            )
            await call.answer()
            return

        await call.message.answer(
            "⏳ <b>Розсилку запущено</b>\n\n"
            "Будь ласка, зачекайте завершення.",
            reply_markup=admin_menu_kb(),
        )
        await call.answer("Запускаю")

        await _run_broadcast(
            dp.bot,
            call.message.chat.id,
            mode=mode,
            content_type=content_type,
            text=text,
            file_id=file_id,
        )
        await state.finish()

    @dp.callback_query_handler(lambda c: c.data == "admin_broadcast_cancel", state="*")
    async def broadcast_cancel(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        await state.finish()
        await call.message.answer(
            "❌ <b>Розсилку скасовано</b>",
            reply_markup=admin_menu_kb(),
        )
        await call.answer("Скасовано")

    # =========================
    # MASTERS
    # =========================

    @dp.message_handler(lambda m: m.text == "📝 Модерація майстрів", state="*")
    async def pending_masters(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await _show_pending_masters(message.chat.id, 0, dp.bot)

    @dp.callback_query_handler(lambda c: c.data.startswith("pending_masters_"), state="*")
    async def pending_masters_page(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        page = int(call.data.split("_")[-1])
        await _show_pending_masters(call.message.chat.id, page, dp.bot)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_approve_master_"), state="*")
    async def admin_approve_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        master_id = int(call.data.split("_")[-1])
        master = await get_master_by_id(master_id)
        if not master:
            await call.answer("Майстра не знайдено", show_alert=True)
            return

        await set_master_status_by_id(master_id, "approved", "offline")

        try:
            await dp.bot.send_message(
                master["user_id"],
                "✅ <b>Ваш профіль підтверджено</b>\n\nТепер ви будете отримувати нові заявки у своїй категорії.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(master["user_id"])),
            )
        except Exception:
            pass

        await call.message.answer("✅ Майстра підтверджено.")
        await call.answer("Готово")

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_reject_master_"), state="*")
    async def admin_reject_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        master_id = int(call.data.split("_")[-1])
        master = await get_master_by_id(master_id)
        if not master:
            await call.answer("Майстра не знайдено", show_alert=True)
            return

        await delete_master_by_id(master_id)

        try:
            await dp.bot.send_message(
                master["user_id"],
                "❌ <b>Анкету не підтверджено</b>\n\nЗаповніть профіль ще раз уважніше.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(master["user_id"])),
            )
        except Exception:
            pass

        await call.message.answer("❌ Анкету відхилено.")
        await call.answer("Готово")

    @dp.message_handler(lambda m: m.text == "👷 Майстри", state="*")
    async def admin_masters(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await _show_admin_masters(message.chat.id, 0, dp.bot)

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_masters_"), state="*")
    async def admin_masters_page(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        page = int(call.data.split("_")[-1])
        await _show_admin_masters(call.message.chat.id, page, dp.bot)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_block_master_"), state="*")
    async def admin_block_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        master_id = int(call.data.split("_")[-1])
        master = await get_master_by_id(master_id)
        if not master:
            await call.answer("Майстра не знайдено", show_alert=True)
            return

        await set_master_status_by_id(master_id, "blocked", "offline")

        try:
            await dp.bot.send_message(
                master["user_id"],
                "🚫 <b>Ваш профіль заблоковано</b>\n\nЗверніться в підтримку, якщо вважаєте це помилкою.",
            )
        except Exception:
            pass

        await call.message.answer("🚫 Майстра заблоковано.")
        await call.answer("Готово")

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_unblock_master_"), state="*")
    async def admin_unblock_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        master_id = int(call.data.split("_")[-1])
        master = await get_master_by_id(master_id)
        if not master:
            await call.answer("Майстра не знайдено", show_alert=True)
            return

        await set_master_status_by_id(master_id, "approved", "offline")

        try:
            await dp.bot.send_message(
                master["user_id"],
                "✅ <b>Ваш профіль знову активний</b>\n\nТепер ви можете отримувати заявки.",
            )
        except Exception:
            pass

        await call.message.answer("✅ Майстра розблоковано.")
        await call.answer("Готово")

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_delete_master_"), state="*")
    async def admin_delete_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        master_id = int(call.data.split("_")[-1])
        master = await get_master_by_id(master_id)
        if not master:
            await call.answer("Майстра не знайдено", show_alert=True)
            return

        await delete_master_by_id(master_id)

        try:
            await dp.bot.send_message(
                master["user_id"],
                "🗑 <b>Ваш профіль видалено адміністратором</b>",
            )
        except Exception:
            pass

        await call.message.answer("🗑 Майстра видалено.")
        await call.answer("Готово")

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_open_master_by_user_"), state="*")
    async def admin_open_master_by_user(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return
        master_user_id = int(call.data.split("_")[-1])
        await _show_master_by_user_id(call.message.chat.id, master_user_id, dp.bot)
        await call.answer()

    # =========================
    # ORDERS
    # =========================

    @dp.message_handler(lambda m: m.text == "📦 Заявки", state="*")
    async def admin_orders(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        await state.finish()
        await message.answer("📦 <b>Фільтр заявок</b>", reply_markup=admin_orders_filter_kb())

    @dp.message_handler(lambda m: m.text in STATUS_FILTER_MAP.keys(), state="*")
    async def admin_orders_by_filter(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        status_filter = STATUS_FILTER_MAP[message.text]
        await _show_admin_orders(message.chat.id, 0, dp.bot, status_filter)

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_orders_"), state="*")
    async def admin_orders_page(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        parts = call.data.split("_")
        page = int(parts[-1])
        status_filter = parts[2] if len(parts) == 4 else None
        if status_filter == "all":
            status_filter = None

        await _show_admin_orders(call.message.chat.id, page, dp.bot, status_filter)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_order_detail_"), state="*")
    async def admin_order_detail(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        order_id = int(call.data.split("_")[-1])
        order = await get_order_row(order_id)
        if not order:
            await call.answer("Заявку не знайдено", show_alert=True)
            return

        offers = await list_order_offers(order_id)
        await send_admin_order_detail(dp.bot, call.message.chat.id, order, offers)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_order_history_"), state="*")
    async def admin_order_history(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return
        order_id = int(call.data.split("_")[-1])
        await _show_order_history(call.message.chat.id, order_id, dp.bot)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_expire_order_"), state="*")
    async def admin_expire_order(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        order_id = int(call.data.split("_")[-1])
        await set_order_status(order_id, "expired")
        await close_chat(order_id)
        await call.message.answer("⌛ Заявку позначено як неактуальну.")
        await call.answer("Готово")

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_progress_order_"), state="*")
    async def admin_progress_order(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        order_id = int(call.data.split("_")[-1])
        row = await fetchrow("SELECT selected_master_id FROM orders WHERE id=$1", order_id)
        selected_master_id = row["selected_master_id"] if row else None

        await set_order_status(order_id, "in_progress", selected_master_id)
        await call.message.answer("🛠 Заявку переведено в статус 'в роботі'.")
        await call.answer("Готово")

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_done_order_"), state="*")
    async def admin_done_order(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        order_id = int(call.data.split("_")[-1])
        row = await fetchrow("SELECT selected_master_id FROM orders WHERE id=$1", order_id)
        selected_master_id = row["selected_master_id"] if row else None

        await set_order_status(order_id, "done", selected_master_id)
        await close_chat(order_id)
        await call.message.answer("🏁 Заявку завершено.")
        await call.answer("Готово")

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_reset_order_"), state="*")
    async def admin_reset_order(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        order_id = int(call.data.split("_")[-1])
        await set_order_status(order_id, "new", None)
        await close_chat(order_id)
        await call.message.answer("🔄 Заявку повернуто в статус 'нова'.")
        await call.answer("Готово")

    # =========================
    # SEARCH
    # =========================

    @dp.message_handler(lambda m: m.text == "🔎 Пошук заявки", state="*")
    async def search_order_start(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await state.finish()
        await AdminPanelState.order_id.set()
        await message.answer(
            "🔎 <b>Пошук заявки</b>\n\nВведіть ID заявки числом.",
            reply_markup=admin_menu_kb(),
        )

    @dp.message_handler(state=AdminPanelState.order_id, content_types=types.ContentTypes.TEXT)
    async def search_order_finish(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await state.finish()
            return

        text = (message.text or "").strip()
        if not text.isdigit():
            await message.answer("Введіть коректний ID заявки числом.")
            return

        order_id = int(text)
        order = await get_order_row(order_id)
        if not order:
            await state.finish()
            await message.answer("Заявку не знайдено.", reply_markup=admin_menu_kb())
            return

        offers = await list_order_offers(order_id)
        await send_admin_order_detail(dp.bot, message.chat.id, order, offers)
        await _show_order_history(message.chat.id, order_id, dp.bot)
        await state.finish()

    @dp.message_handler(lambda m: m.text == "🔎 Пошук користувача", state="*")
    async def search_user_start(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await state.finish()
        await AdminPanelState.user_id.set()
        await message.answer(
            "🔎 <b>Пошук користувача</b>\n\nВведіть user_id клієнта.",
            reply_markup=admin_menu_kb(),
        )

    @dp.message_handler(state=AdminPanelState.user_id, content_types=types.ContentTypes.TEXT)
    async def search_user_finish(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await state.finish()
            return

        text = (message.text or "").strip()
        if not text.isdigit():
            await message.answer("Введіть коректний user_id числом.")
            return

        user_id = int(text)
        rows = await fetch(
            """
            SELECT *
            FROM orders
            WHERE user_id=$1
            ORDER BY created_at DESC, id DESC
            LIMIT 20
            """,
            user_id,
        )

        await state.finish()

        if not rows:
            await message.answer("Заявок цього користувача не знайдено.", reply_markup=admin_menu_kb())
            return

        await message.answer(
            f"👤 <b>Користувач {user_id}</b>\nЗнайдено заявок: <b>{len(rows)}</b>",
            reply_markup=admin_menu_kb(),
        )

        for row in rows:
            await send_order_card(
                dp.bot,
                message.chat.id,
                row,
                title="📄 Заявка користувача",
                reply_markup=admin_order_actions_inline(row["id"], row["status"]),
            )

    @dp.message_handler(lambda m: m.text == "🔎 Пошук майстра", state="*")
    async def search_master_start(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await state.finish()
        await AdminPanelState.master_user_id.set()
        await message.answer(
            "🔎 <b>Пошук майстра</b>\n\nВведіть user_id майстра.",
            reply_markup=admin_menu_kb(),
        )

    @dp.message_handler(state=AdminPanelState.master_user_id, content_types=types.ContentTypes.TEXT)
    async def search_master_finish(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await state.finish()
            return

        text = (message.text or "").strip()
        if not text.isdigit():
            await message.answer("Введіть коректний user_id числом.")
            return

        master_user_id = int(text)
        await state.finish()
        await _show_master_by_user_id(message.chat.id, master_user_id, dp.bot)

    # =========================
    # STALE ORDERS
    # =========================

    @dp.message_handler(lambda m: m.text == "📦 Завислі заявки", state="*")
    async def stale_orders(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await _show_stale_orders(message.chat.id, dp.bot)

    # =========================
    # COMPLAINTS
    # =========================

    @dp.message_handler(lambda m: m.text == "⚠️ Скарги", state="*")
    async def admin_complaints(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        rows = await fetch(
            """
            SELECT *
            FROM complaints
            ORDER BY id DESC
            LIMIT 20
            """
        )

        if not rows:
            await message.answer(
                "⚠️ <b>Скарг поки немає</b>",
                reply_markup=admin_menu_kb(),
            )
            return

        await message.answer(
            "⚠️ <b>Останні скарги</b>",
            reply_markup=admin_menu_kb(),
        )

        for row in rows:
            text = (
                f"⚠️ <b>Скарга #{row['id']}</b>\n\n"
                f"🆔 <b>Заявка:</b> #{row['order_id']}\n"
                f"👤 <b>Від кого:</b> <code>{row['from_user_id']}</code>\n"
                f"🎯 <b>На кого:</b> {row['against_role']} "
                f"(<code>{row['against_user_id']}</code>)\n\n"
                f"💬 <b>Текст:</b>\n{row['text']}"
            )
            await message.answer(
                text,
                reply_markup=admin_complaint_actions_inline(
                    row["id"], row["order_id"], row["against_user_id"]
                ),
            )

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_delete_complaint_"), state="*")
    async def admin_delete_complaint(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return
        complaint_id = int(call.data.split("_")[-1])
        await execute("DELETE FROM complaints WHERE id=$1", complaint_id)
        await call.message.answer("🗑 Скаргу видалено.")
        await call.answer("Готово")

    # =========================
    # SUPPORT REPLY
    # =========================

    @dp.callback_query_handler(lambda c: c.data.startswith("support_reply_"), state="*")
    async def support_reply_start(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer()
            return

        user_id = int(call.data.split("_")[-1])
        await state.finish()
        await state.update_data(support_target_user_id=user_id)
        await AdminPanelState.support_reply.set()

        await call.message.answer(
            f"↩️ <b>Відповідь користувачу</b>\n\n"
            f"ID: <code>{user_id}</code>\n\n"
            "Напишіть текст відповіді одним повідомленням.",
            reply_markup=admin_menu_kb(),
        )
        await call.answer()

    @dp.message_handler(state=AdminPanelState.support_reply, content_types=types.ContentTypes.TEXT)
    async def support_reply_send(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            await state.finish()
            return

        data = await state.get_data()
        user_id = data.get("support_target_user_id")
        text = (message.text or "").strip()

        if not user_id:
            await state.finish()
            await message.answer(
                "Не вдалося визначити користувача.",
                reply_markup=admin_menu_kb(),
            )
            return

        if not text or len(text) < 2:
            await message.answer("Напишіть нормальну відповідь.")
            return

        reply_text = (
            "🛎 <b>Відповідь від підтримки</b>\n\n"
            f"{text}"
        )

        try:
            await dp.bot.send_message(user_id, reply_text)
        except Exception:
            await message.answer(
                "Не вдалося надіслати повідомлення користувачу. Можливо, він не відкривав бота.",
                reply_markup=admin_menu_kb(),
            )
            await state.finish()
            return

        await state.finish()
        await message.answer(
            "✅ Відповідь надіслано користувачу.",
            reply_markup=admin_menu_kb(),
        )
