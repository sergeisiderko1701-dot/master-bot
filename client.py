import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from constants import CATEGORY_LABEL_TO_VALUE, category_label
from keyboards import (
    back_menu_kb,
    categories_kb,
    client_actions_kb,
    main_menu_kb,
    offer_select_inline,
)
from repositories import (
    client_active_orders_count,
    create_order,
    fetch,
    fetchrow,
    get_cooldown,
    get_order_row,
    list_client_orders,
    list_order_offers,
    set_cooldown,
)
from services import notify_admin_about_order, notify_masters_about_order, send_master_card, send_order_card
from states import ClientCreateOrder
from ui_texts import (
    ask_district_text,
    ask_media_text,
    ask_problem_text,
    choose_category_text,
    client_actions_text,
    order_created_text,
)
from utils import is_admin, normalize_text, now_ts


logger = logging.getLogger(__name__)

BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}
SKIP_WORDS = {"пропустити", "skip", "-"}
CHANGE_CATEGORY_BUTTONS = {"🔄 Змінити спеціальність", "🔧 Змінити спеціальність"}


def register(dp):
    @dp.message_handler(lambda m: m.text == "👤 Клієнт", state="*")
    async def client_menu(message: types.Message, state: FSMContext):
        data = await state.get_data()
        category = data.get("client_category")

        await state.finish()

        if category:
            await state.update_data(client_category=category)
            await message.answer(
                client_actions_text(category),
                reply_markup=client_actions_kb(),
            )
            return

        await message.answer(
            choose_category_text(),
            reply_markup=categories_kb(),
        )

    @dp.message_handler(lambda m: m.text in CHANGE_CATEGORY_BUTTONS, state="*")
    async def change_category(message: types.Message, state: FSMContext):
        await state.update_data(client_category=None)
        await message.answer(
            choose_category_text(),
            reply_markup=categories_kb(),
        )

    @dp.message_handler(lambda m: m.text in BACK_BUTTONS, state="*")
    async def back_handler(message: types.Message, state: FSMContext):
        current_state = await state.get_state()
        data = await state.get_data()

        if current_state in (
            ClientCreateOrder.district.state,
            ClientCreateOrder.problem.state,
            ClientCreateOrder.media.state,
        ):
            category = data.get("client_category")
            await state.finish()

            if category:
                await state.update_data(client_category=category)
                await message.answer(
                    client_actions_text(category),
                    reply_markup=client_actions_kb(),
                )
            else:
                await message.answer(
                    choose_category_text(),
                    reply_markup=categories_kb(),
                )
            return

        category = data.get("client_category")
        if category:
            await message.answer(
                client_actions_text(category),
                reply_markup=client_actions_kb(),
            )
            return

        await message.answer(
            choose_category_text(),
            reply_markup=categories_kb(),
        )

    @dp.message_handler(lambda m: m.text in CATEGORY_LABEL_TO_VALUE.keys(), state="*")
    async def choose_category(message: types.Message, state: FSMContext):
        category = CATEGORY_LABEL_TO_VALUE[message.text]
        await state.update_data(client_category=category)
        await message.answer(
            client_actions_text(category),
            reply_markup=client_actions_kb(),
        )

    @dp.message_handler(lambda m: m.text == "📨 Створити заявку", state="*")
    async def create_order_start(message: types.Message, state: FSMContext):
        data = await state.get_data()
        category = data.get("client_category")

        if not category:
            await message.answer(
                "Спочатку оберіть категорію.",
                reply_markup=categories_kb(),
            )
            return

        prev = await get_cooldown(message.from_user.id, "client_create_order")
        current = now_ts()

        if current - prev < settings.client_order_cooldown:
            left_seconds = settings.client_order_cooldown - (current - prev)
            await message.answer(
                f"Зачекайте {left_seconds} сек перед новою заявкою.",
                reply_markup=client_actions_kb(),
            )
            return

        active_count = await client_active_orders_count(message.from_user.id)
        if active_count >= settings.max_active_client_orders:
            await message.answer(
                "У вас вже занадто багато активних заявок.",
                reply_markup=client_actions_kb(),
            )
            return

        await ClientCreateOrder.district.set()
        await message.answer(
            ask_district_text(),
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(state=ClientCreateOrder.district, content_types=types.ContentTypes.TEXT)
    async def client_order_district(message: types.Message, state: FSMContext):
        district = normalize_text(message.text, 255)

        if not district:
            await message.answer(
                "Будь ласка, вкажіть район або адресу коротко.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(district=district)
        await ClientCreateOrder.problem.set()
        await message.answer(
            ask_problem_text(),
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(state=ClientCreateOrder.problem, content_types=types.ContentTypes.TEXT)
    async def client_order_problem(message: types.Message, state: FSMContext):
        problem = normalize_text(message.text, 1500)

        if not problem or len(problem) < 5:
            await message.answer(
                "Опишіть проблему трохи детальніше.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(problem=problem)
        await ClientCreateOrder.media.set()
        await message.answer(
            ask_media_text(),
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=ClientCreateOrder.media)
    async def client_order_media(message: types.Message, state: FSMContext):
        data = await state.get_data()
        media_type = None
        media_file_id = None
        text = (message.text or "").strip().lower()

        if message.photo:
            media_type = "photo"
            media_file_id = message.photo[-1].file_id
        elif message.video:
            media_type = "video"
            media_file_id = message.video.file_id
        elif text in SKIP_WORDS:
            pass
        else:
            await message.answer(
                "Надішліть фото, відео або напишіть 'пропустити'.",
                reply_markup=back_menu_kb(),
            )
            return

        order_id = await create_order(
            user_id=message.from_user.id,
            category=data["client_category"],
            district=data.get("district", ""),
            problem=data.get("problem", ""),
            media_type=media_type,
            media_file_id=media_file_id,
        )

        await set_cooldown(
            message.from_user.id,
            "client_create_order",
            now_ts(),
        )

        order_row = await get_order_row(order_id)

        masters = await fetch(
            """
            SELECT user_id, category, status
            FROM masters
            WHERE status='approved'
            """
        )

        order_category = (data["client_category"] or "").strip()
        filtered_masters = []

        for master in masters:
            master_category = (master["category"] or "").strip()
            if master_category == order_category:
                filtered_masters.append(master)

        logger.info("ORDER ID=%s CATEGORY=%s", order_id, order_category)
        logger.info("APPROVED MASTERS FOUND=%s", len(masters))
        logger.info("FILTERED MASTERS FOR ORDER=%s", len(filtered_masters))

        try:
            await notify_admin_about_order(dp.bot, settings.admin_id, order_row)
        except Exception as e:
            logger.warning("Помилка повідомлення адміну по заявці %s: %s", order_id, e)

        try:
            await notify_masters_about_order(dp.bot, order_row, filtered_masters)
        except Exception as e:
            logger.warning("Помилка розсилки майстрам по заявці %s: %s", order_id, e)

        await state.finish()
        await state.update_data(client_category=order_category)

        await message.answer(
            order_created_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(lambda m: m.text == "👷 Переглянути майстрів", state="*")
    async def view_masters(message: types.Message, state: FSMContext):
        data = await state.get_data()
        category = data.get("client_category")

        if not category:
            await message.answer(
                "Спочатку оберіть категорію.",
                reply_markup=categories_kb(),
            )
            return

        rows = await fetch(
            """
            SELECT *
            FROM masters
            WHERE status='approved' AND category=$1
            ORDER BY rating DESC, reviews_count DESC, name ASC
            LIMIT 20
            """,
            category,
        )

        if not rows:
            await message.answer(
                "У цій категорії поки немає підтверджених майстрів.",
                reply_markup=client_actions_kb(),
            )
            return

        await message.answer(
            f"👷 Майстри в категорії: {category_label(category)}",
            reply_markup=client_actions_kb(),
        )

        for row in rows:
            try:
                await send_master_card(
                    dp.bot,
                    message.chat.id,
                    row,
                    title="👷 Майстер",
                )
            except Exception:
                continue

    @dp.message_handler(lambda m: m.text == "📦 Мої заявки", state="*")
    async def my_orders(message: types.Message, state: FSMContext):
        rows = await list_client_orders(message.from_user.id)

        if not rows:
            await message.answer(
                "У вас поки немає заявок.",
                reply_markup=client_actions_kb(),
            )
            return

        await message.answer(
            "📦 Ваші заявки:",
            reply_markup=client_actions_kb(),
        )

        from keyboards import client_order_actions_inline

        for row in rows[:20]:
            try:
                await send_order_card(
                    dp.bot,
                    message.chat.id,
                    row,
                    title="📄 Ваша заявка",
                    reply_markup=client_order_actions_inline(row["id"], row["status"]),
                )
            except Exception:
                continue

    @dp.callback_query_handler(lambda c: c.data.startswith("client_offers_"), state="*")
    async def client_offers(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])

        order = await fetchrow(
            "SELECT * FROM orders WHERE id=$1 AND user_id=$2",
            order_id,
            call.from_user.id,
        )

        if not order:
            await call.answer("Вашу заявку не знайдено.", show_alert=True)
            return

        if order["status"] in ("cancelled", "done", "expired"):
            await call.answer("Ця заявка вже закрита.", show_alert=True)
            return

        offers = await list_order_offers(order_id)

        if not offers:
            await call.message.answer("По цій заявці поки немає пропозицій.")
            await call.answer()
            return

        await call.message.answer(
            f"📬 <b>Пропозиції по заявці #{order_id}</b>\n\n"
            f"Оберіть майстра, який підходить найкраще 👇"
        )

        for offer in offers:
            text = (
                f"💼 <b>Пропозиція</b>\n\n"
                f"👤 Майстер: {offer['name']}\n"
                f"⭐ {float(offer['rating']):.2f} | відгуків: {offer['reviews_count']}\n"
                f"💰 Ціна: {offer['price']}\n"
                f"⏱ Коли зможе: {offer['eta']}\n"
                f"📝 Коментар: {offer['comment']}"
            )
            await call.message.answer(
                text,
                reply_markup=offer_select_inline(offer["id"]),
            )

        await call.answer()
