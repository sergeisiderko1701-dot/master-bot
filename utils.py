import time
from config import settings


def now_ts() -> int:
    return int(time.time())


def is_admin(user_id: int) -> bool:
    return user_id == settings.admin_id


def normalize_text(value: str, max_len: int = 1500) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return value[:max_len]
