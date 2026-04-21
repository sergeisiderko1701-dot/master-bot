# =========================
# LIMITS
# =========================
# Залишаємо для сумісності, якщо десь у коді ще є імпорти з constants.

CLIENT_ORDER_COOLDOWN = 30
MASTER_OFFER_COOLDOWN = 15

MAX_ACTIVE_CLIENT_ORDERS = 3
MAX_ACTIVE_MASTER_ORDERS = 3

ONLINE_TIMEOUT = 300
PAGE_SIZE = 5


# =========================
# CATEGORIES
# =========================

CATEGORY_PLUMBER = "plumber"
CATEGORY_ELECTRICIAN = "electrician"
CATEGORY_REPAIR = "repair"
CATEGORY_WASHING = "washing"
CATEGORY_AC = "ac"
CATEGORY_FURNITURE = "furniture"
CATEGORY_DOORS = "doors"
CATEGORY_CLEANING = "cleaning"

CATEGORIES = [
    ("🚰 Сантехнік", CATEGORY_PLUMBER),
    ("⚡ Електрик", CATEGORY_ELECTRICIAN),
    ("🛠 Ремонт", CATEGORY_REPAIR),
    ("🧺 Пральні машини", CATEGORY_WASHING),
    ("❄️ Кондиціонери", CATEGORY_AC),
    ("🪑 Меблі", CATEGORY_FURNITURE),
    ("🚪 Двері / замки", CATEGORY_DOORS),
    ("🧹 Прибирання", CATEGORY_CLEANING),
]

CATEGORY_LABEL_TO_VALUE = {label: value for label, value in CATEGORIES}
CATEGORY_VALUE_TO_LABEL = {value: label for label, value in CATEGORIES}
VALID_CATEGORIES = set(CATEGORY_VALUE_TO_LABEL.keys())


def category_label(value: str) -> str:
    return CATEGORY_VALUE_TO_LABEL.get(value, value or "—")


# =========================
# ORDER STATUSES
# =========================

ORDER_STATUS_NEW = "new"
ORDER_STATUS_OFFERED = "offered"
ORDER_STATUS_MATCHED = "matched"
ORDER_STATUS_IN_PROGRESS = "in_progress"
ORDER_STATUS_DONE = "done"
ORDER_STATUS_CANCELLED = "cancelled"
ORDER_STATUS_EXPIRED = "expired"
ORDER_STATUS_DISPUTE = "dispute"

ORDER_STATUSES = {
    ORDER_STATUS_NEW,
    ORDER_STATUS_OFFERED,
    ORDER_STATUS_MATCHED,
    ORDER_STATUS_IN_PROGRESS,
    ORDER_STATUS_DONE,
    ORDER_STATUS_CANCELLED,
    ORDER_STATUS_EXPIRED,
    ORDER_STATUS_DISPUTE,
}

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
    return STATUS_TEXT.get(status, status or "—")


# =========================
# STATUS GROUPS
# =========================

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

MASTER_CAN_RESPOND_ORDER_STATUSES = {
    ORDER_STATUS_NEW,
    ORDER_STATUS_OFFERED,
}

MASTER_ACTIVE_ORDER_STATUSES = {
    ORDER_STATUS_MATCHED,
    ORDER_STATUS_IN_PROGRESS,
}

ADMIN_RESETTABLE_ORDER_STATUSES = {
    ORDER_STATUS_OFFERED,
    ORDER_STATUS_MATCHED,
    ORDER_STATUS_IN_PROGRESS,
}

ADMIN_FINISHABLE_ORDER_STATUSES = {
    ORDER_STATUS_MATCHED,
    ORDER_STATUS_IN_PROGRESS,
}

ADMIN_EXPIRABLE_ORDER_STATUSES = ORDER_STATUSES - CLOSED_ORDER_STATUSES


# =========================
# MASTER STATUSES
# =========================

MASTER_STATUS_PENDING = "pending"
MASTER_STATUS_APPROVED = "approved"
MASTER_STATUS_BLOCKED = "blocked"

MASTER_STATUSES = {
    MASTER_STATUS_PENDING,
    MASTER_STATUS_APPROVED,
    MASTER_STATUS_BLOCKED,
}


# =========================
# MASTER AVAILABILITY
# =========================

MASTER_AVAILABILITY_ONLINE = "online"
MASTER_AVAILABILITY_OFFLINE = "offline"

MASTER_AVAILABILITIES = {
    MASTER_AVAILABILITY_ONLINE,
    MASTER_AVAILABILITY_OFFLINE,
}


def master_availability_label(value: str) -> str:
    if value == MASTER_AVAILABILITY_ONLINE:
        return "онлайн"
    if value == MASTER_AVAILABILITY_OFFLINE:
        return "офлайн"
    return value or "—"


def master_status_label(value: str) -> str:
    if value == MASTER_STATUS_PENDING:
        return "на перевірці"
    if value == MASTER_STATUS_APPROVED:
        return "підтверджений"
    if value == MASTER_STATUS_BLOCKED:
        return "заблокований"
    return value or "—"
