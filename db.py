import logging

import asyncpg


logger = logging.getLogger(__name__)

_pool: asyncpg.pool.Pool | None = None


async def init_db(database_url: str):
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10)

    async with _pool.acquire() as conn:
        # =========================
        # MASTERS
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS masters (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                district TEXT,
                phone TEXT,
                description TEXT,
                experience TEXT,
                photo TEXT,
                rating DOUBLE PRECISION DEFAULT 0,
                reviews_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'pending',
                availability TEXT DEFAULT 'offline',
                last_seen BIGINT DEFAULT 0,
                created_at BIGINT DEFAULT 0,
                updated_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS district TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS phone TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS description TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS experience TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS photo TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS rating DOUBLE PRECISION DEFAULT 0
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS reviews_count INTEGER DEFAULT 0
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS availability TEXT DEFAULT 'offline'
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS last_seen BIGINT DEFAULT 0
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )
        await conn.execute(
            """
            ALTER TABLE masters
            ADD COLUMN IF NOT EXISTS updated_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # ORDERS
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                category TEXT NOT NULL,
                district TEXT,
                problem TEXT,
                client_phone TEXT,
                media_type TEXT,
                media_file_id TEXT,
                status TEXT DEFAULT 'new',
                selected_master_id BIGINT,
                rating INTEGER,
                review_text TEXT,
                master_reminder_sent_at BIGINT,
                admin_no_offer_alert_sent_at BIGINT,
                client_finish_reminder_sent_at BIGINT,
                client_offer_reminder_sent_at BIGINT,
                created_at BIGINT DEFAULT 0,
                updated_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS district TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS problem TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS client_phone TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS media_type TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS media_file_id TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'new'
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS selected_master_id BIGINT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS rating INTEGER
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS review_text TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS master_reminder_sent_at BIGINT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS admin_no_offer_alert_sent_at BIGINT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS client_finish_reminder_sent_at BIGINT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS client_offer_reminder_sent_at BIGINT
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )
        await conn.execute(
            """
            ALTER TABLE orders
            ADD COLUMN IF NOT EXISTS updated_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # OFFERS
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS offers (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL,
                master_user_id BIGINT NOT NULL,
                price TEXT,
                eta TEXT,
                comment TEXT,
                status TEXT DEFAULT 'active',
                created_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE offers
            ADD COLUMN IF NOT EXISTS price TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE offers
            ADD COLUMN IF NOT EXISTS eta TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE offers
            ADD COLUMN IF NOT EXISTS comment TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE offers
            ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'
            """
        )
        await conn.execute(
            """
            ALTER TABLE offers
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # CHATS
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL,
                client_user_id BIGINT NOT NULL,
                master_user_id BIGINT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE chats
            ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active'
            """
        )
        await conn.execute(
            """
            ALTER TABLE chats
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # CHAT MESSAGES
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                order_id INTEGER NOT NULL,
                sender_user_id BIGINT NOT NULL,
                sender_role TEXT NOT NULL,
                message_type TEXT,
                text TEXT,
                file_id TEXT,
                created_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE chat_messages
            ADD COLUMN IF NOT EXISTS message_type TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE chat_messages
            ADD COLUMN IF NOT EXISTS text TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE chat_messages
            ADD COLUMN IF NOT EXISTS file_id TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE chat_messages
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )

        # старі поля, якщо ще десь залишились
        await conn.execute(
            """
            ALTER TABLE chat_messages
            ADD COLUMN IF NOT EXISTS message_text TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE chat_messages
            ADD COLUMN IF NOT EXISTS media_type TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE chat_messages
            ADD COLUMN IF NOT EXISTS media_file_id TEXT
            """
        )

        # =========================
        # COMPLAINTS
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS complaints (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL,
                from_user_id BIGINT NOT NULL,
                against_user_id BIGINT NOT NULL,
                against_role TEXT NOT NULL,
                text TEXT,
                created_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE complaints
            ADD COLUMN IF NOT EXISTS text TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE complaints
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # ORDER EVENTS
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS order_events (
                id SERIAL PRIMARY KEY,
                order_id INTEGER NOT NULL,
                event_type TEXT,
                from_status TEXT,
                to_status TEXT,
                actor_user_id BIGINT,
                actor_role TEXT,
                payload TEXT,
                created_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE order_events
            ADD COLUMN IF NOT EXISTS event_type TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE order_events
            ADD COLUMN IF NOT EXISTS from_status TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE order_events
            ADD COLUMN IF NOT EXISTS to_status TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE order_events
            ADD COLUMN IF NOT EXISTS actor_user_id BIGINT
            """
        )
        await conn.execute(
            """
            ALTER TABLE order_events
            ADD COLUMN IF NOT EXISTS actor_role TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE order_events
            ADD COLUMN IF NOT EXISTS payload TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE order_events
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # USER COOLDOWNS
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_cooldowns (
                user_id BIGINT NOT NULL,
                action_key TEXT NOT NULL,
                last_at BIGINT DEFAULT 0,
                PRIMARY KEY (user_id, action_key)
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE user_cooldowns
            ADD COLUMN IF NOT EXISTS last_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # SPAM LOGS
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS spam_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                action_key TEXT,
                scope TEXT,
                hit_count INTEGER,
                limit_value INTEGER,
                window_seconds INTEGER,
                mute_seconds INTEGER,
                reason_text TEXT,
                created_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE spam_logs
            ADD COLUMN IF NOT EXISTS action_key TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE spam_logs
            ADD COLUMN IF NOT EXISTS scope TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE spam_logs
            ADD COLUMN IF NOT EXISTS hit_count INTEGER
            """
        )
        await conn.execute(
            """
            ALTER TABLE spam_logs
            ADD COLUMN IF NOT EXISTS limit_value INTEGER
            """
        )
        await conn.execute(
            """
            ALTER TABLE spam_logs
            ADD COLUMN IF NOT EXISTS window_seconds INTEGER
            """
        )
        await conn.execute(
            """
            ALTER TABLE spam_logs
            ADD COLUMN IF NOT EXISTS mute_seconds INTEGER
            """
        )
        await conn.execute(
            """
            ALTER TABLE spam_logs
            ADD COLUMN IF NOT EXISTS reason_text TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE spam_logs
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # SUPPORT MESSAGES
        # =========================
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS support_messages (
                id SERIAL PRIMARY KEY,
                from_user_id BIGINT NOT NULL,
                text TEXT,
                created_at BIGINT DEFAULT 0
            )
            """
        )

        await conn.execute(
            """
            ALTER TABLE support_messages
            ADD COLUMN IF NOT EXISTS text TEXT
            """
        )
        await conn.execute(
            """
            ALTER TABLE support_messages
            ADD COLUMN IF NOT EXISTS created_at BIGINT DEFAULT 0
            """
        )

        # =========================
        # INDEXES
        # =========================
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_masters_status ON masters(status)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_masters_category ON masters(category)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_masters_status_category ON masters(status, category)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_masters_user_id ON masters(user_id)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_selected_master_id ON orders(selected_master_id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_offers_order_id ON offers(order_id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_offers_master_user_id ON offers(master_user_id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_offers_status ON offers(status)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chats_order_id ON chats(order_id)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_order_id ON chat_messages(order_id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_complaints_order_id ON complaints(order_id)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_order_events_order_id ON order_events(order_id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_order_events_created_at ON order_events(created_at)
            """
        )

        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_spam_logs_user_id ON spam_logs(user_id)
            """
        )
        await conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_spam_logs_created_at ON spam_logs(created_at)
            """
        )

    logger.info("Database schema initialized successfully")


def get_pool():
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    return _pool


async def reset_db_pool(database_url: str):
    global _pool

    if _pool is not None:
        await _pool.close()

    _pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10)
    logger.info("Database pool reset successfully")
