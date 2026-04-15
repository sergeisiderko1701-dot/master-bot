CLIENT_ORDER_COOLDOWN = 30
MASTER_OFFER_COOLDOWN = 15
MAX_ACTIVE_CLIENT_ORDERS = 3
MAX_ACTIVE_MASTER_ORDERS = 3
ONLINE_TIMEOUT = 300
PAGE_SIZE = 5

CATEGORIES = [
    ("🚰 Сантехнік", "Сантехнік"),
    ("⚡ Електрик", "Електрик"),
    ("🛠 Ремонт", "Ремонт"),
]

CATEGORY_LABEL_TO_VALUE = {label: value for label, value in CATEGORIES}
CATEGORY_VALUE_TO_LABEL = {value: label for label, value in CATEGORIES}

STATUS_TEXT = {
    "new": "Очікує майстрів",
    "offered": "Є пропозиції",
    "matched": "Майстра обрано",
    "in_progress": "В роботі",
    "awaiting_client_confirmation": "Очікує підтвердження",
    "done": "Завершено",
    "cancelled": "Скасовано",
    "expired": "Неактивна",
    "dispute": "Спір",
}


def category_label(value: str) -> str:
    return CATEGORY_VALUE_TO_LABEL.get(value, value)


def status_label(status: str) -> str:
    return STATUS_TEXT.get(status, status)
