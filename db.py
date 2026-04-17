import asyncpg


_pool = None


async def init_db(database_url: str):
    global _pool

    if _pool is not None:
        return

    _pool = await asyncpg.create_pool(
        dsn=database_url,
        min_size=1,
        max_size=10,
    )

    async with _pool.acquire() as conn:
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
            last_seen BIGINT DEFAULT 0,
            created_at BIGINT,
            updated_at BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            category TEXT,
            district TEXT,
            problem TEXT,
            media_type TEXT,
            media_file_id TEXT,
            status TEXT DEFAULT 'new',
            selected_master_id BIGINT,
            rating INTEGER,
            review_text TEXT,
            status_reason_code TEXT,
            status_reason_text TEXT,
            created_at BIGINT,
            updated_at BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS offers (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            master_user_id BIGINT,
            price TEXT,
            eta TEXT,
            comment TEXT,
            status TEXT DEFAULT 'active',
            created_at BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id SERIAL PRIMARY KEY,
            order_id INTEGER UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
            client_user_id BIGINT,
            master_user_id BIGINT,
            status TEXT DEFAULT 'active',
            created_at BIGINT,
            updated_at BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER REFERENCES chats(id) ON DELETE CASCADE,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            sender_user_id BIGINT,
            sender_role TEXT,
            message_type TEXT,
            text TEXT,
            file_id TEXT,
            created_at BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
            from_user_id BIGINT,
            against_user_id BIGINT,
            against_role TEXT,
            text TEXT,
            created_at BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id SERIAL PRIMARY KEY,
            from_user_id BIGINT,
            text TEXT,
            created_at BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS order_events (
            id SERIAL PRIMARY KEY,
            order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
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

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS user_cooldowns (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            action_key TEXT NOT NULL,
            last_at BIGINT NOT NULL,
            UNIQUE (user_id, action_key)
        );
        """)

        # -------------------------
        # INDEXES
        # -------------------------

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
        CREATE INDEX IF NOT EXISTS idx_masters_category_status
        ON masters(category, status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_user_id
        ON orders(user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_status
        ON orders(status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_category_status
        ON orders(category, status);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_orders_selected_master_id
        ON orders(selected_master_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_offers_order_id
        ON offers(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_offers_master_user_id
        ON offers(master_user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_offers_order_status
        ON offers(order_id, status);
        """)

        await conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS ux_offers_one_active_per_master_order
        ON offers(order_id, master_user_id)
        WHERE status = 'active';
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chats_order_id
        ON chats(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_order_id
        ON chat_messages(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_chat_id
        ON chat_messages(chat_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_complaints_order_id
        ON complaints(order_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_support_messages_from_user_id
        ON support_messages(from_user_id);
        """)

        await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_user_cooldowns_user_action
        ON user_cooldowns(user_id, action_key);
        """)

        # -------------------------
        # SAFE MIGRATIONS
        # якщо таблиці вже були створені старою схемою
        # -------------------------

        await conn.execute("""
        ALTER TABLE masters
        ADD COLUMN IF NOT EXISTS created_at BIGINT;
        """)

        await conn.execute("""
        ALTER TABLE masters
        ADD COLUMN IF NOT EXISTS updated_at BIGINT;
        """)

        await conn.execute("""
        ALTER TABLE chats
        ADD COLUMN IF NOT EXISTS updated_at BIGINT;
        """)

        await conn.execute("""
        ALTER TABLE chats
        ADD COLUMN IF NOT EXISTS created_at BIGINT;
        """)

        # для старих версій chat_messages
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


def get_pool():
    if _pool is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
    return _pool
