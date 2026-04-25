# =========================
# LIMITS
# =========================
# Залишаємо для сумісності, якщо десь у коді ще є імпорти з constants.
# Основним джерелом runtime-значень надалі бажано зробити config.py.

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
CATEGORY_AIR_CONDITIONERS = "air_conditioners"
CATEGORY_WASHING_MACHINES = "washing_machines"
CATEGORY_FURNITURE = "furniture"
CATEGORY_DOORS_LOCKS = "doors_locks"
CATEGORY_REPAIR = "repair"
CATEGORY_CLEANING = "cleaning"

# Порядок важливий: саме так категорії будуть показуватися в UI
CATEGORIES = [
    ("🚰 Сантехнік", CATEGORY_PLUMBER),
    ("⚡ Електрик", CATEGORY_ELECTRICIAN),
    ("❄️ Кондиціонери", CATEGORY_AIR_CONDITIONERS),
    ("🧺 Пральні машини", CATEGORY_WASHING_MACHINES),
    ("🪑 Меблі", CATEGORY_FURNITURE),
    ("🚪 Двері/замки", CATEGORY_DOORS_LOCKS),
    ("🛠 Ремонт", CATEGORY_REPAIR),
    ("🧹 Прибирання", CATEGORY_CLEANING),
]

CATEGORY_LABEL_TO_VALUE = {label: value for label, value in CATEGORIES}
CATEGORY_VALUE_TO_LABEL = {value: label for label, value in CATEGORIES}
VALID_CATEGORIES = set(CATEGORY_VALUE_TO_LABEL.keys())


def category_label(value: str) -> str:
    return CATEGORY_VALUE_TO_LABEL.get(value, value or "—")


def parse_categories(value) -> list[str]:
    if not value:
        return []

    if isinstance(value, (list, tuple, set)):
        result = []
        for item in value:
            item = str(item).strip()
            if item:
                result.append(item)
        return result

    return [item.strip() for item in str(value).split(",") if item.strip()]


def normalize_categories_value(value) -> str:
    categories = parse_categories(value)
    unique = []
    seen = set()

    for item in categories:
        if item in VALID_CATEGORIES and item not in seen:
            unique.append(item)
            seen.add(item)

    return ",".join(unique)


def category_labels(value) -> str:
    categories = parse_categories(value)
    if not categories:
        return "—"
    return ", ".join(category_label(item) for item in categories)


# =========================
# ODESSA DISTRICTS
# =========================

DISTRICT_ALL_ODESSA = "Вся Одеса"

ODESSA_DISTRICTS = [
    "Центр",
    "Аркадія",
    "Фонтан",
    "Таїрова",
    "Черемушки",
    "Молдаванка",
    "Слобідка",
    "Селище Котовського",
    "Пересип",
    "Лузанівка",
    "Чорноморка",
    DISTRICT_ALL_ODESSA,
]

VALID_ODESSA_DISTRICTS = set(ODESSA_DISTRICTS)


def parse_districts(value) -> list[str]:
    if not value:
        return []

    if isinstance(value, (list, tuple, set)):
        result = []
        for item in value:
            item = str(item).strip()
            if item:
                result.append(item)
        return result

    return [item.strip() for item in str(value).split(",") if item.strip()]


def normalize_districts_value(value) -> str:
    districts = parse_districts(value)
    unique = []
    seen = set()

    # Якщо майстер обрав "Вся Одеса", зберігаємо тільки її.
    # Це спрощує майбутню фільтрацію:
    # if DISTRICT_ALL_ODESSA in master_districts -> показувати всі заявки.
    if DISTRICT_ALL_ODESSA in districts:
        return DISTRICT_ALL_ODESSA

    for item in districts:
        if item in VALID_ODESSA_DISTRICTS and item not in seen:
            unique.append(item)
            seen.add(item)

    return ",".join(unique)


def district_labels(value) -> str:
    districts = parse_districts(value)
    if not districts:
        return "—"
    return ", ".join(districts)


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
