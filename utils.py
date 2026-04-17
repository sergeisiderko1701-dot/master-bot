import time
from config import settings


def now_ts() -> int:
    return int(time.time())


def is_admin(user_id: int) -> bool:
    return user_id == settings.admin_id


def normalize_text(value, max_len: int = 1500) -> str:
    """
    Очищає текст:
    - приводить до str
    - прибирає зайві пробіли
    - обрізає довжину
    """
    if value is None:
        return ""

    value = str(value).strip()

    if not value:
        return ""

    # прибираємо подвійні пробіли
    value = " ".join(value.split())

    return value[:max_len]


def safe_str(value, default: str = "—") -> str:
    """
    Безпечний текст для UI
    """
    if value is None:
        return default

    value = str(value).strip()
    return value if value else default


def safe_int(value, default: int = 0) -> int:
    """
    Безпечне число
    """
    try:
        return int(value)
    except Exception:
        return default
