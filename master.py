from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from config import settings
from validators import normalize_phone, is_valid_ua_phone
from constants import (
    DISTRICT_ALL_ODESSA,
    VALID_CATEGORIES,
    VALID_ODESSA_DISTRICTS,
    category_labels,
    district_labels,
    normalize_categories_value,
    normalize_districts_value,
    parse_categories,
    parse_districts,
)
from keyboards import (
    back_menu_kb,
    edit_profile_inline_kb,
    main_menu_kb,
    master_categories_inline_kb,
    master_districts_inline_kb,
    master_menu_kb,
    master_reviews_pagination_inline,
    order_card_master_actions,
    selected_order_master_actions,
    skip_photo_kb,
    skip_verification_kb,
)
from repositories import (
    approved_master_row,
    create_or_update_master,
    fetchrow,
    list_active_orders_for_master,
    list_new_orders_for_master,
    get_master_reviews_page,
    master_any_row,
    touch_master_presence,
    update_master_profile,
)
from services import send_master_card, send_order_card
from verification import (
    build_verification_admin_text,
    save_master_verification,
    normalize_verification_text,
)
from states import MasterRegistration, ProfileEdit
from ui_texts import master_profile_text
from utils import is_admin, normalize_text, safe_user_text


PROFILE_FIELD_MAP = {
    "name": "name",
    "category": "category",
    "district": "district",
    "phone": "phone",
    "description": "description",
    "experience": "experience",
    "photo": "photo",
}

BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}
SKIP_WORDS = {
    "пропустити",
    "skip",
    "-",
    "➡️ пропустити",
    "➡️ пропустити фото",
}


def request_contact_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📲 Поділитися номером", request_contact=True))
    kb.add(KeyboardButton("⬅️ Назад"), KeyboardButton("🏠 У меню"))
    return kb


def _validate_profile_field(field: str, message: types.Message):
    if field == "photo":
        value = message.photo[-1].file_id if message.photo else None
        if not value and (message.text or "").strip().lower() not in SKIP_WORDS:
            return False, None, "Надішліть фото або натисніть <b>➡️ Пропустити фото</b>."
        return True, value, None

    raw_text = message.text or ""

    if field == "name":
        value = normalize_text(raw_text, 120)
        if not value or len(value) < 2:
            return False, None, "Введіть коректне ім'я."
        return True, value, None

    if field == "phone":
        phone = normalize_phone(raw_text)
        if not is_valid_ua_phone(phone):
            return False, None, "Введіть коректний номер у форматі +380XXXXXXXXX."
        return True, phone, None

    if field == "description":
        value = normalize_text(raw_text, 1000)
        if not value or len(value) < 10:
            return False, None, "Напишіть трохи детальніше про себе."
        return True, value, None

    if field == "experience":
        value = normalize_text(raw_text, 1000)
        if not value or len(value) < 5:
            return False, None, "Опишіть свій досвід трохи конкретніше."
        return True, value, None

    value = normalize_text(raw_text, 1000)
    if not value:
        return False, None, "Надішліть текстове значення."
    return True, value, None


def _get_selected_categories(data: dict) -> list[str]:
    return parse_categories(data.get("selected_categories"))


def _get_selected_districts(data: dict) -> list[str]:
    return parse_districts(data.get("selected_districts"))


async def _show_category_selector(message_or_call, selected_values):
    text = (
        "🔧 <b>Оберіть одну або кілька спеціальностей</b>\n\n"
        "Можна вибрати кілька варіантів.\n"
        "Після вибору натисніть <b>✅ Готово</b>."
    )
    markup = master_categories_inline_kb(selected_values)

    if isinstance(message_or_call, types.CallbackQuery):
        await message_or_call.message.answer(text, reply_markup=markup)
    else:
        await message_or_call.answer(text, reply_markup=markup)


async def _show_district_selector(message_or_call, selected_values):
    text = (
        "📍 <b>Оберіть райони, де ви працюєте</b>\n\n"
        "Можна вибрати один або кілька районів.\n"
        "Якщо працюєте по всьому місту — оберіть <b>Вся Одеса</b>.\n\n"
        "Після вибору натисніть <b>✅ Готово</b>."
    )
    markup = master_districts_inline_kb(selected_values)

    if isinstance(message_or_call, types.CallbackQuery):
        await message_or_call.message.answer(text, reply_markup=markup)
    else:
        await message_or_call.answer(text, reply_markup=markup)


MASTER_REVIEWS_PAGE_SIZE = 5


def _format_master_reviews_text(data: dict) -> str:
    master = data.get("master")
    reviews = data.get("reviews") or []
    total = int(data.get("total") or 0)
    page = int(data.get("page") or 0)
    page_size = int(data.get("page_size") or MASTER_REVIEWS_PAGE_SIZE)

    rating = float(master["rating"] or 0) if master else 0.0
    reviews_count = int(master["reviews_count"] or 0) if master else total

    if total <= 0:
        return (
            "⭐ <b>Мої відгуки</b>\n\n"
            "Поки що у вас немає відгуків.\n\n"
            "Коли клієнт завершить заявку та поставить оцінку, вона з’явиться тут."
        )

    start = page * page_size + 1
    end = min(total, start + len(reviews) - 1)

    text = (
        "⭐ <b>Мої відгуки</b>\n\n"
        f"⭐ <b>Ваш рейтинг:</b> {rating:.2f}\n"
        f"📝 <b>Всього відгуків:</b> {reviews_count}\n\n"
        f"Показано: <b>{start}–{end}</b> з <b>{total}</b>\n\n"
    )

    for item in reviews:
        item_rating = item["rating"]
        review_text = safe_user_text(item["review_text"] or "Без коментаря")
        order_id = item["order_id"]
        text += f"⭐ <b>{item_rating}</b> · заявка #{order_id}\n{review_text}\n\n"

    return text.strip()


async def _send_master_reviews_page(message_or_call, master_user_id: int, page: int = 0):
    data = await get_master_reviews_page(
        master_user_id=master_user_id,
        page=page,
        page_size=MASTER_REVIEWS_PAGE_SIZE,
    )

    total = int(data.get("total") or 0)
    page = int(data.get("page") or 0)
    page_size = int(data.get("page_size") or MASTER_REVIEWS_PAGE_SIZE)

    has_prev = page > 0
    has_next = (page + 1) * page_size < total
    markup = master_reviews_pagination_inline(page, has_prev, has_next) if total > page_size else None
    text = _format_master_reviews_text(data)

    if isinstance(message_or_call, types.CallbackQuery):
        try:
            await message_or_call.message.edit_text(text, reply_markup=markup)
        except Exception:
            await message_or_call.message.answer(text, reply_markup=markup)
    else:
        await message_or_call.answer(text, reply_markup=markup)


def register(dp):
    async def show_master_profile(message: types.Message, master_row):
        text = master_profile_text(master_row)

        if master_row["photo"]:
            try:
                await dp.bot.send_photo(
                    message.chat.id,
                    master_row["photo"],
                    caption=text,
                )
            except Exception:
                await message.answer(text)
        else:
            await message.answer(text)

        await message.answer(
            "👇 <b>Меню майстра</b>",
            reply_markup=master_menu_kb(),
        )

    @dp.message_handler(lambda m: m.text in ["🔧 Майстер", "🔧 Я майстер"], state="*")
    async def master_entry(message: types.Message, state: FSMContext):
        await state.finish()
        master = await master_any_row(message.from_user.id)

        if master and master["status"] == "approved":
            await touch_master_presence(message.from_user.id)
            await show_master_profile(message, master)
            return

        if master and master["status"] == "pending":
            await message.answer(
                "⏳ <b>Ваша анкета вже на перевірці</b>\n\n"
                "Поки адміністратор не підтвердить профіль, нові заявки не надходитимуть.",
                reply_markup=back_menu_kb(),
            )
            return

        if master and master["status"] == "blocked":
            await message.answer(
                "🚫 <b>Ваш профіль майстра заблокований</b>\n\n"
                "Зверніться в підтримку, якщо вважаєте це помилкою.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await MasterRegistration.name.set()
        await message.answer(
            "👷 <b>Реєстрація майстра</b>\n\n"
            "Після заповнення анкети адміністратор перевірить профіль.\n"
            "Після підтвердження ви почнете отримувати заявки у своїх категоріях.\n\n"
            "Введіть ваше ім'я:",
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(lambda m: m.text in BACK_BUTTONS, state="*")
    async def master_back_handler(message: types.Message, state: FSMContext):
        current_state = await state.get_state()

        if current_state in (
            MasterRegistration.name.state,
            MasterRegistration.category.state,
            MasterRegistration.district.state,
            MasterRegistration.description.state,
            MasterRegistration.experience.state,
            MasterRegistration.phone.state,
            MasterRegistration.verification.state,
            MasterRegistration.photo.state,
            ProfileEdit.value.state,
            ProfileEdit.category.state,
        ):
            await state.finish()
            await message.answer(
                "Повернулись у головне меню.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

    @dp.message_handler(state=MasterRegistration.name, content_types=types.ContentTypes.TEXT)
    async def reg_name(message: types.Message, state: FSMContext):
        name = normalize_text(message.text, 120)
        if not name or len(name) < 2:
            await message.answer(
                "Введіть коректне ім'я.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(name=name, selected_categories=[], selected_districts=[])
        await MasterRegistration.category.set()
        await _show_category_selector(message, [])

    @dp.callback_query_handler(lambda c: c.data.startswith("master_cat_toggle_"), state=[MasterRegistration.category, ProfileEdit.category])
    async def category_toggle(call: types.CallbackQuery, state: FSMContext):
        category_value = call.data.split("master_cat_toggle_", 1)[1].strip()

        if category_value not in VALID_CATEGORIES:
            await call.answer("Некоректна категорія", show_alert=True)
            return

        data = await state.get_data()
        selected = _get_selected_categories(data)

        if category_value in selected:
            selected.remove(category_value)
        else:
            selected.append(category_value)

        await state.update_data(selected_categories=selected)

        await call.message.edit_reply_markup(
            reply_markup=master_categories_inline_kb(selected)
        )
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data == "master_cat_done", state=MasterRegistration.category)
    async def reg_category_done(call: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        selected = _get_selected_categories(data)

        if not selected:
            await call.answer("Оберіть хоча б одну спеціальність", show_alert=True)
            return

        await state.update_data(category=normalize_categories_value(selected), selected_districts=[])
        await MasterRegistration.district.set()
        await call.message.answer(
            f"✅ <b>Обрані спеціальності:</b> {category_labels(selected)}",
            reply_markup=back_menu_kb(),
        )
        await _show_district_selector(call, [])
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("master_dist_toggle_"), state=[MasterRegistration.district, ProfileEdit.category])
    async def district_toggle(call: types.CallbackQuery, state: FSMContext):
        district_value = call.data.split("master_dist_toggle_", 1)[1].strip()

        if district_value not in VALID_ODESSA_DISTRICTS:
            await call.answer("Некоректний район", show_alert=True)
            return

        data = await state.get_data()
        selected = _get_selected_districts(data)

        if district_value == DISTRICT_ALL_ODESSA:
            selected = [] if DISTRICT_ALL_ODESSA in selected else [DISTRICT_ALL_ODESSA]
        else:
            if DISTRICT_ALL_ODESSA in selected:
                selected.remove(DISTRICT_ALL_ODESSA)

            if district_value in selected:
                selected.remove(district_value)
            else:
                selected.append(district_value)

        await state.update_data(selected_districts=selected)
        await call.message.edit_reply_markup(
            reply_markup=master_districts_inline_kb(selected)
        )
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data == "master_dist_done", state=MasterRegistration.district)
    async def reg_district_done(call: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        selected = _get_selected_districts(data)

        if not selected:
            await call.answer("Оберіть хоча б один район", show_alert=True)
            return

        await state.update_data(district=normalize_districts_value(selected))
        await MasterRegistration.description.set()
        await call.message.answer(
            f"✅ <b>Обрані райони:</b> {district_labels(selected)}",
            reply_markup=back_menu_kb(),
        )
        await call.message.answer(
            "🧾 <b>Коротко про себе</b>\n\n"
            "Напишіть кілька речень про ваш досвід і спеціалізацію.",
            reply_markup=back_menu_kb(),
        )
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data == "master_cat_done", state=ProfileEdit.category)
    async def edit_category_done(call: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        edit_field = data.get("edit_field")

        if edit_field != "category":
            await call.answer()
            return

        selected = _get_selected_categories(data)

        if not selected:
            await call.answer("Оберіть хоча б одну спеціальність", show_alert=True)
            return

        await update_master_profile(
            call.from_user.id,
            PROFILE_FIELD_MAP["category"],
            selected,
        )

        await state.finish()
        await call.message.answer(
            f"✅ <b>Спеціальності оновлено:</b> {category_labels(selected)}",
            reply_markup=master_menu_kb(),
        )
        await call.answer("Збережено")

    @dp.callback_query_handler(lambda c: c.data == "master_dist_done", state=ProfileEdit.category)
    async def edit_district_done(call: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        edit_field = data.get("edit_field")

        if edit_field != "district":
            await call.answer()
            return

        selected = _get_selected_districts(data)

        if not selected:
            await call.answer("Оберіть хоча б один район", show_alert=True)
            return

        normalized = normalize_districts_value(selected)

        await update_master_profile(
            call.from_user.id,
            PROFILE_FIELD_MAP["district"],
            normalized,
        )

        await state.finish()
        await call.message.answer(
            f"✅ <b>Райони роботи оновлено:</b> {district_labels(normalized)}",
            reply_markup=master_menu_kb(),
        )
        await call.answer("Збережено")

    @dp.message_handler(state=MasterRegistration.description, content_types=types.ContentTypes.TEXT)
    async def reg_description(message: types.Message, state: FSMContext):
        description = normalize_text(message.text, 1000)
        if not description or len(description) < 10:
            await message.answer(
                "Напишіть трохи детальніше про себе.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(description=description)
        await MasterRegistration.experience.set()
        await message.answer(
            "🛠 <b>Досвід роботи</b>\n\n"
            "Напишіть, з чим саме допомагаєте клієнтам.",
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(state=MasterRegistration.experience, content_types=types.ContentTypes.TEXT)
    async def reg_experience(message: types.Message, state: FSMContext):
        experience = normalize_text(message.text, 1000)
        if not experience or len(experience) < 5:
            await message.answer(
                "Опишіть свій досвід трохи конкретніше.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(experience=experience)
        await MasterRegistration.phone.set()
        await message.answer(
            "📞 <b>Контактний телефон</b>\n\n"
            "Можете:\n"
            "• натиснути кнопку <b>📲 Поділитися номером</b>\n"
            "• або написати номер вручну у форматі <b>+380XXXXXXXXX</b>\n\n"
            "Цей номер побачить тільки клієнт, який обере вас.",
            reply_markup=request_contact_kb(),
        )

    @dp.message_handler(state=MasterRegistration.phone, content_types=types.ContentTypes.CONTACT)
    async def reg_phone_contact(message: types.Message, state: FSMContext):
        if not message.contact:
            await message.answer(
                "Не вдалося отримати контакт. Спробуйте ще раз.",
                reply_markup=request_contact_kb(),
            )
            return

        if message.contact.user_id != message.from_user.id:
            await message.answer(
                "Будь ласка, надішліть саме <b>свій</b> номер кнопкою <b>📲 Поділитися номером</b>.",
                reply_markup=request_contact_kb(),
            )
            return

        phone = normalize_phone(message.contact.phone_number)

        if not is_valid_ua_phone(phone):
            await message.answer(
                "Номер із контакту виглядає некоректно. Надішліть правильний номер або введіть вручну у форматі <b>+380XXXXXXXXX</b>.",
                reply_markup=request_contact_kb(),
            )
            return

        await state.update_data(phone=phone)
        await MasterRegistration.verification.set()
        await message.answer(
            "🛡 <b>Підтвердження досвіду</b>\n\n"
            "Надішліть щось одне:\n"
            "• посилання на Kabanchik/OLX/Instagram/сайт\n"
            "• скрін профілю або відгуків\n"
            "• фото прикладів робіт\n\n"
            "Це побачить тільки адміністратор.",
            reply_markup=skip_verification_kb(),
        )

    @dp.message_handler(state=MasterRegistration.phone, content_types=types.ContentTypes.TEXT)
    async def reg_phone(message: types.Message, state: FSMContext):
        text = (message.text or "").strip()

        if text in BACK_BUTTONS:
            await state.finish()
            await message.answer(
                "Повернулись у головне меню.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        phone = normalize_phone(text)
        if not is_valid_ua_phone(phone):
            await message.answer(
                "Введіть коректний номер у форматі <b>+380XXXXXXXXX</b> або натисніть кнопку <b>📲 Поділитися номером</b>.",
                reply_markup=request_contact_kb(),
            )
            return

        await state.update_data(phone=phone)
        await MasterRegistration.verification.set()
        await message.answer(
            "🛡 <b>Підтвердження досвіду</b>\n\n"
            "Надішліть щось одне:\n"
            "• посилання на Kabanchik/OLX/Instagram/сайт\n"
            "• скрін профілю або відгуків\n"
            "• фото прикладів робіт\n\n"
            "Це побачить тільки адміністратор.",
            reply_markup=skip_verification_kb(),
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=MasterRegistration.verification)
    async def reg_verification(message: types.Message, state: FSMContext):
        text_raw = (message.text or "").strip()
        text_low = text_raw.lower()

        if text_raw in BACK_BUTTONS:
            await state.finish()
            await message.answer(
                "Повернулись у головне меню.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        verification_type = None
        verification_text = None
        verification_file_id = None

        if message.photo:
            verification_type = "photo"
            verification_file_id = message.photo[-1].file_id
        elif text_low in {"➡️ пропустити перевірку", "пропустити", "skip", "-"}:
            verification_type = "skipped"
        elif text_raw:
            verification_type = "link"
            verification_text = normalize_verification_text(text_raw)
        else:
            await message.answer(
                "Надішліть посилання, скрін/фото або натисніть <b>➡️ Пропустити перевірку</b>.",
                reply_markup=skip_verification_kb(),
            )
            return

        await state.update_data(
            verification_type=verification_type,
            verification_text=verification_text,
            verification_file_id=verification_file_id,
        )

        await MasterRegistration.photo.set()
        await message.answer(
            "📸 <b>Фото профілю</b>\n\n"
            "Надішліть фото або натисніть <b>➡️ Пропустити фото</b>.",
            reply_markup=skip_photo_kb(),
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=MasterRegistration.photo)
    async def reg_photo(message: types.Message, state: FSMContext):
        text = (message.text or "").strip().lower()
        photo = message.photo[-1].file_id if message.photo else None

        if not photo and text not in SKIP_WORDS:
            await message.answer(
                "Надішліть фото або натисніть <b>➡️ Пропустити фото</b>.",
                reply_markup=skip_photo_kb(),
            )
            return

        data = await state.get_data()
        data["user_id"] = message.from_user.id
        data["photo"] = photo
        data["category"] = normalize_categories_value(data.get("category") or data.get("selected_categories"))
        data["district"] = normalize_districts_value(data.get("district") or data.get("selected_districts"))

        await create_or_update_master(data)

        await save_master_verification(
            user_id=message.from_user.id,
            verification_type=data.get("verification_type") or "skipped",
            verification_text=data.get("verification_text"),
            verification_file_id=data.get("verification_file_id"),
            verification_status="skipped" if (data.get("verification_type") == "skipped") else "pending",
        )

        master_row = await fetchrow(
            "SELECT * FROM masters WHERE user_id=$1",
            message.from_user.id,
        )

        try:
            await send_master_card(
                dp.bot,
                settings.admin_id,
                master_row,
                title="📝 Нова заявка майстра",
            )
            await dp.bot.send_message(
                settings.admin_id,
                build_verification_admin_text(master_row),
            )
            if data.get("verification_type") == "photo" and data.get("verification_file_id"):
                await dp.bot.send_photo(
                    settings.admin_id,
                    data.get("verification_file_id"),
                    caption="📷 Скрін/фото для перевірки досвіду майстра",
                )
        except Exception:
            pass

        await state.finish()
        await message.answer(
            "⏳ <b>Анкету надіслано</b>\n\n"
            "Після перевірки адміністратор активує ваш профіль.\n"
            "Після цього ви почнете отримувати заявки у своїх категоріях.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )


    @dp.message_handler(lambda m: m.text == "⭐ Мої відгуки", state="*")
    async def master_reviews(message: types.Message, state: FSMContext):
        master = await approved_master_row(message.from_user.id)
        if not master:
            await message.answer(
                "Профіль майстра недоступний.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await touch_master_presence(message.from_user.id)
        await _send_master_reviews_page(message, message.from_user.id, page=0)

    @dp.callback_query_handler(lambda c: c.data.startswith("master_reviews_page_"), state="*")
    async def master_reviews_page(call: types.CallbackQuery, state: FSMContext):
        master = await approved_master_row(call.from_user.id)
        if not master:
            await call.answer("Профіль майстра недоступний.", show_alert=True)
            return

        try:
            page = int(call.data.split("master_reviews_page_", 1)[1])
        except Exception:
            page = 0

        await touch_master_presence(call.from_user.id)
        await _send_master_reviews_page(call, call.from_user.id, page=page)
        await call.answer()

    @dp.message_handler(lambda m: m.text in {"👤 Мій профіль", "👤 Профіль"}, state="*")
    async def profile(message: types.Message, state: FSMContext):
        master = await approved_master_row(message.from_user.id)
        if not master:
            await message.answer(
                "Профіль майстра недоступний.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await touch_master_presence(message.from_user.id)
        await show_master_profile(message, master)

    @dp.message_handler(lambda m: m.text in {"✏️ Редагувати профіль", "✏️ Редагувати"}, state="*")
    async def edit_profile(message: types.Message, state: FSMContext):
        master = await approved_master_row(message.from_user.id)
        if not master:
            await message.answer(
                "Профіль майстра недоступний.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await touch_master_presence(message.from_user.id)
        await message.answer("Оберіть, що хочете змінити:", reply_markup=back_menu_kb())
        await message.answer("Поля профілю:", reply_markup=edit_profile_inline_kb())

    @dp.callback_query_handler(lambda c: c.data.startswith("edit_"), state="*")
    async def edit_profile_field(call: types.CallbackQuery, state: FSMContext):
        master = await approved_master_row(call.from_user.id)
        if not master:
            await call.answer("Профіль недоступний", show_alert=True)
            return

        field = call.data.replace("edit_", "", 1)
        if field not in PROFILE_FIELD_MAP:
            await call.answer()
            return

        if field == "category":
            selected = parse_categories(master["category"])
            await state.update_data(edit_field=field, selected_categories=selected)
            await ProfileEdit.category.set()
            await _show_category_selector(call, selected)
            await call.answer()
            return

        if field == "district":
            selected = parse_districts(master["district"])
            await state.update_data(edit_field=field, selected_districts=selected)
            await ProfileEdit.category.set()
            await _show_district_selector(call, selected)
            await call.answer()
            return

        await state.update_data(edit_field=field)
        await ProfileEdit.value.set()

        if field == "photo":
            prompt = "Надішліть нове фото або натисніть <b>➡️ Пропустити фото</b>."
            reply_markup = skip_photo_kb()
        elif field == "phone":
            prompt = (
                "📞 <b>Новий номер телефону</b>\n\n"
                "Можете натиснути кнопку <b>📲 Поділитися номером</b> "
                "або ввести вручну у форматі <b>+380XXXXXXXXX</b>."
            )
            reply_markup = request_contact_kb()
        else:
            prompt = "Надішліть нове значення:"
            reply_markup = back_menu_kb()

        await call.message.answer(prompt, reply_markup=reply_markup)
        await call.answer()

    @dp.message_handler(state=ProfileEdit.value, content_types=types.ContentTypes.CONTACT)
    async def edit_profile_save_contact(message: types.Message, state: FSMContext):
        data = await state.get_data()
        field = data.get("edit_field")

        if field != "phone":
            await message.answer(
                "Тут очікується інший тип даних.",
                reply_markup=back_menu_kb(),
            )
            return

        if not message.contact:
            await message.answer(
                "Не вдалося отримати контакт. Спробуйте ще раз.",
                reply_markup=request_contact_kb(),
            )
            return

        if message.contact.user_id != message.from_user.id:
            await message.answer(
                "Будь ласка, надішліть саме <b>свій</b> номер кнопкою <b>📲 Поділитися номером</b>.",
                reply_markup=request_contact_kb(),
            )
            return

        phone = normalize_phone(message.contact.phone_number)

        if not is_valid_ua_phone(phone):
            await message.answer(
                "Номер із контакту виглядає некоректно. Надішліть правильний номер або введіть вручну у форматі <b>+380XXXXXXXXX</b>.",
                reply_markup=request_contact_kb(),
            )
            return

        await update_master_profile(
            message.from_user.id,
            PROFILE_FIELD_MAP[field],
            phone,
        )

        await state.finish()
        await message.answer("✅ Профіль оновлено.", reply_markup=master_menu_kb())

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=ProfileEdit.value)
    async def edit_profile_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        field = data["edit_field"]

        is_valid, value, error_text = _validate_profile_field(field, message)
        if not is_valid:
            reply_markup = request_contact_kb() if field == "phone" else back_menu_kb()
            await message.answer(
                error_text,
                reply_markup=reply_markup,
            )
            return

        await update_master_profile(
            message.from_user.id,
            PROFILE_FIELD_MAP[field],
            value,
        )

        await state.finish()
        await message.answer("✅ Профіль оновлено.", reply_markup=master_menu_kb())

    @dp.message_handler(lambda m: m.text in {"📦 Нові заявки", "🔔 Нові заявки"}, state="*")
    async def new_orders(message: types.Message, state: FSMContext):
        master = await approved_master_row(message.from_user.id)
        if not master:
            await message.answer(
                "❌ <b>Ви ще не можете отримувати заявки</b>\n\n"
                "Можливі причини:\n"
                "• профіль ще не підтверджений\n"
                "• профіль заблокований\n"
                "• ви ще не завершили реєстрацію\n\n"
                "Якщо ви вже подавали анкету — дочекайтесь перевірки адміністратора.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await touch_master_presence(message.from_user.id)

        rows = await list_new_orders_for_master(master["category"], master["district"])
        if not rows:
            await message.answer(
                f"📭 <b>Нових заявок поки немає</b>\n\n"
                f"Категорії: {category_labels(master['category'])}\n"
                f"Райони: {district_labels(master['district'])}\n\n"
                "Ми покажемо вам нові заявки, щойно вони з’являться.\n\n"
                "ℹ️ Щоб отримувати заявки:\n"
                "• профіль має бути підтверджений\n"
                "• хоча б одна категорія має збігатися із заявкою\n"
                "• бажано відкрити бот через /start",
                reply_markup=master_menu_kb(),
            )
            return

        await message.answer(
            f"📦 <b>Нові заявки</b>\n\n"
            f"Категорії: {category_labels(master['category'])}\n"
            f"Райони: {district_labels(master['district'])}",
            reply_markup=master_menu_kb(),
        )

        for row in rows[:20]:
            try:
                await send_order_card(
                    dp.bot,
                    message.chat.id,
                    row,
                    title="📢 Доступна заявка",
                    reply_markup=order_card_master_actions(row["id"]),
                )
            except Exception:
                continue

    @dp.message_handler(lambda m: m.text in {"💬 Активні заявки", "📌 Мої роботи"}, state="*")
    async def active_orders(message: types.Message, state: FSMContext):
        master = await approved_master_row(message.from_user.id)
        if not master:
            await message.answer(
                "❌ Ви не підтверджений майстер.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await touch_master_presence(message.from_user.id)

        rows = await list_active_orders_for_master(message.from_user.id)
        if not rows:
            await message.answer(
                "📭 <b>У вас немає активних заявок</b>\n\n"
                "Коли клієнт обере вашу пропозицію, вона з’явиться тут.\n"
                "Після вибору клієнтом вам відкриються його контакти.",
                reply_markup=master_menu_kb(),
            )
            return

        await message.answer(
            "✅ <b>Ваші активні заявки</b>",
            reply_markup=master_menu_kb(),
        )

        for row in rows[:20]:
            try:
                await send_order_card(
                    dp.bot,
                    message.chat.id,
                    row,
                    title="📄 Активна заявка",
                    reply_markup=selected_order_master_actions(row["id"]),
                )
            except Exception:
                continue
