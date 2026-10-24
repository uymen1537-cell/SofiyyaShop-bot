import aiosqlite
from config import DB_PATH
from datetime import datetime

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                role TEXT DEFAULT 'customer',  -- admin, mahsulotchi, courier, customer
                phone TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                photo_file_id TEXT,
                price INTEGER NOT NULL,
                category TEXT NOT NULL,  -- mavjud, yolda, buyurtma
                is_active INTEGER DEFAULT 1,
                added_by INTEGER,
                channel_message_id INTEGER,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                product_price INTEGER,
                delivery_price INTEGER DEFAULT 0,
                total_price INTEGER,
                lat REAL,
                lon REAL,
                address_text TEXT,
                status TEXT DEFAULT 'new',  -- new, accepted, delivering, delivered, cancelled
                courier_id INTEGER,
                estimated_minutes INTEGER,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)
        await db.commit()


async def get_or_create_user(telegram_id: int, username: str = None, full_name: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            user = await cursor.fetchone()
        if user:
            return dict(user)
        role = "customer"
        from config import ADMIN_IDS, MAHSULOTCHI_IDS, COURIER_IDS
        if telegram_id in ADMIN_IDS:
            role = "admin"
        elif telegram_id in MAHSULOTCHI_IDS:
            role = "mahsulotchi"
        elif telegram_id in COURIER_IDS:
            role = "courier"
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO users (telegram_id, username, full_name, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (telegram_id, username, full_name, role, now)
        )
        await db.commit()
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            user = await cursor.fetchone()
        return dict(user)


async def update_user_role(telegram_id: int, role: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET role = ? WHERE telegram_id = ?", (role, telegram_id))
        await db.commit()


async def add_product(name: str, description: str, photo_file_id: str, price: int, category: str, added_by: int):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO products (name, description, photo_file_id, price, category, added_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, description, photo_file_id, price, category, added_by, now)
        )
        await db.commit()
        return cursor.lastrowid


async def set_channel_message_id(product_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE products SET channel_message_id = ? WHERE id = ?",
            (message_id, product_id)
        )
        await db.commit()


async def get_products_by_category(category: str, only_active: bool = True):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM products WHERE category = ?"
        params = [category]
        if only_active:
            query += " AND is_active = 1"
        query += " ORDER BY id DESC"
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None


async def get_all_products(only_active: bool = False):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM products"
        if only_active:
            query += " WHERE is_active = 1"
        query += " ORDER BY id DESC"
        async with db.execute(query) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def deactivate_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET is_active = 0 WHERE id = ?", (product_id,))
        await db.commit()


async def activate_product(product_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE products SET is_active = 1 WHERE id = ?", (product_id,))
        await db.commit()


async def update_product(product_id: int, name: str = None, description: str = None, price: int = None, category: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if price is not None:
            updates.append("price = ?")
            params.append(price)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if not updates:
            return
        params.append(product_id)
        query = f"UPDATE products SET {', '.join(updates)} WHERE id = ?"
        await db.execute(query, params)
        await db.commit()


async def create_order(user_id: int, product_id: int, quantity: int, product_price: int,
                       delivery_price: int, total: int, lat: float, lon: float,
                       address_text: str, estimated_minutes: int):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        cursor = await db.execute(
            """INSERT INTO orders 
               (user_id, product_id, quantity, product_price, delivery_price, total_price,
                lat, lon, address_text, status, estimated_minutes, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?)""",
            (user_id, product_id, quantity, product_price, delivery_price, total,
             lat, lon, address_text, estimated_minutes, now, now)
        )
        await db.commit()
        return cursor.lastrowid


async def get_order(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT o.*, u.telegram_id as user_tg_id, u.full_name as user_name, u.username as user_username,
                   p.name as product_name, p.photo_file_id
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN products p ON o.product_id = p.id
            WHERE o.id = ?
        """, (order_id,)) as cursor:
            row = await cursor.fetchone()
        return dict(row) if row else None


async def get_new_orders():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT o.*, u.telegram_id as user_tg_id, u.full_name as user_name, u.username as user_username,
                   p.name as product_name
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN products p ON o.product_id = p.id
            WHERE o.status = 'new'
            ORDER BY o.id ASC
        """) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_courier_orders(courier_tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Avval courier ning user_id sini topamiz
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (courier_tg_id,)) as cursor:
            c = await cursor.fetchone()
        if not c:
            return []
        courier_id = c[0]
        async with db.execute("""
            SELECT o.*, u.telegram_id as user_tg_id, u.full_name as user_name, u.username as user_username,
                   p.name as product_name
            FROM orders o
            JOIN users u ON o.user_id = u.id
            JOIN products p ON o.product_id = p.id
            WHERE o.courier_id = ? AND o.status IN ('accepted', 'delivering')
            ORDER BY o.id DESC
        """, (courier_id,)) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def accept_order(order_id: int, courier_tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (courier_tg_id,)) as cursor:
            c = await cursor.fetchone()
        if not c:
            return False
        courier_id = c[0]
        now = datetime.now().isoformat()
        await db.execute(
            "UPDATE orders SET status = 'accepted', courier_id = ?, updated_at = ? WHERE id = ? AND status = 'new'",
            (courier_id, now, order_id)
        )
        await db.commit()
        return True


async def update_order_status(order_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        await db.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, order_id)
        )
        await db.commit()


async def get_user_orders(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            u = await cursor.fetchone()
        if not u:
            return []
        async with db.execute("""
            SELECT o.*, p.name as product_name
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.user_id = ?
            ORDER BY o.id DESC LIMIT 20
        """, (u[0],)) as cursor:
            rows = await cursor.fetchall()
        return [dict(r) for r in rows]
