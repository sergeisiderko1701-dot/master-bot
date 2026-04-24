import html
import re
import time

from config import settings


_ZERO_WIDTH_SPACE = "\u200b"


def neutralize_links(value: str) -> str:
    """
    Ламає автопосилання Telegram, але залишає текст читабельним.

    HTML escape захищає від <b>/<a>, але Telegram все одно може сам робити
    клікабельними https://..., www..., email і @username. Тут ми додаємо
    zero-width space у ключові місця.
    """
    if not value:
        return value

    text = str(value)

    # https://example.com -> https://​example.com
    text = re.sub(
        r"(?i)\b(https?)://",
        lambda m: f"{m.group(1)}://{_ZERO_WIDTH_SPACE}",
        text,
    )

    # www.example.com -> www.​example.com
    text = re.sub(
        r"(?i)\bwww\.",
        f"www.{_ZERO_WIDTH_SPACE}",
        text,
    )

    # user@example.com -> user@​example.com
    text = re.sub(
        r"([A-Za-z0-9._%+\-]{1,64})@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
        lambda m: f"{m.group(1)}@{_ZERO_WIDTH_SPACE}{m.group(2)}",
        text,
    )

    # @username -> @​username
    text = re.sub(
        r"(?<!\w)@([A-Za-z0-9_]{3,32})",
        lambda m: f"@{_ZERO_WIDTH_SPACE}{m.group(1)}",
        text,
    )

    return text


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

    Не ламаємо посилання тут, щоб не записувати zero-width символи в БД.
    Посилання нейтралізуємо на етапі виводу через safe_str/safe_user_text.
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

    Додатково ламає автопосилання Telegram: https://, www., email, @username.
    """
    if value is None:
        return default

    value = str(value).strip()
    if not value:
        return default

    value = html.unescape(value)
    value = neutralize_links(value)
    return html.escape(value, quote=True)


def safe_user_text(value, default: str = "—") -> str:
    """
    Явний alias для тексту від користувача: HTML escape + нейтралізація посилань.
    """
    return safe_str(value, default)


def safe_int(value, default: int = 0) -> int:
    """
    Безпечне число.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
