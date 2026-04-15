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


settings = Settings()
