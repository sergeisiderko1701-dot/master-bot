from dataclasses import dataclass
import os
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_id: int = int(os.getenv("ADMIN_ID", "0"))
    database_url: str = os.getenv("DATABASE_URL", "")
    client_order_cooldown: int = int(os.getenv("CLIENT_ORDER_COOLDOWN", "30"))
    master_offer_cooldown: int = int(os.getenv("MASTER_OFFER_COOLDOWN", "15"))
    max_active_client_orders: int = int(os.getenv("MAX_ACTIVE_CLIENT_ORDERS", "3"))
    max_active_master_orders: int = int(os.getenv("MAX_ACTIVE_MASTER_ORDERS", "3"))
    online_timeout: int = int(os.getenv("ONLINE_TIMEOUT", "300"))
    page_size: int = int(os.getenv("PAGE_SIZE", "5"))


settings = Settings()

if not settings.bot_token:
    raise RuntimeError("BOT_TOKEN is not set")
if not settings.database_url:
    raise RuntimeError("DATABASE_URL is not set")
if settings.admin_id <= 0:
    raise RuntimeError("ADMIN_ID is not set correctly")
