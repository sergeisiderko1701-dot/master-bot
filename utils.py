import html
import time

from config import settings


def now_ts() -> int:
    return int(time.time())


def is_admin(user_id: int) -> bool:
    return user_id == settings.admin_id


def normalize_text(value, max_len: int = 1500) -> str:
    """
    Очищає та нормалізує текст для збереження/подальшого показу в Telegram HTML.

    Важливо:
    - html.unescape() перед html.escape() прибирає проблему подвійного escape,
      якщо текст уже був збережений як &lt;...&gt;.
    - HTML-теги користувача завжди стають безпечним текстом.
    """
    if value is None:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    value = " ".join(value.split())
    value = html.escape(html.unescape(value), quote=True)

    return value[:max_len]


def safe_str(value, default: str = "—") -> str:
    """
    Безпечний текст для вставки в повідомлення Telegram з parse_mode='HTML'.

    Використовуй для будь-якого тексту з БД, Telegram user object або введення користувача.
    Не використовуй для власних HTML-шаблонів типу '<b>...</b>'.
    """
    if value is None:
        return default

    value = str(value).strip()
    if not value:
        return default

    return html.escape(html.unescape(value), quote=True)


def safe_int(value, default: int = 0) -> int:
    """
    Безпечне число.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
