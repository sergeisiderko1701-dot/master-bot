import html
import re
import time

from config import settings


# Zero-width space used to break Telegram auto-link detection.
_ZWSP = "\u200b"


_LINK_PATTERNS = [
    (re.compile(r"(?i)\b(https?)://"), lambda m: f"{m.group(1)}://{_ZWSP}"),
    (re.compile(r"(?i)\bwww\."), lambda m: f"www.{_ZWSP}"),
    (re.compile(r"(?i)\b(t\.me/)"), lambda m: f"t.{_ZWSP}me/"),
    (re.compile(r"(?i)\b(telegram\.me/)"), lambda m: f"telegram.{_ZWSP}me/"),
    (re.compile(r"(?i)\b(mailto:)"), lambda m: f"mailto:{_ZWSP}"),
]


_EMAIL_RE = re.compile(
    r"\b([A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"
)
_USERNAME_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_]{3,32})")


def now_ts() -> int:
    return int(time.time())


def is_admin(user_id: int) -> bool:
    return user_id == settings.admin_id


def neutralize_links(value: str) -> str:
    """
    Breaks Telegram auto-linking for URLs, emails and @usernames.
    Keeps text readable, but prevents it from becoming clickable.
    """
    if value is None:
        return ""

    text = str(value)

    for pattern, repl in _LINK_PATTERNS:
        text = pattern.sub(repl, text)

    text = _EMAIL_RE.sub(lambda m: f"{m.group(1)}@{_ZWSP}{m.group(2)}", text)
    text = _USERNAME_RE.sub(lambda m: f"@{_ZWSP}{m.group(1)}", text)

    return text


def normalize_text(value, max_len: int = 1500) -> str:
    """
    Cleans user text for storing/using in Telegram HTML messages:
    - converts to str
    - trims and collapses spaces
    - breaks Telegram auto-links
    - escapes HTML
    - truncates length
    """
    if value is None:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    value = " ".join(value.split())
    value = neutralize_links(value)
    value = html.escape(value)

    return value[:max_len]


def safe_str(value, default: str = "—") -> str:
    """
    Safe text for Telegram HTML output.
    Escapes HTML but does not intentionally break plain links.
    Use safe_user_text() for user-generated messages where links should not be clickable.
    """
    if value is None:
        return default

    value = str(value).strip()
    if not value:
        return default

    return html.escape(value)


def safe_user_text(value, default: str = "—") -> str:
    """
    Safe user-generated text for Telegram HTML output:
    - breaks Telegram auto-links
    - escapes HTML
    """
    if value is None:
        return default

    value = str(value).strip()
    if not value:
        return default

    value = neutralize_links(value)
    return html.escape(value)


def safe_int(value, default: int = 0) -> int:
    """
    Safe integer conversion.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
