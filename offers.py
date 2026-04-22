import logging

from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from constants import parse_categories
from keyboards import (
    back_menu_kb,
    chat_reply_kb,
    client_order_actions_inline,
    exit_chat_inline,
    main_menu_kb,
    offer_select_inline,
    rating_inline,
    selected_order_master_actions,
)
from repositories import (
    add_complaint,
    approved_master_row,
    choose_offer,
    create_chat_message,
    create_offer,
    fetchrow,
    finish_order,
    get_chat_for_order,
    get_chat_history,
    get_cooldown,
    get_order_row,
    list_order_offers,
    master_active_offers_count,
    master_active_orders_count,
    rate_order,
    refuse_order,
    set_cooldown,
    touch_master_presence,
)
from security import allow_callback_action, allow_message_action
from services import send_chat_history
from states import ChatFlow, ComplaintWrite, OfferCreate, RatingFlow
from ui_texts import (
    chat_media_caption,
    chat_open_text,
    chat_text_message,
    client_master_selected_text,
    master_selected_for_master_text,
    offer_card_text,
    rating_thanks,
    tip_master_offer,
    tip_master_selected,
    tip_no_response,
)
from utils import is_admin, normalize_text, now_ts


logger = logging.getLogger(__name__)

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
                masters.reviews_count,
                masters.phone,
                masters.category,
                masters.availability,
                masters.last_seen
            FROM offers
            JOIN masters ON masters.user_id = offers.master_user_id
            WHERE offers.id=$1
            """,
            offer_id,
        )

    async def send_offer_to_client(client_user_id: int, order_id: int, offer_id: int):
        offer = await get_offer_full_row(offer_id)
        if not offer:
            logger.warning("Offer %s not found for client notification", offer_id)
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

    def _safe_val(row, key, default=None):
        try:
            value = row[key]
            return default if value is None else value
        except Exception:
            return default

    async def _get_actual_client_markup(order_id: int):
        order = await get_order_row(order_id)
        actual_status = order["status"] if order else "matched"
        return client_order_actions_inline(order_id, actual_status)

    async def _get_actual_master_markup(order_id: int):
        order = await get_order_row(order_id)
        if order and order["status"] in {"matched", "in_progress"}:
            return selected_order_master_actions(order_id)
        return main_menu_kb()

    async def _after_dialog_markup(role: str, order_id: int):
        if role == "client":
            return await _get_actual_client_markup(order_id)
        return await _get_actual_master_markup(order_id)

    def build_client_contact_text(user: types.User, order_row) -> str:
        full_name = " ".join(
            part for part in [user.first_name, user.last_name] if part
        ).strip() or "Клієнт"
        username_line = f"🔗 Username: @{user.username}\n" if user.username else ""
        tg_link = f'<a href="tg://user?id={user.id}">{full_name}</a>'
        phone_line = (
            f"📞 Телефон: {_safe_val(order_row, 'client_phone')}\n"
            if _safe_val(order_row, "client_phone")
            else ""
        )

        return (
            "👤 <b>Контакти клієнта</b>\n\n"
            f"Ім'я: {full_name}\n"
            f"{phone_line}"
            f"{username_line}"
            f"Telegram: {tg_link}\n"
            f"ID: <code>{user.id}</code>\n\n"
            "Контакти відкрито після того, як клієнт обрав вас."
        )

    async def share_contacts_after_choose(call: types.CallbackQuery, order_id: int, offer_full):
        order_row = await get_order_row(order_id)

        try:
            await dp.bot.send_message(
                call.from_user.id,
                client_master_selected_text(
                    master_name=_safe_val(offer_full, "name", "Майстер"),
                    phone=_safe_val(offer_full, "phone", "—"),
                    rating=_safe_val(offer_full, "rating"),
                    reviews_count=_safe_val(offer_full, "reviews_count"),
                    eta=_safe_val(offer_full, "eta"),
                ),
                reply_markup=client_order_actions_inline(order_id, "matched"),
            )
            await dp.bot.send_message(call.from_user.id, tip_no_response())
        except Exception as e:
            logger.warning(
                "Не вдалося надіслати контакти майстра клієнту %s: %s",
                call.from_user.id,
                e,
            )

        try:
            await dp.bot.send_message(
                offer_full["master_user_id"],
                (
                    f"{master_selected_for_master_text(order_id)}\n\n"
                    f"{build_client_contact_text(call.from_user, order_row)}"
                ),
                reply_markup=selected_order_master_actions(order_id),
            )
            await dp.bot.send_message(offer_full["master_user_id"], tip_master_selected())
        except Exception as e:
            logger.warning(
                "Не вдалося надіслати контакти клієнта майстру %s: %s",
                offer_full["master_user_id"],
                e,
            )

    async def start_dialog_write(
        message_or_call,
        state: FSMContext,
        *,
        order_id: int,
        role: str,
        target_user_id: int,
        chat_id: int,
        is_client: bool,
    ):
        await state.finish()
        await state.update_data(
            chat_role=role,
            order_id=order_id,
            target_user_id=target_user_id,
            chat_id=chat_id,
        )
        await ChatFlow.message.set()

        text = (
            f"{chat_open_text(order_id, is_client=is_client)}\n\n"
            "Ви можете надсилати кілька повідомлень підряд.\n"
            "Щоб вийти — натисніть <b>❌ Закрити</b>."
        )

        if isinstance(message_or_call, types.CallbackQuery):
            await message_or_call.message.answer(text, reply_markup=chat_reply_kb())
            await message_or_call.answer()
        else:
            await message_or_call.answer(text, reply_markup=chat_reply_kb())

    @dp.callback_query_handler(lambda c: c.data.startswith("offer_start_"), state="*")
    async def offer_start(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="master_offer_start",
            limit=12,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        order_id = int(call.data.split("_")[-1])

        master = await approved_master_row(call.from_user.id)
        if not master:
            await call.answer("Доступно тільки підтвердженим майстрам.", show_alert=True)
            return

        await touch_master_presence(call.from_user.id)

        if await master_active_orders_count(call.from_user.id) >= settings.max_active_master_orders:
            await call.answer("У вас уже максимум активних заявок.", show_alert=True)
            return

        if await master_active_offers_count(call.from_user.id) >= settings.max_active_master_offers:
            await call.answer(
                f"У вас уже максимум активних відгуків ({settings.max_active_master_offers}). "
                f"Дочекайтесь вибору клієнта або закриття частини заявок.",
                show_alert=True,
            )
            return

        last_offer_at = await get_cooldown(call.from_user.id, "master_create_offer")
        current_ts = now_ts()
        if current_ts - last_offer_at < settings.master_offer_cooldown:
            left = settings.master_offer_cooldown - (current_ts - last_offer_at)
            await call.answer(
                f"Зачекайте {left} сек перед новим відгуком.",
                show_alert=True,
            )
            return

        master_categories = parse_categories(master["category"])
        if not master_categories:
            await call.answer("У вашому профілі не налаштовані категорії.", show_alert=True)
            return

        order = await fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id=$1
              AND category = ANY($2::text[])
              AND status = ANY($3::text[])
            """,
            order_id,
            master_categories,
            ["new", "offered"],
        )

        if not order:
            await call.answer("Заявка недоступна або вже закрита.", show_alert=True)
            return

        await state.finish()
        await state.update_data(offer_order_id=order_id)
        await OfferCreate.price.set()

        await call.message.answer(
            f"💰 <b>Відгук на заявку #{order_id}</b>\n\n"
            "Вкажіть ціну або діапазон.\n"
            "Наприклад: <b>800 грн</b> або <b>800–1200 грн</b>",
            reply_markup=back_menu_kb(),
        )
        await call.message.answer(tip_master_offer())
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
            "⏱ <b>Коли зможете?</b>\n\n"
            "Напишіть коротко.\n"
            "Наприклад: <b>через 1 годину</b> або <b>сьогодні до 18:00</b>",
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
            "📝 <b>Коментар</b>\n\n"
            "Напишіть короткий коментар або <b>пропустити</b>.",
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(state=OfferCreate.comment, content_types=types.ContentTypes.TEXT)
    async def offer_comment(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="master_offer_finish",
            limit=10,
            window_seconds=120,
            mute_seconds=300,
        )
        if not allowed:
            return

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

        if await master_active_offers_count(message.from_user.id) >= settings.max_active_master_offers:
            await state.finish()
            await message.answer(
                f"У вас уже максимум активних відгуків ({settings.max_active_master_offers}). "
                f"Дочекайтесь вибору клієнта або закриття частини заявок.",
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
                "Не вдалося створити пропозицію. Можливо, заявка вже неактуальна, ви вже відгукувались або досягли ліміту активних відгуків.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await set_cooldown(message.from_user.id, "master_create_offer", now_ts())

        order = await get_order_row(order_id)
        if order:
            try:
                await send_offer_to_client(order["user_id"], order_id, offer_id)
            except Exception as e:
                logger.warning(
                    "Не вдалося надіслати оффер клієнту по заявці %s: %s",
                    order_id,
                    e,
                )

        await state.finish()
        await message.answer(
            "✅ <b>Пропозицію надіслано клієнту</b>\n\n"
            "Якщо клієнт обере вас, контакти відкриються автоматично.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("choose_offer_"), state="*")
    async def choose_offer_handler(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="client_choose_offer",
            limit=10,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        offer_id = int(call.data.split("_")[-1])

        selected_offer = await choose_offer(offer_id, call.from_user.id)
        if not selected_offer:
            await call.answer("Не вдалося обрати цю пропозицію.", show_alert=True)
            return

        offer_full = await get_offer_full_row(offer_id)
        order_id = int(selected_offer["order_id"])

        if offer_full:
            await share_contacts_after_choose(call, order_id, offer_full)

        await call.answer("Пропозицію обрано")

    @dp.callback_query_handler(lambda c: c.data.startswith("finish_order_"), state="*")
    async def finish_order_handler(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="master_finish_order",
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
            await call.answer("Заявка недоступна для завершення.", show_alert=True)
            return

        await finish_order(order_id)

        await call.message.answer(
            f"🏁 <b>Заявку #{order_id} завершено</b>",
            reply_markup=main_menu_kb(is_admin_user=is_admin(call.from_user.id)),
        )

        try:
            await dp.bot.send_message(
                order["user_id"],
                (
                    f"🏁 <b>Заявку #{order_id} позначено як завершену</b>\n\n"
                    "Будь ласка, оцініть майстра від 1 до 5 ⭐"
                ),
                reply_markup=rating_inline(order_id),
            )
        except Exception as e:
            logger.warning("Не вдалося надіслати клієнту запит на рейтинг по заявці %s: %s", order_id, e)

        await call.answer("Заявку завершено")

    @dp.callback_query_handler(lambda c: c.data.startswith("refuse_order_"), state="*")
    async def refuse_order_handler(call: types.CallbackQuery, state: FSMContext):
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
                client_text = (
                    f"❌ <b>Майстер відмовився від заявки #{order_id}</b>\n\n"
                    "Заявка знову відкрита для нових пропозицій майстрів.\n"
                    "Щойно хтось відгукнеться — ви побачите це в боті."
                )
                actual_status = updated_order["status"] if updated_order else "new"
                client_markup = client_order_actions_inline(order_id, actual_status)

            await dp.bot.send_message(
                order["user_id"],
                client_text,
                reply_markup=client_markup,
            )

            if active_offers:
                await dp.bot.send_message(
                    order["user_id"],
                    f"📬 <b>Доступних пропозицій зараз:</b> {len(active_offers)}",
                )

        except Exception as e:
            logger.warning("Не вдалося повідомити клієнта про відмову по заявці %s: %s", order_id, e)

        await call.answer("Відмову збережено")

    @dp.callback_query_handler(lambda c: c.data.startswith("complain_master_"), state="*")
    async def complain_master_start(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="complain_master_start",
            limit=6,
            window_seconds=60,
            mute_seconds=600,
        )
        if not allowed:
            return

        order_id = int(call.data.split("_")[-1])

        order = await fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id=$1
              AND user_id=$2
              AND selected_master_id IS NOT NULL
            """,
            order_id,
            call.from_user.id,
        )
        if not order:
            await call.answer("Скаргу не можна подати.", show_alert=True)
            return

        await state.finish()
        await state.update_data(
            complaint_order_id=order_id,
            against_user_id=order["selected_master_id"],
            against_role="master",
            complaint_return_role="client",
        )
        await ComplaintWrite.text.set()

        await call.message.answer(
            "⚠️ <b>Скарга на майстра</b>\n\n"
            "Напишіть коротко, що сталося.\n"
            "Повідомлення отримає адміністратор.",
            reply_markup=back_menu_kb(),
        )
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("complain_client_"), state="*")
    async def complain_client_start(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="complain_client_start",
            limit=6,
            window_seconds=60,
            mute_seconds=600,
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
            """,
            order_id,
            call.from_user.id,
        )
        if not order:
            await call.answer("Скаргу не можна подати.", show_alert=True)
            return

        await state.finish()
        await state.update_data(
            complaint_order_id=order_id,
            against_user_id=order["user_id"],
            against_role="client",
            complaint_return_role="master",
        )
        await ComplaintWrite.text.set()

        await call.message.answer(
            "⚠️ <b>Скарга на клієнта</b>\n\n"
            "Напишіть коротко, що сталося.\n"
            "Повідомлення отримає адміністратор.",
            reply_markup=back_menu_kb(),
        )
        await call.answer()

    @dp.message_handler(state=ComplaintWrite.text, content_types=types.ContentTypes.TEXT)
    async def complaint_send(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="complaint_send",
            limit=5,
            window_seconds=300,
            mute_seconds=900,
        )
        if not allowed:
            return

        text = normalize_text(message.text, 1500)
        data = await state.get_data()

        order_id = data.get("complaint_order_id")
        against_user_id = data.get("against_user_id")
        against_role = data.get("against_role")
        return_role = data.get("complaint_return_role")

        if not order_id or not against_user_id or not against_role:
            await state.finish()
            await message.answer(
                "Не вдалося зберегти скаргу.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        if not text or len(text) < 5:
            await message.answer(
                "Опишіть проблему трохи детальніше.",
                reply_markup=back_menu_kb(),
            )
            return

        try:
            await add_complaint(
                order_id=order_id,
                from_user_id=message.from_user.id,
                against_user_id=against_user_id,
                against_role=against_role,
                text=text,
            )

            username_line = f"🔗 Username: @{message.from_user.username}\n" if message.from_user.username else ""
            admin_text = (
                "⚠️ <b>Нова скарга</b>\n\n"
                f"🆔 <b>Заявка:</b> #{order_id}\n"
                f"👤 <b>Від кого:</b> {message.from_user.full_name}\n"
                f"🆔 <b>ID автора:</b> <code>{message.from_user.id}</code>\n"
                f"{username_line}"
                f"🎯 <b>На кого:</b> {against_role}\n"
                f"🆔 <b>ID відповідача:</b> <code>{against_user_id}</code>\n\n"
                f"💬 <b>Текст скарги:</b>\n{text}"
            )

            await dp.bot.send_message(settings.admin_id, admin_text)
        except Exception as e:
            logger.warning("Не вдалося зберегти/відправити скаргу по заявці %s: %s", order_id, e)
            await state.finish()
            await message.answer(
                "Не вдалося надіслати скаргу. Спробуйте пізніше.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await state.finish()
        await message.answer(
            "✅ <b>Скаргу надіслано</b>\n\n"
            "Адміністратор розгляне її найближчим часом.",
            reply_markup=await _after_dialog_markup(return_role, order_id),
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("rate_"), state="*")
    async def rate_choose_handler(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="client_rate_order",
            limit=8,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        try:
            _, order_id_str, rating_str = call.data.split("_")
            order_id = int(order_id_str)
            rating_value = int(rating_str)
        except Exception:
            await call.answer("Некоректна оцінка", show_alert=True)
            return

        order = await fetchrow(
            """
            SELECT *
            FROM orders
            WHERE id=$1
              AND user_id=$2
              AND status='done'
            """,
            order_id,
            call.from_user.id,
        )
        if not order:
            await call.answer("Цю заявку не можна оцінити.", show_alert=True)
            return

        if order["rating"] is not None:
            await call.answer("Ви вже оцінили цю заявку.", show_alert=True)
            return

        await state.finish()
        await state.update_data(rate_order_id=order_id, rate_value=rating_value)
        await RatingFlow.review.set()

        await call.message.answer(
            f"⭐ <b>Оцінка: {rating_value}/5</b>\n\n"
            "Напишіть короткий відгук або напишіть <b>пропустити</b>.",
            reply_markup=back_menu_kb(),
        )
        await call.answer()

    @dp.message_handler(state=RatingFlow.review, content_types=types.ContentTypes.TEXT)
    async def rate_review_handler(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="client_rate_review",
            limit=6,
            window_seconds=300,
            mute_seconds=600,
        )
        if not allowed:
            return

        data = await state.get_data()
        order_id = data.get("rate_order_id")
        rating_value = data.get("rate_value")

        if not order_id or not rating_value:
            await state.finish()
            await message.answer(
                "Не вдалося зберегти оцінку.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        review_text = (message.text or "").strip()
        if review_text.lower() in SKIP_WORDS:
            review_text = None
        else:
            review_text = normalize_text(review_text, 1000)

        result = await rate_order(
            order_id=order_id,
            client_user_id=message.from_user.id,
            rating=rating_value,
            review_text=review_text,
        )

        if not result:
            await state.finish()
            await message.answer(
                "Не вдалося зберегти оцінку. Можливо, заявку вже оцінено.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        try:
            if result["selected_master_id"]:
                await dp.bot.send_message(
                    result["selected_master_id"],
                    (
                        f"⭐ <b>Клієнт оцінив вашу роботу</b>\n\n"
                        f"Заявка #{order_id}\n"
                        f"Оцінка: <b>{rating_value}/5</b>\n"
                        f"{f'Відгук: {review_text}' if review_text else 'Без текстового відгуку'}"
                    ),
                )
        except Exception as e:
            logger.warning("Не вдалося повідомити майстра про нову оцінку по заявці %s: %s", order_id, e)

        await state.finish()
        await message.answer(
            rating_thanks(),
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("client_chat_"), state="*")
    async def client_dialog_start(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="client_open_chat",
            limit=15,
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
              AND user_id=$2
              AND selected_master_id IS NOT NULL
              AND status = ANY($3::text[])
            """,
            order_id,
            call.from_user.id,
            ["matched", "in_progress"],
        )
        if not order:
            await call.answer("Діалог недоступний", show_alert=True)
            return

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active" or chat["client_user_id"] != call.from_user.id:
            await call.answer("Діалог не знайдено", show_alert=True)
            return

        await start_dialog_write(
            call,
            state,
            order_id=order_id,
            role="client",
            target_user_id=chat["master_user_id"],
            chat_id=chat["id"],
            is_client=True,
        )

    @dp.callback_query_handler(lambda c: c.data.startswith("master_chat_open_"), state="*")
    async def master_dialog_start(call: types.CallbackQuery, state: FSMContext):
        allowed = await allow_callback_action(
            call,
            action_key="master_open_chat",
            limit=15,
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
            await call.answer("Діалог недоступний", show_alert=True)
            return

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active" or chat["master_user_id"] != call.from_user.id:
            await call.answer("Діалог не знайдено", show_alert=True)
            return

        await touch_master_presence(call.from_user.id)

        await start_dialog_write(
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
        allowed = await allow_callback_action(
            call,
            action_key="open_chat_history",
            limit=15,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        order_id = int(call.data.split("_")[-1])

        chat = await get_chat_for_order(order_id)
        if not chat:
            await call.answer("Історію не знайдено", show_alert=True)
            return

        if call.from_user.id not in (chat["client_user_id"], chat["master_user_id"]):
            await call.answer("Доступ заборонено", show_alert=True)
            return

        msgs = await get_chat_history(order_id, 30)
        await send_chat_history(dp.bot, call.message.chat.id, order_id, msgs)
        await call.answer()

    @dp.message_handler(lambda m: m.text == "📜 Історія", state=ChatFlow.message)
    async def history_from_dialog(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="open_chat_history_message",
            limit=10,
            window_seconds=60,
            mute_seconds=300,
        )
        if not allowed:
            return

        data = await state.get_data()
        msgs = await get_chat_history(data["order_id"], 30)
        await send_chat_history(dp.bot, message.chat.id, data["order_id"], msgs)

    @dp.message_handler(lambda m: m.text in {"❌ Закрити", "❌ Закрити чат"}, state=ChatFlow.message)
    async def close_dialog_mode(message: types.Message, state: FSMContext):
        data = await state.get_data()
        role = data.get("chat_role")
        order_id = data.get("order_id")
        await state.finish()

        if role and order_id:
            await message.answer(
                "✋ <b>Режим написання закрито</b>\n\n"
                f"Ви повернулись до заявки #{order_id}.",
                reply_markup=await _after_dialog_markup(role, order_id),
            )
            return

        await message.answer(
            "✋ <b>Режим написання закрито</b>",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(lambda m: m.text in {"⬅️ Назад", "🏠 У меню"}, state=ChatFlow.message)
    async def close_dialog_mode_navigation(message: types.Message, state: FSMContext):
        data = await state.get_data()
        role = data.get("chat_role")
        order_id = data.get("order_id")
        await state.finish()

        if message.text == "🏠 У меню":
            await message.answer(
                "🏠 <b>Повернення в меню</b>",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        if role and order_id:
            await message.answer(
                "↩️ <b>Повернення із чату</b>\n\n"
                f"Ви повернулись до заявки #{order_id}.",
                reply_markup=await _after_dialog_markup(role, order_id),
            )
            return

        await message.answer(
            "↩️ <b>Повернення із чату</b>",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=ChatFlow.message)
    async def relay_dialog_message(message: types.Message, state: FSMContext):
        allowed = await allow_message_action(
            message,
            action_key="chat_send_message",
            limit=12,
            window_seconds=60,
            mute_seconds=600,
        )
        if not allowed:
            return

        data = await state.get_data()
        target_id = data["target_user_id"]
        role = data["chat_role"]
        order_id = data["order_id"]
        chat_id = data["chat_id"]

        chat = await get_chat_for_order(order_id)
        if not chat or chat["status"] != "active":
            await state.finish()
            await message.answer(
                "Цей діалог уже недоступний.",
                reply_markup=await _after_dialog_markup(role, order_id),
            )
            return

        if role == "client" and chat["client_user_id"] != message.from_user.id:
            await state.finish()
            await message.answer(
                "Цей діалог вам більше недоступний.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        if role == "master" and chat["master_user_id"] != message.from_user.id:
            await state.finish()
            await message.answer(
                "Цей діалог вам більше недоступний.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

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
                await message.answer(
                    "✅ <b>Фото надіслано</b>\n\n"
                    "Можете надіслати ще повідомлення або натиснути <b>❌ Закрити</b>.",
                    reply_markup=chat_reply_kb(),
                )
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
                await message.answer(
                    "✅ <b>Відео надіслано</b>\n\n"
                    "Можете надіслати ще повідомлення або натиснути <b>❌ Закрити</b>.",
                    reply_markup=chat_reply_kb(),
                )
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
            await message.answer(
                "✅ <b>Повідомлення надіслано</b>\n\n"
                "Можете надіслати ще повідомлення або натиснути <b>❌ Закрити</b>.",
                reply_markup=chat_reply_kb(),
            )

        except Exception as e:
            logger.warning("Помилка пересилки повідомлення по заявці %s: %s", order_id, e)
            await message.answer(
                "Не вдалося переслати повідомлення. Спробуйте ще раз.",
                reply_markup=chat_reply_kb(),
            )
