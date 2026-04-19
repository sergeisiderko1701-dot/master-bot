import html
import time

from config import settings


def now_ts() -> int:
    return int(time.time())


def is_admin(user_id: int) -> bool:
    return user_id == settings.admin_id


def normalize_text(value, max_len: int = 1500) -> str:
    """
    Очищає та нормалізує текст:
    - приводить до str
    - прибирає зайві пробіли
    - екранує HTML
    - обрізає довжину
    """
    if value is None:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    value = " ".join(value.split())
    value = html.escape(value)

    return value[:max_len]


def safe_str(value, default: str = "—") -> str:
    """
    Безпечний текст для UI.
    """
    if value is None:
        return default

    value = str(value).strip()
    if not value:
        return default

    return html.escape(value)


def safe_int(value, default: int = 0) -> int:
    """
    Безпечне число.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
