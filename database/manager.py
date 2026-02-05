import aiosqlite
import asyncio
from typing import Optional, List, Dict, Any
try:
    from .models import (
        CREATE_USERS_TABLE, CREATE_CATEGORIES_TABLE, CREATE_PRODUCTS_TABLE,
        CREATE_ORDERS_TABLE, CREATE_FINANCIAL_LOGS_TABLE, CREATE_TRUST_LOGS_TABLE,
        CREATE_SETTINGS_TABLE, CREATE_PAYMENT_METHODS_TABLE, CREATE_PROVIDERS_TABLE, DEFAULT_SETTINGS
    )
except ImportError:
    from database.models import (
        CREATE_USERS_TABLE, CREATE_CATEGORIES_TABLE, CREATE_PRODUCTS_TABLE,
        CREATE_ORDERS_TABLE, CREATE_FINANCIAL_LOGS_TABLE, CREATE_TRUST_LOGS_TABLE,
        CREATE_SETTINGS_TABLE, CREATE_PAYMENT_METHODS_TABLE, CREATE_PROVIDERS_TABLE, DEFAULT_SETTINGS
    )
from config.settings import DB_PATH, OrderStatus

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = asyncio.Lock()
        self._db = None

    async def connect(self):
        if self._db is None:
            self._db = await aiosqlite.connect(self.db_path)
            self._db.row_factory = aiosqlite.Row
        return self._db

    async def init_db(self):
        async with self._lock:
            db = await self.connect()
            await db.execute(CREATE_USERS_TABLE)
            await db.execute(CREATE_CATEGORIES_TABLE)
            await db.execute(CREATE_PROVIDERS_TABLE)
            await db.execute(CREATE_PRODUCTS_TABLE)
            await db.execute(CREATE_ORDERS_TABLE)
            await db.execute(CREATE_FINANCIAL_LOGS_TABLE)
            await db.execute(CREATE_TRUST_LOGS_TABLE)
            await db.execute(CREATE_SETTINGS_TABLE)
            await db.execute(CREATE_PAYMENT_METHODS_TABLE)
            
            for key, val in DEFAULT_SETTINGS:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
            
            await db.commit()

    # --- عمليات المستخدمين والرتب ---
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create_user(self, telegram_id: int, username: str, role: str = 'USER'):
        db = await self.connect()
        await db.execute("INSERT OR IGNORE INTO users (telegram_id, username, role) VALUES (?, ?, ?)", (telegram_id, username, role))
        await db.commit()

    async def update_user_role(self, telegram_id: int, role: str):
        db = await self.connect()
        await db.execute("UPDATE users SET role = ? WHERE telegram_id = ?", (role, telegram_id))
        await db.commit()

    async def has_open_order(self, user_id: int) -> bool:
        db = await self.connect()
        cursor = await db.execute("""
            SELECT COUNT(*) as count FROM orders 
            WHERE user_id = ? AND status NOT IN (?, ?, ?)
        """, (user_id, OrderStatus.COMPLETED, OrderStatus.FAILED, OrderStatus.CANCELED))
        row = await cursor.fetchone()
        return row['count'] > 0

    async def update_user_balance(self, user_id: int, amount: float, log_type: str, admin_id: int = None, reason: str = None, order_id: int = None):
        async with self._lock:
            db = await self.connect()
            await db.execute("BEGIN")
            try:
                cursor = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,))
                user = await cursor.fetchone()
                if not user: raise Exception("User not found")
                balance_before = user['balance']
                balance_after = balance_before + amount
                if balance_after < 0: raise Exception("Insufficient balance")
                await db.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (balance_after, user_id))
                await db.execute("""
                    INSERT INTO financial_logs (user_id, order_id, type, amount, balance_before, balance_after, admin_id, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, order_id, log_type, amount, balance_before, balance_after, admin_id, reason))
                await db.commit()
                return True, balance_after
            except Exception as e:
                await db.rollback()
                return False, str(e)

    # --- عمليات المنتجات والأقسام والمزودين ---
    async def get_categories(self, only_active: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM categories"
        if only_active: query += " WHERE is_active = 1"
        db = await self.connect()
        cursor = await db.execute(query)
        return [dict(row) for row in await cursor.fetchall()]

    async def add_category(self, name: str):
        db = await self.connect()
        await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()

    async def get_providers(self) -> List[Dict[str, Any]]:
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM providers WHERE is_active = 1")
        return [dict(row) for row in await cursor.fetchall()]

    async def get_products(self, category_id: int = None, only_active: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        if category_id:
            query += " AND category_id = ?"
            params.append(category_id)
        if only_active:
            query += " AND is_active = 1 AND type != 'DISABLED'"
        db = await self.connect()
        cursor = await db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]

    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def add_product(self, category_id: int, name: str, description: str, price_usd: float, provider_id: int = None, variation_id: str = None, type: str = 'MANUAL'):
        db = await self.connect()
        await db.execute("""
            INSERT INTO products (category_id, provider_id, name, description, price_usd, variation_id, type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (category_id, provider_id, name, description, price_usd, variation_id, type))
        await db.commit()

    # --- عمليات الطلبات ---
    async def create_order(self, user_id: int, product_id: int, player_id: str, price_usd: float, price_local: float, exchange_rate: float, status: str = OrderStatus.NEW) -> int:
        db = await self.connect()
        cursor = await db.execute("""
            INSERT INTO orders (user_id, product_id, player_id, price_usd, price_local, exchange_rate, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, product_id, player_id, price_usd, price_local, exchange_rate, status))
        order_id = cursor.lastrowid
        await db.commit()
        return order_id

    async def update_order_status(self, order_id: int, status: str, admin_notes: str = None, execution_type: str = 'MANUAL', operator_id: int = None):
        db = await self.connect()
        await db.execute("""
            UPDATE orders SET status = ?, admin_notes = ?, execution_type = ?, operator_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (status, admin_notes, execution_type, operator_id, order_id))
        
        if status in [OrderStatus.COMPLETED, OrderStatus.FAILED]:
            cursor = await db.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,))
            order = await cursor.fetchone()
            if order:
                action_text = f"تم {'إكمال' if status == OrderStatus.COMPLETED else 'فشل'} الطلب #{order_id}"
                await db.execute("""
                    INSERT INTO trust_logs (order_id, user_id, action_text, execution_type)
                    VALUES (?, ?, ?, ?)
                """, (order_id, order['user_id'], action_text, execution_type))
        await db.commit()

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        cursor = await db.execute("""
            SELECT o.*, p.name as product_name, u.username, u.telegram_id
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.telegram_id
            WHERE o.id = ?
        """, (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    # --- الإعدادات ---
    async def get_setting(self, key: str, default: Any = None) -> Any:
        db = await self.connect()
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row['value'] if row else default

    async def set_setting(self, key: str, value: str):
        db = await self.connect()
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

    # --- طرق الدفع ---
    async def get_payment_methods(self, only_active: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM payment_methods"
        if only_active: query += " WHERE is_active = 1"
        db = await self.connect()
        cursor = await db.execute(query)
        return [dict(row) for row in await cursor.fetchall()]

    async def add_payment_method(self, name: str, description: str):
        db = await self.connect()
        await db.execute("INSERT INTO payment_methods (name, description) VALUES (?, ?)", (name, description))
        await db.commit()

    async def get_payment_method(self, method_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM payment_methods WHERE id = ?", (method_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_stats(self) -> Dict[str, Any]:
        db = await self.connect()
        stats = {}
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE date(created_at) = date('now')")
        stats['today_orders'] = (await cursor.fetchone())['count']
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE execution_type = 'MANUAL'")
        stats['manual_count'] = (await cursor.fetchone())['count']
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE execution_type = 'AUTO'")
        stats['auto_count'] = (await cursor.fetchone())['count']
        return stats

    async def get_trust_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM trust_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in await cursor.fetchall()]

    async def get_active_users(self) -> List[int]:
        db = await self.connect()
        cursor = await db.execute("SELECT telegram_id FROM users WHERE is_blocked = 0")
        return [row['telegram_id'] for row in await cursor.fetchall()]

db_manager = DatabaseManager(DB_PATH)
