import html
import re
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

    Залишено сумісним зі старим кодом.
    Для текстів, які показуються користувачам у Telegram і не мають бути клікабельними,
    використовуй safe_user_text().
    """
    if value is None:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    value = " ".join(value.split())
    value = html.escape(value)

    return value[:max_len]


def _neutralize_links_raw(value: str) -> str:
    """
    Фізично ламає автопосилання Telegram.
    Після цього Telegram не має що відкривати:
    https://google.com -> https[:]//google[.]com
    www.google.com -> www[.]google[.]com
    test@gmail.com -> test[@]gmail[.]com
    @username -> [@]username
    """
    text = str(value or "")

    # URLs with scheme: replace :// first, then dots in the URL token.
    def fix_url(match: re.Match) -> str:
        token = match.group(0)
        token = re.sub(r"(?i)^https://", "https[:]//", token)
        token = re.sub(r"(?i)^http://", "http[:]//", token)
        token = token.replace(".", "[.]")
        return token

    text = re.sub(r"(?i)\bhttps?://[^\s<>()\[\]{}\"']+", fix_url, text)

    # www.* tokens
    def fix_www(match: re.Match) -> str:
        token = match.group(0)
        token = token.replace("www.", "www[.]")
        token = token.replace(".", "[.]")
        return token

    text = re.sub(r"(?i)\bwww\.[^\s<>()\[\]{}\"']+", fix_www, text)

    # Emails
    def fix_email(match: re.Match) -> str:
        token = match.group(0)
        token = token.replace("@", "[@]")
        token = token.replace(".", "[.]")
        return token

    text = re.sub(
        r"(?i)\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
        fix_email,
        text,
    )

    # Telegram usernames
    text = re.sub(
        r"(?<!\w)@([A-Za-z0-9_]{3,32})\b",
        r"[@]\1",
        text,
    )

    return text


def safe_str(value, default: str = "—") -> str:
    """
    Безпечний HTML-текст для UI.
    Екранує HTML, але НЕ ламає автопосилання.
    """
    if value is None:
        return default

    value = str(value).strip()
    if not value:
        return default

    return html.escape(value)


def safe_user_text(value, default: str = "—") -> str:
    """
    Безпечний текст від користувача для Telegram HTML:
    - ламає URL/email/@username, щоб вони НЕ відкривались;
    - екранує HTML.
    """
    if value is None:
        return default

    value = str(value).strip()
    if not value:
        return default

    value = _neutralize_links_raw(value)
    return html.escape(value)


def safe_int(value, default: int = 0) -> int:
    """
    Безпечне число.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
