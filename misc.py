from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from constants import status_label
from keyboards import admin_menu_kb, admin_orders_filter_kb, main_menu_kb, pagination_inline, support_reply_inline
from repositories import (
    admin_stats,
    delete_master_by_id,
    fetch,
    fetchrow,
    get_master_by_id,
    get_order_row,
    list_admin_masters,
    list_admin_orders,
    list_pending_masters,
    list_order_offers,
    set_master_status_by_id,
    set_order_status,
    close_chat,
)
from services import send_admin_order_detail, send_master_card, send_order_card
from states import SupportReply
from utils import is_admin, normalize_text, now_ts


def register(dp):
    @dp.message_handler(lambda m: m.text == "👑 Адмін", state="*")
    async def admin_panel(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await state.finish()
        await message.answer("👑 Адмін панель:", reply_markup=admin_menu_kb())

    @dp.message_handler(lambda m: m.text == "👷 База майстрів", state="*")
    async def masters_page(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await show_admin_masters_page(message.chat.id, 0)

    @dp.message_handler(lambda m: m.text == "📝 Заявки майстрів", state="*")
    async def pending_page(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await show_pending_masters_page(message.chat.id, 0)

    @dp.message_handler(lambda m: m.text == "📦 Заявки клієнтів", state="*")
    async def orders_filter(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await message.answer("Оберіть фільтр заявок:", reply_markup=admin_orders_filter_kb())

    @dp.message_handler(lambda m: m.text == "📊 Статистика", state="*")
    async def stats(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        data = await admin_stats()
        text = (
            f"📊 Статистика\n\n"
            f"👷 Усього майстрів: {data['masters_total']}\n"
            f"✅ Підтверджені: {data['masters_approved']}\n"
            f"📝 На модерації: {data['masters_pending']}\n"
            f"🚫 Заблоковані: {data['masters_blocked']}\n\n"
            f"📦 Усього заявок: {data['orders_total']}\n"
            f"🆕 Нові: {data['orders_new']}\n"
            f"📬 Є пропозиції: {data['orders_offered']}\n"
            f"🤝 Обрано майстра: {data['orders_matched']}\n"
            f"🛠 В роботі: {data['orders_progress']}\n"
            f"✅ Завершені: {data['orders_done']}\n"
            f"❌ Скасовані: {data['orders_cancelled']}\n"
            f"⌛ Прострочені: {data['orders_expired']}"
        )
        await message.answer(text, reply_markup=admin_menu_kb())

    async def show_pending_masters_page(chat_id: int, page: int):
        offset = page * settings.page_size
        rows, total = await list_pending_masters(settings.page_size, offset)
        if not rows:
            await dp.bot.send_message(chat_id, "Немає заявок майстрів на модерацію.", reply_markup=admin_menu_kb())
            return
        await dp.bot.send_message(chat_id, f"📝 Заявки майстрів (сторінка {page + 1}):")
        from keyboards import admin_pending_master_inline
        for row in rows:
            await send_master_card(dp.bot, chat_id, row, title="📝 Заявка майстра", reply_markup=admin_pending_master_inline(row["id"]))
        pag = pagination_inline("page_pending_masters", page, page > 0, offset + settings.page_size < total)
        if pag:
            await dp.bot.send_message(chat_id, "Навігація:", reply_markup=pag)

    async def show_admin_masters_page(chat_id: int, page: int):
        offset = page * settings.page_size
        rows, total = await list_admin_masters(settings.page_size, offset)
        if not rows:
            await dp.bot.send_message(chat_id, "У базі немає майстрів.", reply_markup=admin_menu_kb())
            return
        await dp.bot.send_message(chat_id, f"👷 База майстрів (сторінка {page + 1}):")
        from keyboards import admin_master_card_inline
        for row in rows:
            await send_master_card(dp.bot, chat_id, row, title="📄 Майстер", reply_markup=admin_master_card_inline(row["id"], row["status"]))
        pag = pagination_inline("page_masters", page, page > 0, offset + settings.page_size < total)
        if pag:
            await dp.bot.send_message(chat_id, "Навігація:", reply_markup=pag)

    async def show_admin_orders_page(chat_id: int, page: int, status_filter=None):
        offset = page * settings.page_size
        rows, total = await list_admin_orders(settings.page_size, offset, status_filter)
        if not rows:
            await dp.bot.send_message(chat_id, "Заявок немає.", reply_markup=admin_orders_filter_kb())
            return
        title = "📦 Заявки клієнтів"
        if status_filter:
            title += f" — {status_label(status_filter)}"
        title += f" (сторінка {page + 1})"
        await dp.bot.send_message(chat_id, title)
        from keyboards import admin_order_actions_inline
        for row in rows:
            await send_order_card(dp.bot, chat_id, row, title="📄 Заявка", reply_markup=admin_order_actions_inline(row["id"], row["status"]))
        prefix = f"page_orders_{status_filter or 'all'}"
        pag = pagination_inline(prefix, page, page > 0, offset + settings.page_size < total)
        if pag:
            await dp.bot.send_message(chat_id, "Навігація:", reply_markup=pag)

    ORDER_FILTERS = {
        "📋 Усі заявки": None,
        "🆕 Нові": "new",
        "📬 Є пропозиції": "offered",
        "🤝 Обрано майстра": "matched",
        "🛠 В роботі": "in_progress",
        "✅ Завершені": "done",
        "❌ Скасовані": "cancelled",
        "⌛ Прострочені": "expired",
    }

    @dp.message_handler(lambda m: m.text in ORDER_FILTERS, state="*")
    async def filter_orders(message: types.Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        await show_admin_orders_page(message.chat.id, 0, ORDER_FILTERS[message.text])

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_approve_master_"), state="*")
    async def approve_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer("Недоступно", show_alert=True)
            return
        master_id = int(call.data.split("_")[-1])
        master = await fetchrow("SELECT * FROM masters WHERE id=$1 AND status='pending'", master_id)
        if not master:
            await call.answer("Заявку не знайдено", show_alert=True)
            return
        await set_master_status_by_id(master_id, "approved")
        try:
            await dp.bot.send_message(master["user_id"], "✅ Вашу заявку схвалено. Ви тепер майстер.")
        except Exception:
            pass
        await call.message.answer("✅ Майстра підтверджено.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_reject_master_"), state="*")
    async def reject_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            await call.answer("Недоступно", show_alert=True)
            return
        master_id = int(call.data.split("_")[-1])
        master = await fetchrow("SELECT * FROM masters WHERE id=$1 AND status='pending'", master_id)
        if not master:
            await call.answer("Заявку не знайдено", show_alert=True)
            return
        await delete_master_by_id(master_id)
        try:
            await dp.bot.send_message(master["user_id"], "❌ Вашу заявку майстра відхилено.")
        except Exception:
            pass
        await call.message.answer("❌ Заявку майстра відхилено.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_block_master_"), state="*")
    async def block_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        master_id = int(call.data.split("_")[-1])
        master = await get_master_by_id(master_id)
        if not master:
            await call.answer("Майстра не знайдено", show_alert=True)
            return
        await set_master_status_by_id(master_id, "blocked", "offline")
        try:
            await dp.bot.send_message(master["user_id"], "🚫 Ваш профіль майстра заблоковано.")
        except Exception:
            pass
        await call.message.answer("🚫 Майстра заблоковано.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_unblock_master_"), state="*")
    async def unblock_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        master_id = int(call.data.split("_")[-1])
        master = await get_master_by_id(master_id)
        if not master:
            await call.answer("Майстра не знайдено", show_alert=True)
            return
        await set_master_status_by_id(master_id, "approved")
        try:
            await dp.bot.send_message(master["user_id"], "✅ Ваш профіль майстра розблоковано.")
        except Exception:
            pass
        await call.message.answer("✅ Майстра розблоковано.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_delete_master_"), state="*")
    async def delete_master(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        master_id = int(call.data.split("_")[-1])
        master = await get_master_by_id(master_id)
        if not master:
            await call.answer("Майстра не знайдено", show_alert=True)
            return
        await delete_master_by_id(master_id)
        try:
            await dp.bot.send_message(master["user_id"], "🗑 Ваш профіль майстра видалено адміністратором.")
        except Exception:
            pass
        await call.message.answer("🗑 Майстра видалено.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_order_detail_"), state="*")
    async def order_detail(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
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
    async def expire_order(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        order_id = int(call.data.split("_")[-1])
        order = await get_order_row(order_id)
        if not order:
            await call.answer("Заявку не знайдено", show_alert=True)
            return
        await set_order_status(order_id, "expired", order["selected_master_id"])
        await close_chat(order_id)
        await call.message.answer("⌛ Заявку закрито як неактуальну.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_progress_order_"), state="*")
    async def progress_order(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        order_id = int(call.data.split("_")[-1])
        order = await get_order_row(order_id)
        if not order:
            await call.answer("Заявку не знайдено", show_alert=True)
            return
        await set_order_status(order_id, "in_progress", order["selected_master_id"])
        await call.message.answer("🛠 Заявку переведено в статус «в роботі».")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_done_order_"), state="*")
    async def done_order(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        order_id = int(call.data.split("_")[-1])
        order = await get_order_row(order_id)
        if not order:
            await call.answer("Заявку не знайдено", show_alert=True)
            return
        await set_order_status(order_id, "done", order["selected_master_id"])
        await close_chat(order_id)
        await call.message.answer("🏁 Заявку завершено адміністратором.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("admin_reset_order_"), state="*")
    async def reset_order(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        order_id = int(call.data.split("_")[-1])
        order = await get_order_row(order_id)
        if not order:
            await call.answer("Заявку не знайдено", show_alert=True)
            return
        await set_order_status(order_id, "new", None)
        await close_chat(order_id)
        await call.message.answer("🔄 Заявку повернуто в нові.")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("support_reply_"), state="*")
    async def support_reply(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        await state.update_data(support_target_user_id=int(call.data.split("_")[-1]))
        await SupportReply.text.set()
        await call.message.answer("Напишіть відповідь користувачу:")
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("page_masters_"), state="*")
    async def page_masters(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        await show_admin_masters_page(call.message.chat.id, int(call.data.split("_")[-1]))
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("page_pending_masters_"), state="*")
    async def page_pending(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        await show_pending_masters_page(call.message.chat.id, int(call.data.split("_")[-1]))
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("page_orders_"), state="*")
    async def page_orders(call: types.CallbackQuery, state: FSMContext):
        if not is_admin(call.from_user.id):
            return
        data = call.data.replace("page_orders_", "", 1)
        status_part, page_str = data.rsplit("_", 1)
        status_filter = None if status_part == "all" else status_part
        await show_admin_orders_page(call.message.chat.id, int(page_str), status_filter)
        await call.answer()
