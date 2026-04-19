import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "").strip()
    admin_id: int = _to_int(os.getenv("ADMIN_ID"), 0)
    database_url: str = os.getenv("DATABASE_URL", "").strip()

    fsm_storage: str = os.getenv("FSM_STORAGE", "memory").strip().lower()
    auto_apply_schema: bool = _to_bool(os.getenv("AUTO_APPLY_SCHEMA"), False)

    client_order_cooldown: int = _to_int(os.getenv("CLIENT_ORDER_COOLDOWN"), 60)
    max_active_client_orders: int = _to_int(os.getenv("MAX_ACTIVE_CLIENT_ORDERS"), 3)

    page_size: int = _to_int(os.getenv("PAGE_SIZE"), 5)
    online_timeout: int = _to_int(os.getenv("ONLINE_TIMEOUT"), 300)

    max_active_master_orders: int = _to_int(os.getenv("MAX_ACTIVE_MASTER_ORDERS"), 3)
    master_offer_cooldown: int = _to_int(os.getenv("MASTER_OFFER_COOLDOWN"), 60)

    app_instance_name: str = os.getenv("APP_INSTANCE_NAME", "unknown-instance").strip()

    def validate(self):
        if not self.bot_token:
            raise ValueError("BOT_TOKEN is required")
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        if self.admin_id < 0:
            raise ValueError("ADMIN_ID must be >= 0")
        if self.page_size <= 0:
            raise ValueError("PAGE_SIZE must be > 0")
        if self.client_order_cooldown < 0:
            raise ValueError("CLIENT_ORDER_COOLDOWN must be >= 0")
        if self.master_offer_cooldown < 0:
            raise ValueError("MASTER_OFFER_COOLDOWN must be >= 0")
        if self.max_active_client_orders <= 0:
            raise ValueError("MAX_ACTIVE_CLIENT_ORDERS must be > 0")
        if self.max_active_master_orders <= 0:
            raise ValueError("MAX_ACTIVE_MASTER_ORDERS must be > 0")
        if self.online_timeout < 0:
            raise ValueError("ONLINE_TIMEOUT must be >= 0")


settings = Settings()
