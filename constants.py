# ---------- LIMITS ----------

CLIENT_ORDER_COOLDOWN = 30
MASTER_OFFER_COOLDOWN = 15

MAX_ACTIVE_CLIENT_ORDERS = 3
MAX_ACTIVE_MASTER_ORDERS = 3

ONLINE_TIMEOUT = 300
PAGE_SIZE = 5


# ---------- CATEGORIES ----------

CATEGORIES = [
    ("🚰 Сантехнік", "plumber"),
    ("⚡ Електрик", "electrician"),
    ("🛠 Ремонт", "repair"),
]

CATEGORY_LABEL_TO_VALUE = {label: value for label, value in CATEGORIES}
CATEGORY_VALUE_TO_LABEL = {value: label for label, value in CATEGORIES}


def category_label(value: str) -> str:
    return CATEGORY_VALUE_TO_LABEL.get(value, value)


# ---------- STATUSES ----------

ORDER_STATUS_NEW = "new"
ORDER_STATUS_OFFERED = "offered"
ORDER_STATUS_MATCHED = "matched"
ORDER_STATUS_IN_PROGRESS = "in_progress"
ORDER_STATUS_DONE = "done"
ORDER_STATUS_CANCELLED = "cancelled"
ORDER_STATUS_EXPIRED = "expired"
ORDER_STATUS_DISPUTE = "dispute"


STATUS_TEXT = {
    ORDER_STATUS_NEW: "Очікує майстрів",
    ORDER_STATUS_OFFERED: "Є пропозиції",
    ORDER_STATUS_MATCHED: "Майстра обрано",
    ORDER_STATUS_IN_PROGRESS: "В роботі",
    ORDER_STATUS_DONE: "Завершено",
    ORDER_STATUS_CANCELLED: "Скасовано",
    ORDER_STATUS_EXPIRED: "Неактивна",
    ORDER_STATUS_DISPUTE: "Спір",
}


def status_label(status: str) -> str:
    return STATUS_TEXT.get(status, status)


# ---------- STATUS GROUPS ----------

ACTIVE_ORDER_STATUSES = {
    ORDER_STATUS_NEW,
    ORDER_STATUS_OFFERED,
    ORDER_STATUS_MATCHED,
    ORDER_STATUS_IN_PROGRESS,
}

CLOSED_ORDER_STATUSES = {
    ORDER_STATUS_DONE,
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_EXPIRED,
}

CHAT_AVAILABLE_STATUSES = {
    ORDER_STATUS_MATCHED,
    ORDER_STATUS_IN_PROGRESS,
}

CANCELLABLE_STATUSES = {
    ORDER_STATUS_NEW,
    ORDER_STATUS_OFFERED,
    ORDER_STATUS_MATCHED,
}
