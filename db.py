import logging

import asyncpg


logger = logging.getLogger(__name__)

_pool: asyncpg.pool.Pool | None = None


async def _ensure_column(conn, table: str, sql_fragment: str):
    await conn.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {sql_fragment}")


async def _ensure_index(conn, sql: str):
    await conn.execute(sql)


async def _cleanup_duplicate_offers_before_unique_index(conn):
    """
    Old MVP data may contain several offers from the same master for the same order.
    PostgreSQL cannot create UNIQUE(order_id, master_user_id) until those duplicates are removed.

    Strategy:
    - keep the newest row by id for each (order_id, master_user_id);
    - delete older duplicates;
    - log how many rows were removed.
    """
    deleted = await conn.fetchval(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id, master_user_id
                    ORDER BY id DESC
                ) AS rn
            FROM offers
        ), deleted AS (
            DELETE FROM offers
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
            RETURNING id
        )
        SELECT COUNT(*) FROM deleted
        """
    )
    deleted = int(deleted or 0)
    if deleted:
        logger.warning(
            "Cleaned duplicate offers before creating unique index: deleted=%s",
            deleted,
        )


async def _cleanup_duplicate_chats_before_unique_index(conn):
    """
    Keep one chat per order before creating UNIQUE(chats.order_id).
    Chat messages from duplicate chats are moved to the kept chat id.
    """
    duplicate_rows = await conn.fetch(
        """
        WITH ranked AS (
            SELECT
                id,
                order_id,
                FIRST_VALUE(id) OVER (
                    PARTITION BY order_id
                    ORDER BY
                        CASE WHEN status='active' THEN 0 ELSE 1 END,
                        id DESC
                ) AS keep_id,
                ROW_NUMBER() OVER (
                    PARTITION BY order_id
                    ORDER BY
                        CASE WHEN status='active' THEN 0 ELSE 1 END,
                        id DESC
                ) AS rn
            FROM chats
        )
        SELECT id, keep_id
        FROM ranked
        WHERE rn > 1
        """
    )

    if not duplicate_rows:
        return

    moved_messages = 0
    deleted_chats = 0

    for row in duplicate_rows:
        old_chat_id = row["id"]
        keep_chat_id = row["keep_id"]

        result = await conn.execute(
            """
            UPDATE chat_messages
            SET chat_id=$1
            WHERE chat_id=$2
            """,
            keep_chat_id,
            old_chat_id,
        )
        try:
            moved_messages += int(result.split()[-1])
        except Exception:
            pass

        await conn.execute(
            "DELETE FROM chats WHERE id=$1",
            old_chat_id,
        )
        deleted_chats += 1

    logger.warning(
        "Cleaned duplicate chats before creating unique index: deleted_chats=%s moved_messages=%s",
        deleted_chats,
        moved_messages,
    )


async def _ensure_constraint(conn, name: str, sql: str):
    exists = await conn.fetchval(
        "SELECT 1 FROM pg_constraint WHERE conname=$1",
        name,
    )
    if not exists:
        await conn.execute(sql)


async def init_db(database_url: str):
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=1,
            max_size=10,
        )

    async with _pool.acquire() as conn:
        # =========================================================
        # MASTERS
        # =========================================================
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

        await _ensure_column(conn, "masters", "district TEXT")
        await _ensure_column(conn, "masters", "phone TEXT")
        await _ensure_column(conn, "masters", "description TEXT")
        await _ensure_column(conn, "masters", "experience TEXT")
        await _ensure_column(conn, "masters", "photo TEXT")
        await _ensure_column(conn, "masters", "rating DOUBLE PRECISION DEFAULT 0")
        await _ensure_column(conn, "masters", "reviews_count INTEGER DEFAULT 0")
        await _ensure_column(conn, "masters", "status TEXT DEFAULT 'pending'")
        await _ensure_column(conn, "masters", "availability TEXT DEFAULT 'offline'")
        await _ensure_column(conn, "masters", "last_seen BIGINT DEFAULT 0")
        await _ensure_column(conn, "masters", "created_at BIGINT DEFAULT 0")
        await _ensure_column(conn, "masters", "updated_at BIGINT DEFAULT 0")

        # =========================================================
        # ORDERS
        # =========================================================
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
                is_suspect BOOLEAN DEFAULT FALSE,
                suspicion_score INTEGER DEFAULT 0,
                suspicion_reasons TEXT,
                moderation_status TEXT DEFAULT 'approved',
                created_at BIGINT DEFAULT 0,
                updated_at BIGINT DEFAULT 0
            )
            """
        )

        await _ensure_column(conn, "orders", "district TEXT")
        await _ensure_column(conn, "orders", "problem TEXT")
        await _ensure_column(conn, "orders", "client_phone TEXT")
        await _ensure_column(conn, "orders", "media_type TEXT")
        await _ensure_column(conn, "orders", "media_file_id TEXT")
        await _ensure_column(conn, "orders", "status TEXT DEFAULT 'new'")
        await _ensure_column(conn, "orders", "selected_master_id BIGINT")
        await _ensure_column(conn, "orders", "rating INTEGER")
        await _ensure_column(conn, "orders", "review_text TEXT")
        await _ensure_column(conn, "orders", "master_reminder_sent_at BIGINT")
        await _ensure_column(conn, "orders", "admin_no_offer_alert_sent_at BIGINT")
        await _ensure_column(conn, "orders", "client_finish_reminder_sent_at BIGINT")
        await _ensure_column(conn, "orders", "client_offer_reminder_sent_at BIGINT")
        await _ensure_column(conn, "orders", "is_suspect BOOLEAN DEFAULT FALSE")
        await _ensure_column(conn, "orders", "suspicion_score INTEGER DEFAULT 0")
        await _ensure_column(conn, "orders", "suspicion_reasons TEXT")
        await _ensure_column(conn, "orders", "moderation_status TEXT DEFAULT 'approved'")
        await _ensure_column(conn, "orders", "created_at BIGINT DEFAULT 0")
        await _ensure_column(conn, "orders", "updated_at BIGINT DEFAULT 0")

        # =========================================================
        # OFFERS
        # =========================================================
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

        await _ensure_column(conn, "offers", "price TEXT")
        await _ensure_column(conn, "offers", "eta TEXT")
        await _ensure_column(conn, "offers", "comment TEXT")
        await _ensure_column(conn, "offers", "status TEXT DEFAULT 'active'")
        await _ensure_column(conn, "offers", "created_at BIGINT DEFAULT 0")

        # =========================================================
        # CHATS
        # =========================================================
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

        await _ensure_column(conn, "chats", "status TEXT DEFAULT 'active'")
        await _ensure_column(conn, "chats", "created_at BIGINT DEFAULT 0")

        # =========================================================
        # CHAT MESSAGES
        # =========================================================
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

        await _ensure_column(conn, "chat_messages", "message_type TEXT")
        await _ensure_column(conn, "chat_messages", "text TEXT")
        await _ensure_column(conn, "chat_messages", "file_id TEXT")
        await _ensure_column(conn, "chat_messages", "created_at BIGINT DEFAULT 0")

        # legacy compatibility with old chat schema
        await _ensure_column(conn, "chat_messages", "message_text TEXT")
        await _ensure_column(conn, "chat_messages", "media_type TEXT")
        await _ensure_column(conn, "chat_messages", "media_file_id TEXT")

        # =========================================================
        # COMPLAINTS
        # =========================================================
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

        await _ensure_column(conn, "complaints", "text TEXT")
        await _ensure_column(conn, "complaints", "created_at BIGINT DEFAULT 0")

        # =========================================================
        # ORDER EVENTS
        # =========================================================
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

        await _ensure_column(conn, "order_events", "event_type TEXT")
        await _ensure_column(conn, "order_events", "from_status TEXT")
        await _ensure_column(conn, "order_events", "to_status TEXT")
        await _ensure_column(conn, "order_events", "actor_user_id BIGINT")
        await _ensure_column(conn, "order_events", "actor_role TEXT")
        await _ensure_column(conn, "order_events", "payload TEXT")
        await _ensure_column(conn, "order_events", "created_at BIGINT DEFAULT 0")

        # =========================================================
        # USER COOLDOWNS
        # =========================================================
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

        await _ensure_column(conn, "user_cooldowns", "last_at BIGINT DEFAULT 0")

        # =========================================================
        # SPAM LOGS
        # =========================================================
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

        await _ensure_column(conn, "spam_logs", "action_key TEXT")
        await _ensure_column(conn, "spam_logs", "scope TEXT")
        await _ensure_column(conn, "spam_logs", "hit_count INTEGER")
        await _ensure_column(conn, "spam_logs", "limit_value INTEGER")
        await _ensure_column(conn, "spam_logs", "window_seconds INTEGER")
        await _ensure_column(conn, "spam_logs", "mute_seconds INTEGER")
        await _ensure_column(conn, "spam_logs", "reason_text TEXT")
        await _ensure_column(conn, "spam_logs", "created_at BIGINT DEFAULT 0")

        # =========================================================
        # SUPPORT MESSAGES
        # =========================================================
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

        await _ensure_column(conn, "support_messages", "text TEXT")
        await _ensure_column(conn, "support_messages", "created_at BIGINT DEFAULT 0")

        # =========================================================
        # =========================================================
        # SAFE CONSTRAINTS (NOT VALID = old dirty data will not break startup)
        # =========================================================
        await _ensure_constraint(conn, "chk_orders_status", """
            ALTER TABLE orders
            ADD CONSTRAINT chk_orders_status
            CHECK (status IN ('new','offered','matched','in_progress','done','cancelled','expired','dispute'))
            NOT VALID
        """)

        await _ensure_constraint(conn, "chk_orders_moderation_status", """
            ALTER TABLE orders
            ADD CONSTRAINT chk_orders_moderation_status
            CHECK (moderation_status IN ('approved','pending_review','rejected'))
            NOT VALID
        """)

        await _ensure_constraint(conn, "chk_offers_status", """
            ALTER TABLE offers
            ADD CONSTRAINT chk_offers_status
            CHECK (status IN ('active','chosen','rejected'))
            NOT VALID
        """)

        await _ensure_constraint(conn, "chk_chats_status", """
            ALTER TABLE chats
            ADD CONSTRAINT chk_chats_status
            CHECK (status IN ('active','closed'))
            NOT VALID
        """)

        await _ensure_constraint(conn, "fk_offers_order", """
            ALTER TABLE offers
            ADD CONSTRAINT fk_offers_order
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            NOT VALID
        """)

        await _ensure_constraint(conn, "fk_chats_order", """
            ALTER TABLE chats
            ADD CONSTRAINT fk_chats_order
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            NOT VALID
        """)

        await _ensure_constraint(conn, "fk_chat_messages_chat", """
            ALTER TABLE chat_messages
            ADD CONSTRAINT fk_chat_messages_chat
            FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE
            NOT VALID
        """)

        await _ensure_constraint(conn, "fk_complaints_order", """
            ALTER TABLE complaints
            ADD CONSTRAINT fk_complaints_order
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            NOT VALID
        """)

        await _ensure_constraint(conn, "fk_order_events_order", """
            ALTER TABLE order_events
            ADD CONSTRAINT fk_order_events_order
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            NOT VALID
        """)

        # Clean old duplicate MVP data before creating UNIQUE indexes.
        await _cleanup_duplicate_offers_before_unique_index(conn)
        await _cleanup_duplicate_chats_before_unique_index(conn)

        # INDEXES
        # =========================================================
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_masters_status ON masters(status)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_masters_category ON masters(category)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_masters_status_category ON masters(status, category)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_masters_user_id ON masters(user_id)")

        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_orders_selected_master_id ON orders(selected_master_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_orders_moderation_status ON orders(moderation_status)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_orders_is_suspect ON orders(is_suspect)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_orders_status_category_created ON orders(status, category, created_at DESC)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_orders_moderation_created ON orders(moderation_status, created_at DESC)")

        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_offers_order_id ON offers(order_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_offers_master_user_id ON offers(master_user_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_offers_status ON offers(status)")
        await _ensure_index(conn, "CREATE UNIQUE INDEX IF NOT EXISTS ux_offers_order_master ON offers(order_id, master_user_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_offers_order_status ON offers(order_id, status)")

        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_chats_order_id ON chats(order_id)")
        await _ensure_index(conn, "CREATE UNIQUE INDEX IF NOT EXISTS ux_chats_order ON chats(order_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_chats_order_status ON chats(order_id, status)")

        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_chat_messages_order_id ON chat_messages(order_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id ON chat_messages(chat_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_chat_messages_order_created ON chat_messages(order_id, created_at DESC)")

        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_complaints_order_id ON complaints(order_id)")

        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_order_events_order_id ON order_events(order_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_order_events_created_at ON order_events(created_at)")

        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_spam_logs_user_id ON spam_logs(user_id)")
        await _ensure_index(conn, "CREATE INDEX IF NOT EXISTS idx_spam_logs_created_at ON spam_logs(created_at)")

    logger.info("Database schema initialized successfully")


def get_pool():
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    return _pool


async def reset_db_pool(database_url: str):
    global _pool

    if _pool is not None:
        await _pool.close()

    _pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=10,
    )
    logger.info("Database pool reset successfully")
