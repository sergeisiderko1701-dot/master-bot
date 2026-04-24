import logging
from typing import Optional

from repositories import execute, fetchrow
from utils import now_ts, normalize_text


logger = logging.getLogger(__name__)

_VERIFICATION_COLUMNS_READY = False


async def ensure_master_verification_columns() -> None:
    """
    Adds verification columns lazily without requiring a separate migration.
    Safe to call multiple times.
    """
    global _VERIFICATION_COLUMNS_READY
    if _VERIFICATION_COLUMNS_READY:
        return

    await execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS verification_type TEXT")
    await execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS verification_text TEXT")
    await execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS verification_file_id TEXT")
    await execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'not_verified'")
    await execute("ALTER TABLE masters ADD COLUMN IF NOT EXISTS verification_updated_at BIGINT DEFAULT 0")

    _VERIFICATION_COLUMNS_READY = True


async def save_master_verification(
    *,
    user_id: int,
    verification_type: str,
    verification_text: Optional[str] = None,
    verification_file_id: Optional[str] = None,
    verification_status: str = "pending",
):
    await ensure_master_verification_columns()

    await execute(
        """
        UPDATE masters
        SET verification_type=$1,
            verification_text=$2,
            verification_file_id=$3,
            verification_status=$4,
            verification_updated_at=$5,
            updated_at=$5
        WHERE user_id=$6
        """,
        verification_type,
        verification_text,
        verification_file_id,
        verification_status,
        now_ts(),
        user_id,
    )


async def get_master_verification(user_id: int):
    await ensure_master_verification_columns()
    return await fetchrow(
        """
        SELECT
            verification_type,
            verification_text,
            verification_file_id,
            verification_status,
            verification_updated_at
        FROM masters
        WHERE user_id=$1
        """,
        user_id,
    )


def verification_status_label(value: Optional[str]) -> str:
    if value == "verified":
        return "✅ Досвід підтверджено"
    if value == "pending":
        return "🛡 Досвід на перевірці"
    if value == "rejected":
        return "⚠️ Досвід не підтверджено"
    if value == "skipped":
        return "⚠️ Досвід не підтверджено"
    return "⚠️ Досвід не підтверджено"


def build_verification_admin_text(master_row) -> str:
    def _get(key, default="—"):
        try:
            value = master_row[key]
        except Exception:
            value = None
        return value if value not in (None, "") else default

    verification_type = _get("verification_type")
    verification_text = _get("verification_text")
    verification_status = _get("verification_status", "pending")

    if verification_type == "link":
        proof_line = f"🔗 Посилання / текст: {verification_text}"
    elif verification_type == "photo":
        proof_line = "📷 Скрін / фото: прикріплено окремим повідомленням"
    elif verification_type == "skipped":
        proof_line = "➡️ Майстер пропустив підтвердження"
    else:
        proof_line = "—"

    return (
        "🛡 <b>Підтвердження досвіду майстра</b>\n\n"
        f"👤 <b>Майстер:</b> {_get('name')}\n"
        f"🆔 <b>User ID:</b> <code>{_get('user_id')}</code>\n"
        f"📌 <b>Статус:</b> {verification_status_label(verification_status)}\n"
        f"🧾 <b>Тип:</b> {verification_type}\n\n"
        f"{proof_line}\n\n"
        "Перевірте це перед підтвердженням профілю."
    )


def normalize_verification_text(value: str) -> str:
    return normalize_text(value, 1000)
