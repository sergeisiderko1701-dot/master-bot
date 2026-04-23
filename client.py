import logging
import re

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from anti_fake import evaluate_order_antifake
from config import settings
from constants import CATEGORY_LABEL_TO_VALUE
from keyboards import (
    back_menu_kb,
    categories_kb,
    client_actions_kb,
    client_order_actions_inline,
    main_menu_kb,
    offer_select_inline,
)
from repositories import (
    cancel_order,
    client_active_orders_count,
    create_order,
    get_cooldown,
    get_order_row,
    get_recent_client_order_count,
    has_duplicate_recent_problem,
    list_approved_masters_for_category,
    list_client_orders,
    list_order_offers,
    set_cooldown,
)
from security import allow_callback_action, allow_message_action
from services import notify_admin_about_order, notify_masters_about_order, send_order_card
from states import ClientCreateOrder
from ui_texts import (
    ask_district_text,
    ask_media_text,
    ask_problem_text,
    choose_category_text,
    client_actions_text,
    order_created_text,
    order_sent_to_review_text,
    tip_after_category,
    tip_before_submit,
    tip_choose_master,
)
from utils import is_admin, normalize_text, now_ts


logger = logging.getLogger(__name__)

BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}
SKIP_WORDS = {"пропустити", "skip", "-"}
CHANGE_CATEGORY_BUTTONS = {
    "🔄 Змінити спеціальність",
    "🔧 Змінити спеціальність",
}

BAD_WORDS = {
    "тест",
    "test",
    "asdf",
    "qwerty",
    "12345",
    "фігня",
}


def is_bad_problem_text(text: str) -> bool:
    low = (text or "").lower()
    if len(low) < 10:
        return True
    return any(word in low for word in BAD_WORDS)


def normalize_phone(value: str) -> str:
    raw = (value or "").strip()
    raw = raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if raw.startswith("8"):
        raw = "+3" + raw
    if raw.startswith("380"):
        raw = "+" + raw
    return raw


def is_valid_phone(value: str) -> bool:
    return bool(re.fullmatch(r"\+380\d{9}", value or ""))


def request_contact_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📲 Поділитися номером", request_contact=True))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


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
            ClientCreateOrder.phone.state,
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
        await message.answer(tip_after_category())

    @dp.message_handler(lambda m: m.text == "📨 Створити заявку", state="*")
    async def create_order_start(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="client_create_order_click",
            limit=5,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

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

        if not problem or is_bad_problem_text(problem):
            await message.answer(
                "Опишіть проблему трохи конкретніше. Короткий або тестовий текст не підходить.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(problem=problem)
        await ClientCreateOrder.phone.set()
        await message.answer(
            "📞 <b>Ваш номер телефону</b>\n\n"
            "Можете:\n"
            "• натиснути кнопку <b>📲 Поділитися номером</b>\n"
            "• або написати номер вручну у форматі <b>+380XXXXXXXXX</b>\n\n"
            "Ми покажемо його тільки тому майстру, якого ви самі оберете.",
            reply_markup=request_contact_kb(),
        )

    @dp.message_handler(state=ClientCreateOrder.phone, content_types=types.ContentTypes.CONTACT)
    async def client_order_phone_contact(message: types.Message, state: FSMContext):
        if not message.contact:
            await message.answer(
                "Не вдалося отримати контакт. Спробуйте ще раз.",
                reply_markup=request_contact_kb(),
            )
            return
        if message.contact.user_id and message.contact.user_id != message.from_user.id:
            await message.answer(
                "Будь ласка, надішліть саме <b>свій</b> номер кнопкою <b>📲 Поділитися номером</b>.",
                reply_markup=request_contact_kb(),
            )
            return


        phone = normalize_phone(message.contact.phone_number)

        if not is_valid_phone(phone):
            await message.answer(
                "Номер із контакту виглядає некоректно. Надішліть правильний номер або введіть вручну у форматі <b>+380XXXXXXXXX</b>.",
                reply_markup=request_contact_kb(),
            )
            return

        await state.update_data(client_phone=phone)
        await ClientCreateOrder.media.set()
        await message.answer(
            ask_media_text(),
            reply_markup=back_menu_kb(),
        )
        await message.answer(tip_before_submit())

    @dp.message_handler(state=ClientCreateOrder.phone, content_types=types.ContentTypes.TEXT)
    async def client_order_phone_text(message: types.Message, state: FSMContext):
        text = (message.text or "").strip()

        if text in BACK_BUTTONS:
            category = (await state.get_data()).get("client_category")
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

        phone = normalize_phone(text)

        if not is_valid_phone(phone):
            await message.answer(
                "Введіть коректний номер у форматі <b>+380XXXXXXXXX</b> або натисніть кнопку <b>📲 Поділитися номером</b>.",
                reply_markup=request_contact_kb(),
            )
            return

        await state.update_data(client_phone=phone)
        await ClientCreateOrder.media.set()
        await message.answer(
            ask_media_text(),
            reply_markup=back_menu_kb(),
        )
        await message.answer(tip_before_submit())

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=ClientCreateOrder.media)
    async def client_order_media(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="client_finish_order_form",
            limit=8,
            window_seconds=120,
            mute_seconds=300,
        )
        if not allowed:
            return

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

        recent_orders_count = await get_recent_client_order_count(message.from_user.id, 3600)
        duplicate_problem = await has_duplicate_recent_problem(
            message.from_user.id,
            data.get("problem", ""),
            7,
        )

        has_media = bool(media_file_id)
        antifake = evaluate_order_antifake(
            problem=data.get("problem", ""),
            phone=data.get("client_phone", ""),
            recent_orders_count=recent_orders_count,
            duplicate_problem=duplicate_problem,
            has_media=has_media,
        )

        moderation_status = "pending_review" if antifake.is_suspect else "approved"

        order_id = await create_order(
            user_id=message.from_user.id,
            category=data["client_category"],
            district=data.get("district", ""),
            problem=data.get("problem", ""),
            media_type=media_type,
            media_file_id=media_file_id,
            client_phone=data.get("client_phone"),
            is_suspect=antifake.is_suspect,
            suspicion_score=antifake.score,
            suspicion_reasons="\n".join(antifake.reasons) if antifake.reasons else None,
            moderation_status=moderation_status,
        )

        await set_cooldown(
            message.from_user.id,
            "client_create_order",
            now_ts(),
        )

        order_row = await get_order_row(order_id)

        logger.info(
            "ORDER CREATED id=%s category=%s suspect=%s score=%s moderation=%s",
            order_id,
            data["client_category"],
            antifake.is_suspect,
            antifake.score,
            moderation_status,
        )

        try:
            await notify_admin_about_order(dp.bot, settings.admin_id, order_row)
        except Exception as e:
            logger.warning("Помилка повідомлення адміну по заявці %s: %s", order_id, e)

        await state.finish()
        await state.update_data(client_category=data["client_category"])

        if antifake.is_suspect:
            try:
                reasons_text = "\n".join(f"• {item}" for item in antifake.reasons) if antifake.reasons else "• автоматична перевірка"
                await dp.bot.send_message(
                    settings.admin_id,
                    (
                        f"🕵️ <b>Нова підозріла заявка</b>\n\n"
                        f"🆔 #{order_id}\n"
                        f"👤 user_id: <code>{message.from_user.id}</code>\n"
                        f"📞 Телефон: {data.get('client_phone') or '—'}\n"
                        f"📝 Проблема: {data.get('problem') or '—'}\n\n"
                        f"⚠️ Причини:\n{reasons_text}"
                    ),
                )
            except Exception as e:
                logger.warning("Помилка повідомлення адміну про підозрілу заявку %s: %s", order_id, e)

            await message.answer(
                order_sent_to_review_text(order_id, antifake.reasons),
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        masters = await list_approved_masters_for_category(data["client_category"])
        logger.info("FILTERED MASTERS FOR ORDER=%s -> %s", order_id, len(masters))

        try:
            await notify_masters_about_order(dp.bot, order_row, masters)
        except Exception as e:
            logger.warning("Помилка розсилки майстрам по заявці %s: %s", order_id, e)

        await message.answer(
            order_created_text(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

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
        allowed = await allow_callback_action(
            call,
            action_key="client_open_offers",
            limit=15,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        order_id = int(call.data.split("_")[-1])

        order = await get_order_row(order_id)

        if not order or order["user_id"] != call.from_user.id:
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
            "Оберіть майстра, який підходить найкраще 👇"
        )
        await call.message.answer(tip_choose_master())

        for offer in offers:
            rating = float(offer["rating"] or 0)
            reviews = int(offer["reviews_count"] or 0)
            online = "🟢 Онлайн" if (offer.get("availability") == "online") else "⚪ Офлайн"

            text = (
                f"💼 <b>Пропозиція</b>\n\n"
                f"👤 Майстер: {offer['name']}\n"
                f"{online}\n"
                f"⭐ {rating:.2f} | відгуків: {reviews}\n"
                f"💰 Ціна: {offer['price']}\n"
                f"⏱ Коли зможе: {offer['eta']}\n"
                f"📝 Коментар: {offer['comment']}"
            )
            await call.message.answer(
                text,
                reply_markup=offer_select_inline(offer["id"]),
            )

        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("client_cancel_"), state="*")
    async def client_cancel_order(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="client_cancel_order",
            limit=10,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        order_id = int(call.data.split("_")[-1])

        logger.info(
            "CLIENT CANCEL CLICK user_id=%s order_id=%s",
            call.from_user.id,
            order_id,
        )

        order = await get_order_row(order_id)

        if not order or order["user_id"] != call.from_user.id:
            await call.answer("Заявку не знайдено.", show_alert=True)
            return

        if order["status"] not in {"new", "offered", "matched"}:
            await call.answer(
                "Заявку вже не можна скасувати.",
                show_alert=True,
            )
            return

        try:
            await cancel_order(order_id, call.from_user.id)
            logger.info(
                "CLIENT CANCEL SUCCESS user_id=%s order_id=%s",
                call.from_user.id,
                order_id,
            )
        except Exception as e:
            logger.exception(
                "CLIENT CANCEL FAILED user_id=%s order_id=%s error=%s",
                call.from_user.id,
                order_id,
                e,
            )
            await call.answer("Не вдалося скасувати заявку.", show_alert=True)
            return

        await call.message.answer(
            f"❌ <b>Заявку #{order_id} скасовано</b>",
            reply_markup=client_actions_kb(),
        )
        await call.answer("Готово")
