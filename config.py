import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_id: int = int(os.getenv("ADMIN_ID", "0"))
    database_url: str = os.getenv("DATABASE_URL", "")
    fsm_storage: str = os.getenv("FSM_STORAGE", "memory")
    auto_apply_schema: bool = os.getenv("AUTO_APPLY_SCHEMA", "false").lower() == "true"

    client_order_cooldown: int = int(os.getenv("CLIENT_ORDER_COOLDOWN", "60"))
    max_active_client_orders: int = int(os.getenv("MAX_ACTIVE_CLIENT_ORDERS", "3"))
    page_size: int = int(os.getenv("PAGE_SIZE", "5"))
    online_timeout: int = int(os.getenv("ONLINE_TIMEOUT", "300"))
    max_active_master_orders: int = int(os.getenv("MAX_ACTIVE_MASTER_ORDERS", "3"))
    master_offer_cooldown: int = int(os.getenv("MASTER_OFFER_COOLDOWN", "60"))

    app_instance_name: str = os.getenv("APP_INSTANCE_NAME", "unknown-instance")


settings = Settings()
