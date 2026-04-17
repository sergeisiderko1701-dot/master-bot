from aiogram import types
from aiogram.dispatcher import FSMContext

from config import settings
from keyboards import back_menu_kb, main_menu_kb, support_reply_inline
from repositories import (
    add_complaint,
    add_support_message,
    approved_master_row,
    execute,
    touch_master_presence,
)
from states import ComplaintWrite, RatingFlow, SupportReply, SupportWrite
from utils import is_admin, normalize_text


BACK_BUTTONS = {"⬅️ Назад", "Назад", "🔙 Назад"}
SKIP_WORDS = {"пропустити", "skip", "-"}


def register(dp):
    async def update_master_presence_if_needed(user_id: int):
        master = await approved_master_row(user_id)
        if master:
            await touch_master_presence(user_id)

    @dp.message_handler(state=SupportWrite.text, content_types=types.ContentTypes.TEXT)
    async def support_write(message: types.Message, state: FSMContext):
        text = normalize_text(message.text, 2000) or "Без тексту"

        await add_support_message(message.from_user.id, text)

        try:
            await dp.bot.send_message(
                settings.admin_id,
                f"🆘 <b>Повідомлення в підтримку</b>\n\n"
                f"👤 <b>user_id:</b> {message.from_user.id}\n"
                f"📝 <b>Текст:</b>\n{text}",
                reply_markup=support_reply_inline(message.from_user.id),
            )
        except Exception:
            pass

        await state.finish()
        await message.answer(
            "✅ Повідомлення відправлено адміністратору.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(state=SupportReply.text, content_types=types.ContentTypes.TEXT)
    async def support_reply_send(message: types.Message, state: FSMContext):
        data = await state.get_data()
        target_user_id = data.get("support_target_user_id")
        text = normalize_text(message.text, 2000)

        if not target_user_id:
            await state.finish()
            await message.answer(
                "Не знайдено отримувача відповіді.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        if not text:
            await message.answer("Напишіть текст відповіді.", reply_markup=back_menu_kb())
            return

        try:
            await dp.bot.send_message(
                target_user_id,
                f"💬 <b>Відповідь служби підтримки</b>\n\n{text}",
            )
            await message.answer("✅ Відповідь надіслано.")
        except Exception:
            await message.answer("Не вдалося надіслати відповідь користувачу.")

        await state.finish()
        await message.answer(
            "Повертаю вас у меню.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(state=ComplaintWrite.text, content_types=types.ContentTypes.TEXT)
    async def complaint_save(message: types.Message, state: FSMContext):
        data = await state.get_data()
        text = normalize_text(message.text, 2000) or "Без тексту"

        await add_complaint(
            data["complaint_order_id"],
            message.from_user.id,
            data["against_user_id"],
            data["against_role"],
            text,
        )

        try:
            await dp.bot.send_message(
                settings.admin_id,
                f"⚠️ <b>Нова скарга</b>\n\n"
                f"🆔 <b>Заявка:</b> {data['complaint_order_id']}\n"
                f"👤 <b>Від:</b> {message.from_user.id}\n"
                f"🎯 <b>На кого:</b> {data['against_user_id']} ({data['against_role']})\n"
                f"📝 <b>Текст:</b>\n{text}",
            )
        except Exception:
            pass

        await state.finish()
        await message.answer(
            "✅ Скаргу відправлено адміністратору.",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(state=RatingFlow.value, content_types=types.ContentTypes.TEXT)
    async def rating_value(message: types.Message, state: FSMContext):
        value = (message.text or "").strip()

        if value not in {"1", "2", "3", "4", "5"}:
            await message.answer("Будь ласка, надішліть оцінку цифрою від 1 до 5.")
            return

        data = await state.get_data()
        rating_value_int = int(value)

        await execute(
            """
            UPDATE masters
            SET rating = (rating * reviews_count + $1) / (reviews_count + 1),
                reviews_count = reviews_count + 1,
                updated_at = EXTRACT(EPOCH FROM NOW())::BIGINT
            WHERE user_id=$2
            """,
            rating_value_int,
            data["rating_master_user_id"],
        )

        await execute(
            "UPDATE orders SET rating=$1 WHERE id=$2",
            rating_value_int,
            data["rating_order_id"],
        )

        await state.update_data(rating_value=rating_value_int)
        await RatingFlow.review.set()
        await message.answer(
            "📝 Напишіть короткий текстовий відгук або напишіть 'пропустити':",
            reply_markup=back_menu_kb(),
        )

    @dp.message_handler(state=RatingFlow.review, content_types=types.ContentTypes.TEXT)
    async def rating_review(message: types.Message, state: FSMContext):
        data = await state.get_data()
        raw_text = (message.text or "").strip().lower()

        text = None if raw_text in SKIP_WORDS else normalize_text(message.text, 2000)

        await execute(
            "UPDATE orders SET review_text=$1 WHERE id=$2",
            text,
            data["rating_order_id"],
        )

        await state.finish()
        await message.answer(
            "✅ Дякуємо за відгук!",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(lambda m: m.text in BACK_BUTTONS, state="*")
    async def back_handler(message: types.Message, state: FSMContext):
        await state.finish()
        await update_master_presence_if_needed(message.from_user.id)

        await message.answer(
            "🏠 Головне меню:",
            reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
        )

    @dp.message_handler(content_types=types.ContentTypes.ANY, state="*")
    async def fallback(message: types.Message, state: FSMContext):
        await update_master_presence_if_needed(message.from_user.id)

        if (message.text or "").startswith("/"):
            return

        current = await state.get_state()

        if not current:
            await message.answer(
                "Скористайтесь меню нижче.",
                reply_markup=main_menu_kb(is_admin_user=is_admin(message.from_user.id)),
            )
            return

        await message.answer(
            "Не зрозумів дію. Скористайтесь кнопками меню.",
            reply_markup=back_menu_kb(),
        )
