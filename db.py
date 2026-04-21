import asyncpg


_pool = None


async def init_db(database_url: str):
    global _pool

    if _pool is None:
        _pool = await asyncpg.create_pool(database_url)

    async with _pool.acquire() as conn:
        # =========================
        # MASTERS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS masters (
            id SERIAL PRIMARY KEY,
            user_id BIGINT UNIQUE,
            name TEXT,
            category TEXT,
            district TEXT,
            phone TEXT,
            description TEXT,
            experience TEXT,
            photo TEXT,
            rating DOUBLE PRECISION DEFAULT 0,
            reviews_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            availability TEXT DEFAULT 'offline',
            last_seen BIGINT DEFAULT 0
        );
        """)

        # =========================
        # ORDERS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            category TEXT,
            district TEXT,
            problem TEXT,
            client_phone TEXT,
            media_type TEXT,
            media_file_id TEXT,
            status TEXT DEFAULT 'new',
            selected_master_id BIGINT,
            rating INTEGER,
            review_text TEXT,
            status_reason_code TEXT,
            status_reason_text TEXT,
            created_at BIGINT,
            updated_at BIGINT,
            admin_no_offer_alert_sent_at BIGINT,
            master_reminder_sent_at BIGINT
        );
        """)

        await conn.execute("""
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS client_phone TEXT;
        """)

        await conn.execute("""
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS status_reason_code TEXT;
        """)

        await conn.execute("""
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS status_reason_text TEXT;
        """)

        await conn.execute("""
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS created_at BIGINT;
        """)

        await conn.execute("""
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS updated_at BIGINT;
        """)

        await conn.execute("""
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS admin_no_offer_alert_sent_at BIGINT;
        """)

        await conn.execute("""
        ALTER TABLE orders
        ADD COLUMN IF NOT EXISTS master_reminder_sent_at BIGINT;
        """)

        # =========================
        # OFFERS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id SERIAL PRIMARY KEY,
            order_id INTEGER,
            master_user_id BIGINT,
            price TEXT,
            eta TEXT,
            comment TEXT,
            status TEXT DEFAULT 'active',
            created_at BIGINT
        );
        """)

        # =========================
        # CHATS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id SERIAL PRIMARY KEY,
            order_id INTEGER,
            client_user_id BIGINT,
            master_user_id BIGINT,
            status TEXT DEFAULT 'active',
            created_at BIGINT
        );
        """)

        # =========================
        # CHAT_MESSAGES
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER,
            order_id INTEGER,
            sender_user_id BIGINT,
            sender_role TEXT,
            message_type TEXT,
            text TEXT,
            file_id TEXT,
            created_at BIGINT
        );
        """)

        await conn.execute("""
        ALTER TABLE chat_messages
        ADD COLUMN IF NOT EXISTS message_type TEXT;
        """)

        await conn.execute("""
        ALTER TABLE chat_messages
        ADD COLUMN IF NOT EXISTS text TEXT;
        """)

        await conn.execute("""
        ALTER TABLE chat_messages
        ADD COLUMN IF NOT EXISTS file_id TEXT;
        """)

        await conn.execute("""
        ALTER TABLE chat_messages
        ADD COLUMN IF NOT EXISTS message_text TEXT;
        """)

        await conn.execute("""
        ALTER TABLE chat_messages
        ADD COLUMN IF NOT EXISTS media_type TEXT;
        """)

        await conn.execute("""
        ALTER TABLE chat_messages
        ADD COLUMN IF NOT EXISTS media_file_id TEXT;
        """)

        # =========================
        # COMPLAINTS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id SERIAL PRIMARY KEY,
            order_id INTEGER,
            from_user_id BIGINT,
            against_user_id BIGINT,
            against_role TEXT,
            text TEXT,
            created_at BIGINT
        );
        """)

        # =========================
        # SUPPORT_MESSAGES
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id SERIAL PRIMARY KEY,
            from_user_id BIGINT,
            text TEXT,
            created_at BIGINT
        );
        """)

        # =========================
        # ORDER_EVENTS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS order_events (
            id SERIAL PRIMARY KEY,
            order_id INTEGER,
            event_type TEXT,
            from_status TEXT,
            to_status TEXT,
            reason_code TEXT,
            reason_text TEXT,
            actor_user_id BIGINT,
            actor_role TEXT,
            created_at BIGINT
        );
        """)

        # =========================
        # AUDIT_LOGS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            entity_type TEXT,
            entity_id BIGINT,
            action TEXT,
            old_data TEXT,
            new_data TEXT,
            actor_user_id BIGINT,
            actor_role TEXT,
            created_at BIGINT
        );
        """)

        # =========================
        # USER_COOLDOWNS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_cooldowns (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            action_key TEXT NOT NULL,
            last_at BIGINT NOT NULL,
            UNIQUE (user_id, action_key)
        );
        """)

        # =========================
        # SPAM_LOGS
        # =========================
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS spam_logs (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            action_key TEXT,
            scope TEXT NOT NULL,
            hit_count INTEGER,
            limit_value INTEGER,
            window_seconds INTEGER,
            mute_seconds INTEGER,
            reason_text TEXT,
            created_at BIGINT NOT NULL
        );
        """)

        # =========================
        # INDEXES: MASTERS
        # =========================
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_masters_user_id
        ON masters(user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_masters_status
        ON masters(status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_masters_category
        ON masters(category);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_masters_status_category
        ON masters(status, category);
        """)

        # =========================
        # INDEXES: ORDERS
        # =========================
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_user_id
        ON orders(user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_status
        ON orders(status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_category
        ON orders(category);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_selected_master_id
        ON orders(selected_master_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_category_status
        ON orders(category, status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_user_status
        ON orders(user_id, status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_created_at
        ON orders(created_at DESC);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_updated_at
        ON orders(updated_at DESC);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_admin_no_offer_alert_sent_at
        ON orders(admin_no_offer_alert_sent_at);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_master_reminder_sent_at
        ON orders(master_reminder_sent_at);
        """)

        # =========================
        # INDEXES: OFFERS
        # =========================
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_offers_order_id
        ON offers(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_offers_master_user_id
        ON offers(master_user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_offers_status
        ON offers(status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_offers_order_status
        ON offers(order_id, status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_offers_order_master_status
        ON offers(order_id, master_user_id, status);
        """)

        # =========================
        # INDEXES: CHATS
        # =========================
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chats_order_id
        ON chats(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chats_status
        ON chats(status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chats_client_user_id
        ON chats(client_user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chats_master_user_id
        ON chats(master_user_id);
        """)

        # =========================
        # INDEXES: CHAT_MESSAGES
        # =========================
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id
        ON chat_messages(chat_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_order_id
        ON chat_messages(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at
        ON chat_messages(created_at DESC);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_order_id_id_desc
        ON chat_messages(order_id, id DESC);
        """)

        # =========================
        # INDEXES: COMPLAINTS / SUPPORT
        # =========================
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_complaints_order_id
        ON complaints(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_complaints_from_user_id
        ON complaints(from_user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_complaints_against_user_id
        ON complaints(against_user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_messages_from_user_id
        ON support_messages(from_user_id);
        """)

        # =========================
        # INDEXES: ORDER_EVENTS / AUDIT / COOLDOWNS / SPAM
        # =========================
        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_order_events_order_id
        ON order_events(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
        ON audit_logs(entity_type, entity_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_cooldowns_user_action
        ON user_cooldowns(user_id, action_key);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_spam_logs_user_id
        ON spam_logs(user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_spam_logs_created_at
        ON spam_logs(created_at DESC);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_spam_logs_scope
        ON spam_logs(scope);
        """)


def get_pool():
    if _pool is None:
        raise RuntimeError("Database pool is not initialized")
    return _pool
