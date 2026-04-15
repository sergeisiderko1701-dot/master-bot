import asyncpg


_pool = None


async def init_db(database_url: str):
    global _pool
    _pool = await asyncpg.create_pool(database_url)

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
            last_seen BIGINT DEFAULT 0
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
            order_id INTEGER,
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
            order_id INTEGER,
            client_user_id BIGINT,
            master_user_id BIGINT,
            status TEXT DEFAULT 'active',
            created_at BIGINT
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER,
            order_id INTEGER,
            sender_user_id BIGINT,
            sender_role TEXT,
            message_text TEXT,
            media_type TEXT,
            media_file_id TEXT,
            created_at BIGINT
        );
        """)

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
def get_pool():
    return _pool
