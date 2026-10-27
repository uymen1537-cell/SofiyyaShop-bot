import os
import asyncpg
from datetime import datetime
from config import DB_PATH  # fallback, not used with postgres

DATABASE_URL = os.getenv("DATABASE_URL", "")

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL environment variable is not set")
        url = DATABASE_URL
        # asyncpg needs postgresql:// not postgres://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        _pool = await asyncpg.create_pool(url, min_size=1, max_size=5, command_timeout=60)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                role TEXT DEFAULT 'customer',
                phone TEXT,
                created_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                photo_file_id TEXT,
                price INTEGER NOT NULL,
                category TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                added_by BIGINT,
                channel_message_id BIGINT,
                created_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                product_price INTEGER,
                delivery_price INTEGER DEFAULT 0,
                total_price INTEGER,
                lat DOUBLE PRECISION,
                lon DOUBLE PRECISION,
                address_text TEXT,
                status TEXT DEFAULT 'new',
                courier_id BIGINT,
                estimated_minutes INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


async def get_setting(key: str, default: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT value FROM settings WHERE key = $1", key)
        return row["value"] if row else default


async def set_setting(key: str, value: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO settings (key, value) VALUES ($1, $2)
            ON CONFLICT (key) DO UPDATE SET value = $2
            """,
            key, value
        )


async def get_shop_coords():
    from config import SHOP_LAT, SHOP_LON
    lat = await get_setting("shop_lat")
    lon = await get_setting("shop_lon")
    return (
        float(lat) if lat else SHOP_LAT,
        float(lon) if lon else SHOP_LON
    )


async def get_admins_from_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT telegram_id, full_name, username FROM users WHERE role = 'admin'"
        )
        return [dict(r) for r in rows]


async def get_or_create_user(telegram_id: int, username: str = None, full_name: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        if row:
            return dict(row)
        role = "customer"
        from config import ADMIN_IDS, MAHSULOTCHI_IDS, COURIER_IDS
        if telegram_id in ADMIN_IDS:
            role = "admin"
        elif telegram_id in MAHSULOTCHI_IDS:
            role = "mahsulotchi"
        elif telegram_id in COURIER_IDS:
            role = "courier"
        now = datetime.now().isoformat()
        await conn.execute(
            """
            INSERT INTO users (telegram_id, username, full_name, role, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            telegram_id, username, full_name, role, now
        )
        row = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", telegram_id)
        return dict(row)


async def update_user_role(telegram_id: int, role: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET role = $1 WHERE telegram_id = $2", role, telegram_id
        )


async def add_product(name: str, description: str, photo_file_id: str, price: int, category: str, added_by: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        now = datetime.now().isoformat()
        row = await conn.fetchrow(
            """
            INSERT INTO products (name, description, photo_file_id, price, category, added_by, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            name, description, photo_file_id, price, category, added_by, now
        )
        return row["id"]


async def set_channel_message_id(product_id: int, message_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE products SET channel_message_id = $1 WHERE id = $2",
            message_id, product_id
        )


async def get_products_by_category(category: str, only_active: bool = True):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if only_active:
            rows = await conn.fetch(
                "SELECT * FROM products WHERE category = $1 AND is_active = 1 ORDER BY id DESC",
                category
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM products WHERE category = $1 ORDER BY id DESC",
                category
            )
        return [dict(r) for r in rows]


async def get_product(product_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM products WHERE id = $1", product_id)
        return dict(row) if row else None


async def get_all_products(only_active: bool = False):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if only_active:
            rows = await conn.fetch(
                "SELECT * FROM products WHERE is_active = 1 ORDER BY id DESC"
            )
        else:
            rows = await conn.fetch("SELECT * FROM products ORDER BY id DESC")
        return [dict(r) for r in rows]


async def deactivate_product(product_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE products SET is_active = 0 WHERE id = $1", product_id)


async def activate_product(product_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE products SET is_active = 1 WHERE id = $1", product_id)


async def update_product(product_id: int, name: str = None, description: str = None, price: int = None, category: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if name is not None:
            await conn.execute("UPDATE products SET name = $1 WHERE id = $2", name, product_id)
        if description is not None:
            await conn.execute("UPDATE products SET description = $1 WHERE id = $2", description, product_id)
        if price is not None:
            await conn.execute("UPDATE products SET price = $1 WHERE id = $2", price, product_id)
        if category is not None:
            await conn.execute("UPDATE products SET category = $1 WHERE id = $2", category, product_id)


async def create_order(user_id, product_id, quantity, product_price, delivery_price, total, lat, lon, address_text, estimated_minutes):
    pool = await get_pool()
    async with pool.acquire() as conn:
        now = datetime.now().isoformat()
        row = await conn.fetchrow(
            """
            INSERT INTO orders (
                user_id, product_id, quantity, product_price, delivery_price,
                total_price, lat, lon, address_text, estimated_minutes, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$11)
            RETURNING id
            """,
            user_id, product_id, quantity, product_price, delivery_price,
            total, lat, lon, address_text, estimated_minutes, now
        )
        return row["id"]


async def get_order(order_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT o.*, p.name as product_name, u.full_name as user_name, u.username as user_username,
                   u.telegram_id as user_telegram_id
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.id
            WHERE o.id = $1
            """,
            order_id
        )
        return dict(row) if row else None


async def get_new_orders():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT o.*, p.name as product_name, u.full_name as user_name, u.username as user_username
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.id
            WHERE o.status = 'new'
            ORDER BY o.id DESC
            """
        )
        return [dict(r) for r in rows]


async def accept_order(order_id: int, courier_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        now = datetime.now().isoformat()
        result = await conn.execute(
            "UPDATE orders SET status = 'accepted', courier_id = $1, updated_at = $2 WHERE id = $3 AND status = 'new'",
            courier_id, now, order_id
        )
        # asyncpg: "UPDATE N"
        try:
            return int(result.split()[-1]) > 0
        except Exception:
            return False


async def update_order_status(order_id: int, status: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        now = datetime.now().isoformat()
        await conn.execute(
            "UPDATE orders SET status = $1, updated_at = $2 WHERE id = $3",
            status, now, order_id
        )


async def get_user_orders(telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT o.*, p.name as product_name
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.id
            WHERE u.telegram_id = $1
            ORDER BY o.id DESC
            LIMIT 20
            """,
            telegram_id
        )
        return [dict(r) for r in rows]


async def get_courier_orders(courier_telegram_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT o.*, p.name as product_name, u.full_name as user_name, u.username as user_username
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.id
            WHERE o.courier_id = $1 AND o.status IN ('accepted', 'delivering')
            ORDER BY o.id DESC
            """,
            courier_telegram_id
        )
        return [dict(r) for r in rows]
