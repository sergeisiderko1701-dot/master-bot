from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from keyboards import (
    back_menu_kb,
    chat_reply_kb,
    client_order_actions_inline,
    exit_chat_inline,
    main_menu_kb,
    offer_select_inline,
    selected_order_master_actions,
)
from repositories import (
    approved_master_row,
    choose_offer,
    create_chat_message,
    create_offer,
    fetchrow,
    get_chat_for_order,
    get_chat_history,
    get_cooldown,
    get_order_row,
    master_active_orders_count,
    set_cooldown,
    touch_master_presence,
)
from services import send_chat_history
from states import ChatFlow, OfferCreate
from ui_texts import chat_media_caption, chat_open_text, chat_text_message, offer_card_text
from utils import is_admin, normalize_text, now_ts


BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}
SKIP_WORDS = {"пропустити", "skip", "-"}


def register(dp):
    async def get_offer_full_row(offer_id: int):
        return await fetchrow(
            """
            SELECT
                offers.id,
                offers.order_id,
                offers.master_user_id,
                offers.price,
                offers.eta,
                offers.comment,
                offers.status,
                masters.name,
                masters.rating,
                masters.reviews_count
            FROM offers
            JOIN masters ON masters.user_id = offers.master_user_id
            WHERE offers.id=$1
            """,
            offer_id,
        )

    async def send_offer_to_client(client_user_id: int, order_id: int, offer_id: int):
        offer = await get_offer_full_row(offer_id)
        if not offer:
            return

        await dp.bot.send_message(
            client_user_id,
            f"📬 <b>Нова пропозиція по заявці #{order_id}</b>",
        )
        await dp.bot.send_message(
            client_user_id,
            offer_card_text(offer),
            reply_markup=offer_select_inline(offer_id),
        )

    async def open_chat_for_user(
        call: types.CallbackQuery,
        state: FSMContext,
        *,
        order_id: int,
        role: str,
        target_user_id: int,
        chat_id: int,
        is_client: bool,
    ):
        await state.update_data(
            chat_role=role,
            order_id=order_id,
            target_user_id=target_user_id,
            chat_id=chat_id,
        )
        await ChatFlow.message.set()
        await call.message.answer(
            chat_open_text(order_id, is_client),
            reply_markup=chat_reply_kb(),
        )
        await call.answer()

    # =========================
    # OFFERS FLOW
    # =========================

    @dp.callback_query_handler(lambda c: c.data.startswith("offer_start_"), state="*")
    async def offer_start(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])

        master = await approved_master_row(call.from_user.id)
        if not master:
            await call.answer("Доступно тільки підтвердженим майстрам.", show_alert=True)
            return

        await touch_master_presence(call.from_user.id)

        if await master_active_orders_count(call.from_user.id) >= settings.max_active_master_orders:
            await call.answer("У вас уже максимум активних заявок.", show_alert=True)
            return

        last_offer_at = await get_cooldown(call.from_user.id, "master_create_offer")
        current_ts = now_ts()
        if current_ts - last_offer_at < settings.master_offer_cooldown:
            left = settings.master_offer_cooldown - (current_ts - last_offer_at)
            await call.answer(f"Зачекайте {left} сек перед новим відгуком.", show_alert=True)
            return

        order = await fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id=$1
              AND category=$2
              AND status = ANY($3::text[])
            """,
            order_id,
            master["category"],
            ["new", "offered"],
        )

        if not order:
            await call.answer("Заявка недоступна або вже закрита.", show_alert=True)
            return

        await state.finish()
        await state.update_data(offer_order_id=order_id)
        await OfferCreate.price.set()

        await call.message.answer(
            f"💰 <b>Відгук на заявку #{order_id}</b>\n\nВкажіть ціну або діапазон.\n"
            f"Наприклад: <b>800 грн</b> або <b>800–1200 грн</b>",
            reply_markup=back_menu_kb(),
        )
        await call.answer()

    @dp.message_handler(state=OfferCreate.price, content_types=types.ContentTypes.TEXT)
    async def offer_price(message: types.Message, state: FSMContext):
        text = (message.text or "").strip()

        if text in BACK_BUTTONS:
            await state.finish()
            await message.answer(
                "Відгук скасовано.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        price = normalize_text(message.text, 100)

        if not price or len(price) < 2:
            await message.answer(
                "Вкажіть коректну ціну.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(offer_price=price)
        await OfferCreate.eta.set()
        await message.answer(
            "⏱ <b>Коли зможете?</b>\n\nНапишіть коротко.\nНаприклад: <b>через 1 годину</b> або <b>сьогодні до 18:00</b>",
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(state=OfferCreate.eta, content_types=types.ContentTypes.TEXT)
    async def offer_eta(message: types.Message, state: FSMContext):
        text = (message.text or "").strip()

        if text in BACK_BUTTONS:
            await state.finish()
            await message.answer(
                "Відгук скасовано.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        eta = normalize_text(message.text, 120)

        if not eta or len(eta) < 2:
            await message.answer(
                "Напишіть, коли зможете взяти заявку.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(offer_eta=eta)
        await OfferCreate.comment.set()
        await message.answer(
            "📝 <b>Коментар</b>\n\nНапишіть короткий коментар або <b>пропустити</b>.",
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(state=OfferCreate.comment, content_types=types.ContentTypes.TEXT)
    async def offer_comment(message: types.Message, state: FSMContext):
        text = (message.text or "").strip()

        if text in BACK_BUTTONS:
            await state.finish()
            await message.answer(
                "Відгук скасовано.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        data = await state.get_data()
        order_id = data.get("offer_order_id")

        if not order_id:
            await state.finish()
            await message.answer(
                "Не вдалося визначити заявку.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        master = await approved_master_row(message.from_user.id)
        if not master:
            await state.finish()
            await message.answer(
                "Ваш профіль майстра недоступний.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        comment = None if text.lower() in SKIP_WORDS else normalize_text(message.text, 1000)
        comment = comment or "Без коментаря"

        offer_id = await create_offer(
            order_id=order_id,
            master_user_id=message.from_user.id,
            price=data["offer_price"],
            eta=data["offer_eta"],
            comment=comment,
        )

        if not offer_id:
            await state.finish()
            await message.answer(
                "Не вдалося створити пропозицію. Можливо, заявка вже неактуальна.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await set_cooldown(message.from_user.id, "master_create_offer", now_ts())

        order = await get_order_row(order_id)
        if order:
            try:
                await send_offer_to_client(order["user_id"], order_id, offer_id)
            except Exception:
                pass

        await state.finish()
        await message.answer(
            "✅ <b>Пропозицію надіслано клієнту</b>",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("choose_offer_"), state="*")
    async def choose_offer_handler(call: types.CallbackQuery, state: FSMContext):
        offer_id = int(call.data.split("_")[-1])

        selected_offer = await choose_offer(offer_id, call.from_user.id)
        if not selected_offer:
            await call.answer("Не вдалося обрати цю пропозицію.", show_alert=True)
            return

        offer_full = await get_offer_full_row(offer_id)
        order_id = int(selected_offer["order_id"])
        order = await get_order_row(order_id)

        await call.message.answer(
            "✅ <b>Майстра обрано</b>\n\nТепер ви можете перейти в чат по заявці.",
            reply_markup=client_order_actions_inline(order_id, "matched"),
        )

        if offer_full:
            try:
                await dp.bot.send_message(
                    offer_full["master_user_id"],
                    f"🎉 <b>Вашу пропозицію обрано по заявці #{order_id}</b>\n\n"
                    f"Тепер можете перейти в чат з клієнтом.",
                    reply_markup=selected_order_master_actions(order_id),
                )
            except Exception:
                pass

        if order:
            try:
                await dp.bot.send_message(
                    order["user_id"],
                    f"💬 <b>Чат по заявці #{order_id} вже доступний</b>",
                    reply_markup=client_order_actions_inline(order_id, "matched"),
                )
            except Exception:
                pass

        await call.answer("Пропозицію обрано")

    # =========================
    # CHAT FLOW
    # =========================

    @dp.callback_query_handler(lambda c: c.data.startswith("client_chat_"), state="*")
    async def client_chat(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])

        order = await fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id=$1
              AND user_id=$2
              AND selected_master_id IS NOT NULL
              AND status = ANY($3::text[])
            """,
            order_id,
            call.from_user.id,
            ["matched", "in_progress"],
        )
        if not order:
            await call.answer("Чат недоступний", show_alert=True)
            return

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active" or chat["client_user_id"] != call.from_user.id:
            await call.answer("Чат не знайдено", show_alert=True)
            return

        await open_chat_for_user(
            call,
            state,
            order_id=order_id,
            role="client",
            target_user_id=chat["master_user_id"],
            chat_id=chat["id"],
            is_client=True,
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("master_chat_open_"), state="*")
    async def master_chat(call: types.CallbackQuery, state: FSMContext):
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
            await call.answer("Чат недоступний", show_alert=True)
            return

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active" or chat["master_user_id"] != call.from_user.id:
            await call.answer("Чат не знайдено", show_alert=True)
            return

        await touch_master_presence(call.from_user.id)

        await open_chat_for_user(
            call,
            state,
            order_id=order_id,
            role="master",
            target_user_id=chat["client_user_id"],
            chat_id=chat["id"],
            is_client=False,
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("chat_history_"), state="*")
    async def history(call: types.CallbackQuery, state: FSMContext):
        order_id = int(call.data.split("_")[-1])

        chat = await get_chat_for_order(order_id)
        if not chat:
            await call.answer("Чат не знайдено", show_alert=True)
            return

        if call.from_user.id not in (chat["client_user_id"], chat["master_user_id"]):
            await call.answer("Доступ заборонено", show_alert=True)
            return

        msgs = await get_chat_history(order_id, 30)
        await send_chat_history(dp.bot, call.message.chat.id, order_id, msgs)
        await call.answer()

    @dp.message_handler(lambda m: m.text == "📜 Історія", state=ChatFlow.message)
    async def history_from_chat(message: types.Message, state: FSMContext):
        data = await state.get_data()
        msgs = await get_chat_history(data["order_id"], 30)
        await send_chat_history(dp.bot, message.chat.id, data["order_id"], msgs)

    @dp.message_handler(lambda m: m.text == "❌ Закрити чат", state=ChatFlow.message)
    async def close_chat_reply(message: types.Message, state: FSMContext):
        await state.finish()
        await message.answer(
            "💬 <b>Чат закрито</b>\n\nПовертаю вас у головне меню.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=ChatFlow.message)
    async def relay_chat(message: types.Message, state: FSMContext):
        data = await state.get_data()
        target_id = data["target_user_id"]
        role = data["chat_role"]
        order_id = data["order_id"]
        chat_id = data["chat_id"]

        try:
            if role == "master":
                await touch_master_presence(message.from_user.id)

            if message.photo:
                caption = normalize_text(message.caption or "", 1000)
                await create_chat_message(
                    chat_id,
                    order_id,
                    message.from_user.id,
                    role,
                    "photo",
                    caption,
                    message.photo[-1].file_id,
                )
                await dp.bot.send_photo(
                    target_id,
                    message.photo[-1].file_id,
                    caption=chat_media_caption(order_id, role, caption, "📷"),
                    reply_markup=exit_chat_inline(),
                )
                await message.answer("📷 <b>Фото надіслано</b>", reply_markup=chat_reply_kb())
                return

            if message.video:
                caption = normalize_text(message.caption or "", 1000)
                await create_chat_message(
                    chat_id,
                    order_id,
                    message.from_user.id,
                    role,
                    "video",
                    caption,
                    message.video.file_id,
                )
                await dp.bot.send_video(
                    target_id,
                    message.video.file_id,
                    caption=chat_media_caption(order_id, role, caption, "📹"),
                    reply_markup=exit_chat_inline(),
                )
                await message.answer("📹 <b>Відео надіслано</b>", reply_markup=chat_reply_kb())
                return

            text = normalize_text(message.text or "", 1500)
            if not text:
                await message.answer(
                    "Напишіть повідомлення текстом або надішліть фото / відео.",
                    reply_markup=chat_reply_kb(),
                )
                return

            await create_chat_message(
                chat_id,
                order_id,
                message.from_user.id,
                role,
                "text",
                text,
                None,
            )
            await dp.bot.send_message(
                target_id,
                chat_text_message(order_id, role, text),
                reply_markup=exit_chat_inline(),
            )
            await message.answer("✅ <b>Повідомлення надіслано</b>", reply_markup=chat_reply_kb())

        except Exception:
            await message.answer(
                "Не вдалося переслати повідомлення. Спробуйте ще раз.",
                reply_markup=chat_reply_kb(),
            )
