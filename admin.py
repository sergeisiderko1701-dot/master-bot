from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from constants import status_label
from keyboards import (
    admin_master_card_inline,
    admin_menu_kb,
    admin_order_actions_inline,
    admin_orders_filter_kb,
    admin_pending_master_inline,
    main_menu_kb,
    pagination_inline,
)
from repositories import (
    admin_stats,
    close_chat,
    delete_master_by_id,
    fetch,
    fetchrow,
    get_master_by_id,
    get_master_name,
    get_order_row,
    list_admin_masters,
    list_admin_orders,
    list_order_offers,
    list_pending_masters,
    set_master_status_by_id,
    set_order_status,
)
from services import send_admin_order_detail, send_master_card, send_order_card
from states import SupportReply
from utils import is_admin


PAGE_SIZE = settings.page_size


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


def register(dp):
    @dp.message_handler(lambda m: m.text == "👑 Адмін", state="*")
    async def admin_menu(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        await state.finish()

        stats = await admin_stats()
        text = (
            "👑 <b>Адмін-панель</b>\n\n"
            f"📝 На модерації майстрів: <b>{stats['masters_pending']}</b>\n"
            f"🆕 Нових заявок: <b>{stats['orders_new']}</b>\n"
            f"📬 Заявок з пропозиціями: <b>{stats['orders_offered']}</b>\n"
            f"🛠 В роботі: <b>{stats['orders_progress']}</b>\n\n"
            "Оберіть розділ нижче 👇"
        )
        await message.answer(text, reply_markup=admin_menu_kb())

    @dp.message_handler(lambda m: m.text == "📊 Статистика", state="*")
    async def admin_statistics(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return

        stats = await admin_stats()
        text = (
            "📊 <b>Статистика</b>\n\n"
            f"👷 Всього майстрів: <b>{stats['masters_total']}</b>\n"
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
            master_name = await get_master_name(row["selected_master_id"])
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
            await message.answer(text)

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
        await SupportReply.text.set()

        await call.message.answer(
            f"↩️ <b>Відповідь користувачу</b>\n\n"
            f"ID: <code>{user_id}</code>\n\n"
            "Напишіть текст відповіді одним повідомленням.",
            reply_markup=admin_menu_kb(),
        )
        await call.answer()

    @dp.message_handler(state=SupportReply.text, content_types=types.ContentTypes.TEXT)
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
