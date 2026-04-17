import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def get_env(key: str, default=None, required: bool = False):
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"❌ Environment variable '{key}' is required")
    return value


@dataclass
class Settings:
    # ---------- CORE ----------
    bot_token: str = get_env("BOT_TOKEN", required=True)
    admin_id: int = int(get_env("ADMIN_ID", "0"))
    database_url: str = get_env("DATABASE_URL", required=True)

    # ---------- MODES ----------
    debug: bool = get_env("DEBUG", "false").lower() == "true"
    fsm_storage: str = get_env("FSM_STORAGE", "memory")
    auto_apply_schema: bool = get_env("AUTO_APPLY_SCHEMA", "false").lower() == "true"

    # ---------- LIMITS ----------
    client_order_cooldown: int = int(get_env("CLIENT_ORDER_COOLDOWN", "60"))
    master_offer_cooldown: int = int(get_env("MASTER_OFFER_COOLDOWN", "60"))

    max_active_client_orders: int = int(get_env("MAX_ACTIVE_CLIENT_ORDERS", "3"))
    max_active_master_orders: int = int(get_env("MAX_ACTIVE_MASTER_ORDERS", "3"))

    page_size: int = int(get_env("PAGE_SIZE", "5"))
    online_timeout: int = int(get_env("ONLINE_TIMEOUT", "300"))

    def validate(self):
        if not self.bot_token:
            raise ValueError("❌ BOT_TOKEN is empty")

        if self.admin_id <= 0:
            print("⚠️ WARNING: ADMIN_ID is not set or invalid")

        if not self.database_url:
            raise ValueError("❌ DATABASE_URL is empty")


settings = Settings()
settings.validate()
