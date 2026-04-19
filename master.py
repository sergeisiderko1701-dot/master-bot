from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from constants import category_label
from keyboards import (
    back_menu_kb,
    edit_profile_inline_kb,
    main_menu_kb,
    master_categories_inline_kb,
    master_menu_kb,
)
from repositories import (
    approved_master_row,
    create_or_update_master,
    fetchrow,
    list_active_orders_for_master,
    list_new_orders_for_master,
    master_any_row,
    touch_master_presence,
    update_master_profile,
)
from services import send_master_card, send_order_card
from states import MasterRegistration, ProfileEdit
from ui_texts import ask_district_text
from utils import is_admin, normalize_text


PROFILE_FIELD_MAP = {
    "name": "name",
    "district": "district",
    "phone": "phone",
    "description": "description",
    "experience": "experience",
    "photo": "photo",
}

BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}
SKIP_WORDS = {"пропустити", "skip", "-"}


def register(dp):
    async def show_master_profile(message: types.Message, master_row):
        text = (
            f"👷 <b>Ваш профіль майстра</b>\n\n"
            f"👤 Ім'я: {master_row['name']}\n"
            f"🔧 Категорія: {category_label(master_row['category'])}\n"
            f"📍 Район: {master_row['district'] or '-'}\n"
            f"📞 Телефон: {master_row['phone'] or '-'}\n"
            f"🧾 Про себе: {master_row['description'] or '-'}\n"
            f"🛠 Досвід: {master_row['experience'] or '-'}\n"
            f"⭐ Рейтинг: {float(master_row['rating']):.2f}\n"
            f"💬 Відгуків: {master_row['reviews_count']}\n"
            f"🟢 Статус: {master_row['availability']}\n\n"
            f"ℹ️ <b>Пам'ятка</b>\n"
            f"• нові заявки надходять тільки у вашу категорію\n"
            f"• контакти клієнта відкриваються після того, як клієнт обере вас\n"
            f"• якщо заявок немає — це не помилка, просто зараз немає нових звернень"
        )

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

        await message.answer("👇 <b>Меню майстра</b>", reply_markup=master_menu_kb())

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
            "Після підтвердження ви почнете отримувати заявки у своїй категорії.\n\n"
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
            MasterRegistration.photo.state,
            ProfileEdit.value.state,
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

        await state.update_data(name=name)
        await MasterRegistration.category.set()
        await message.answer(
            "🔧 <b>Оберіть спеціальність</b>\n\n"
            "Саме в цій категорії ви будете отримувати нові заявки.",
            reply_markup=back_menu_kb(),
        )
        await message.answer("Категорії:", reply_markup=master_categories_inline_kb())

    @dp.callback_query_handler(lambda c: c.data.startswith("master_cat_"), state=MasterRegistration.category)
    async def reg_category(call: types.CallbackQuery, state: FSMContext):
        category_value = call.data.split("master_cat_", 1)[1].strip()

        if category_value not in {"plumber", "electrician", "repair"}:
            await call.answer("Некоректна категорія", show_alert=True)
            return

        await state.update_data(category=category_value)
        await MasterRegistration.district.set()
        await call.message.answer(ask_district_text(), reply_markup=back_menu_kb())
        await call.answer()

    @dp.message_handler(state=MasterRegistration.district, content_types=types.ContentTypes.TEXT)
    async def reg_district(message: types.Message, state: FSMContext):
        district = normalize_text(message.text, 255)
        if not district:
            await message.answer(
                "Будь ласка, вкажіть район роботи.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(district=district)
        await MasterRegistration.description.set()
        await message.answer(
            "🧾 <b>Коротко про себе</b>\n\n"
            "Напишіть кілька речень про ваш досвід і спеціалізацію.",
            reply_markup=back_menu_kb(),
        )

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
            "Цей номер побачить тільки клієнт, який обере вас.",
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(state=MasterRegistration.phone, content_types=types.ContentTypes.TEXT)
    async def reg_phone(message: types.Message, state: FSMContext):
        phone = normalize_text(message.text, 50)
        if not phone or len(phone) < 8:
            await message.answer(
                "Введіть коректний номер телефону.",
                reply_markup=back_menu_kb(),
            )
            return

        await state.update_data(phone=phone)
        await MasterRegistration.photo.set()
        await message.answer(
            "📸 <b>Фото профілю</b>\n\n"
            "Надішліть фото або напишіть <b>пропустити</b>.",
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=MasterRegistration.photo)
    async def reg_photo(message: types.Message, state: FSMContext):
        text = (message.text or "").strip().lower()
        photo = message.photo[-1].file_id if message.photo else None

        if not photo and text not in SKIP_WORDS:
            await message.answer(
                "Надішліть фото або напишіть 'пропустити'.",
                reply_markup=back_menu_kb(),
            )
            return

        data = await state.get_data()
        data["user_id"] = message.from_user.id
        data["photo"] = photo

        await create_or_update_master(data)

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
        except Exception:
            pass

        await state.finish()
        await message.answer(
            "⏳ <b>Анкету надіслано</b>\n\n"
            "Після перевірки адміністратор активує ваш профіль.\n"
            "Після цього ви почнете отримувати заявки у своїй категорії.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(lambda m: m.text == "👤 Мій профіль", state="*")
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

    @dp.message_handler(lambda m: m.text == "✏️ Редагувати профіль", state="*")
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

        await state.update_data(edit_field=field)
        await ProfileEdit.value.set()

        prompt = (
            "Надішліть нове значення:"
            if field != "photo"
            else "Надішліть нове фото або напишіть 'пропустити':"
        )
        await call.message.answer(prompt, reply_markup=back_menu_kb())
        await call.answer()

    @dp.message_handler(content_types=types.ContentTypes.ANY, state=ProfileEdit.value)
    async def edit_profile_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        field = data["edit_field"]

        if field == "photo":
            value = message.photo[-1].file_id if message.photo else None
            if not value and (message.text or "").strip().lower() not in SKIP_WORDS:
                await message.answer(
                    "Надішліть фото або напишіть 'пропустити'.",
                    reply_markup=back_menu_kb(),
                )
                return
        else:
            value = normalize_text(message.text, 1000)
            if not value:
                await message.answer(
                    "Надішліть текстове значення.",
                    reply_markup=back_menu_kb(),
                )
                return

        await update_master_profile(
            message.from_user.id,
            PROFILE_FIELD_MAP[field],
            value,
        )

        await state.finish()
        await message.answer("✅ Профіль оновлено.", reply_markup=master_menu_kb())

    @dp.message_handler(lambda m: m.text == "📦 Нові заявки", state="*")
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

        rows = await list_new_orders_for_master(master["category"])
        if not rows:
            await message.answer(
                f"📭 <b>Нових заявок поки немає</b>\n\n"
                f"Категорія: {category_label(master['category'])}\n\n"
                "Ми покажемо вам нові заявки, щойно вони з’являться.\n\n"
                "ℹ️ Щоб отримувати заявки:\n"
                "• профіль має бути підтверджений\n"
                "• категорія має збігатися із заявкою\n"
                "• бажано відкрити бот через /start",
                reply_markup=master_menu_kb(),
            )
            return

        await message.answer(
            f"📦 <b>Нові заявки</b>\n\nКатегорія: {category_label(master['category'])}",
            reply_markup=master_menu_kb(),
        )

        from keyboards import order_card_master_actions

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

    @dp.message_handler(lambda m: m.text == "💬 Активні заявки", state="*")
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

        from keyboards import selected_order_master_actions

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
