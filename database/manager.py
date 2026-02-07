"""
Database Manager - Ultimate Stable Edition
- Optimized for High Concurrency
- Robust Error Handling
- Clean Connection Management
"""

import aiosqlite
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

try:
    from .models import *
except ImportError:
    from database.models import *

from config.settings import DB_PATH, OrderStatus

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._db = None
        self._lock = asyncio.Lock()
        
    async def connect(self):
        if self._db is None:
            async with self._lock:
                if self._db is None:
                    self._db = await aiosqlite.connect(self.db_path, timeout=60)
                    self._db.row_factory = aiosqlite.Row
                    await self._db.execute("PRAGMA journal_mode=WAL")
                    await self._db.execute("PRAGMA foreign_keys=ON")
                    await self._db.execute("PRAGMA synchronous=NORMAL")
        return self._db

    async def init_db(self):
        db = await self.connect()
        async with self._lock:
            # Create all tables sequentially
            await db.execute(CREATE_USERS_TABLE)
            await db.execute(CREATE_USERS_INDEX)
            await db.execute(CREATE_CATEGORIES_TABLE)
            await db.execute(CREATE_PROVIDERS_TABLE)
            await db.execute(CREATE_PRODUCTS_TABLE)
            await db.execute(CREATE_ORDERS_TABLE)
            await db.execute(CREATE_FINANCIAL_LOGS_TABLE)
            await db.execute(CREATE_TRUST_LOGS_TABLE)
            await db.execute(CREATE_SETTINGS_TABLE)
            await db.execute(CREATE_PAYMENT_METHODS_TABLE)
            await db.execute(CREATE_COUPONS_TABLE)
            await db.execute(CREATE_COUPON_USAGE_TABLE)
            await db.execute(CREATE_AUDIT_LOGS_TABLE)
            await db.execute(CREATE_BROADCAST_HISTORY_TABLE)
            await db.execute(CREATE_RATE_LIMITS_TABLE)
            await db.execute(CREATE_ADMIN_SESSIONS_TABLE)
            
            # Add indexes
            await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_financial_logs_user_id ON financial_logs(user_id)")
            
            # Add missing columns
            try: await db.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
            except: pass
            try: await db.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
            except: pass
            try: await db.execute("ALTER TABLE users ADD COLUMN language TEXT")
            except: pass
            try: await db.execute("ALTER TABLE payment_methods ADD COLUMN deleted_at DATETIME DEFAULT NULL")
            except: pass
            
            # Default settings
            for key, val in DEFAULT_SETTINGS:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
            
            await db.commit()

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def create_user(self, telegram_id: int, username: str, first_name: str = None, last_name: str = None, role: str = 'USER', language: str = 'ar'):
        db = await self.connect()
        async with self._lock:
            await db.execute(
                "INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_name, role, language) VALUES (?, ?, ?, ?, ?, ?)",
                (telegram_id, username, first_name, last_name, role, language)
            )
            await db.commit()

    async def update_user_balance(self, user_id: int, amount: float, log_type: str, reason: str = None, admin_id: int = None, order_id: int = None) -> tuple[bool, Any]:
        db = await self.connect()
        async with self._lock:
            try:
                async with db.execute("SELECT balance FROM users WHERE telegram_id = ?", (user_id,)) as cursor:
                    user = await cursor.fetchone()
                    if not user: return False, "User not found"
                    
                    balance_before = user['balance']
                    balance_after = balance_before + amount
                    if balance_after < 0: return False, "Insufficient balance"
                    
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

    async def get_product(self, product_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("SELECT * FROM products WHERE id = ?", (product_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_products(self, category_id: int = None, only_active: bool = True) -> List[Dict[str, Any]]:
        db = await self.connect()
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        if category_id:
            query += " AND category_id = ?"
            params.append(category_id)
        if only_active:
            query += " AND is_active = 1"
        async with db.execute(query, params) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def get_categories(self, only_active: bool = True) -> List[Dict[str, Any]]:
        db = await self.connect()
        query = "SELECT * FROM categories"
        if only_active: query += " WHERE is_active = 1"
        async with db.execute(query) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def create_order(self, user_id: int, product_id: int, player_id: str, price_usd: float, price_local: float, exchange_rate: float, status: str = OrderStatus.NEW) -> int:
        db = await self.connect()
        async with self._lock:
            cursor = await db.execute("""
                INSERT INTO orders (user_id, product_id, player_id, price_usd, price_local, exchange_rate, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, product_id, player_id, price_usd, price_local, exchange_rate, status))
            order_id = cursor.lastrowid
            await db.commit()
            return order_id

    async def update_order_status(self, order_id: int, status: str, admin_notes: str = None, execution_type: str = 'MANUAL', operator_id: int = None):
        db = await self.connect()
        async with self._lock:
            await db.execute("""
                UPDATE orders SET status = ?, admin_notes = ?, execution_type = ?, operator_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, admin_notes, execution_type, operator_id, order_id))
            
            if status in [OrderStatus.COMPLETED, OrderStatus.FAILED]:
                async with db.execute("SELECT user_id FROM orders WHERE id = ?", (order_id,)) as cursor:
                    order = await cursor.fetchone()
                    if order:
                        await db.execute("""
                            INSERT INTO trust_logs (order_id, user_id, action_text, execution_type)
                            VALUES (?, ?, ?, ?)
                        """, (order_id, order['user_id'], f"Order #{order_id} {status}", execution_type))
            await db.commit()

    async def get_order(self, order_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("""
            SELECT o.*, p.name as product_name, u.username, u.telegram_id
            FROM orders o
            JOIN products p ON o.product_id = p.id
            JOIN users u ON o.user_id = u.telegram_id
            WHERE o.id = ?
        """, (order_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_user_orders(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("""
            SELECT o.*, p.name as product_name
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.user_id = ?
            ORDER BY o.created_at DESC LIMIT ?
        """, (user_id, limit)) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def has_open_order(self, user_id: int) -> bool:
        db = await self.connect()
        async with db.execute("""
            SELECT COUNT(*) as count FROM orders 
            WHERE user_id = ? AND status NOT IN (?, ?, ?)
        """, (user_id, OrderStatus.COMPLETED, OrderStatus.FAILED, OrderStatus.CANCELED)) as cursor:
            row = await cursor.fetchone()
            return row['count'] > 0

    async def get_setting(self, key: str, default: Any = None) -> Any:
        db = await self.connect()
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row['value'] if row else default

    async def set_setting(self, key: str, value: str):
        db = await self.connect()
        async with self._lock:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            await db.commit()

    async def get_payment_methods(self, only_active: bool = True) -> List[Dict[str, Any]]:
        db = await self.connect()
        query = "SELECT * FROM payment_methods WHERE deleted_at IS NULL"
        if only_active: query += " AND is_active = 1"
        async with db.execute(query) as cursor:
            return [dict(row) for row in await cursor.fetchall()]

    async def get_payment_method(self, method_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        async with db.execute("SELECT * FROM payment_methods WHERE id = ? AND deleted_at IS NULL", (method_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def validate_coupon(self, code: str, user_id: int, amount: float) -> tuple[bool, str, float]:
        db = await self.connect()
        async with db.execute("SELECT * FROM coupons WHERE code = ?", (code,)) as cursor:
            coupon = await cursor.fetchone()
            if not coupon: return False, "Coupon not found", 0
            if not coupon['is_active']: return False, "Coupon inactive", 0
            if coupon['used_count'] >= coupon['max_uses']: return False, "Coupon fully used", 0
            if amount < coupon['min_amount']: return False, f"Min amount {coupon['min_amount']}$", 0
            
            discount = amount * (coupon['value'] / 100) if coupon['type'] == 'PERCENTAGE' else coupon['value']
            return True, "Valid", discount

    async def use_coupon(self, code: str, user_id: int, order_id: int, discount_amount: float):
        db = await self.connect()
        async with self._lock:
            async with db.execute("SELECT id FROM coupons WHERE code = ?", (code,)) as cursor:
                coupon = await cursor.fetchone()
                if coupon:
                    await db.execute("""
                        INSERT INTO coupon_usage (coupon_id, user_id, order_id, discount_amount)
                        VALUES (?, ?, ?, ?)
                    """, (coupon['id'], user_id, order_id, discount_amount))
                    await db.execute("UPDATE coupons SET used_count = used_count + 1 WHERE id = ?", (coupon['id'],))
                    await db.commit()

    async def log_admin_action(self, admin_id: int, action: str, target_type: str = None, target_id: int = None, details: str = None):
        db = await self.connect()
        async with self._lock:
            await db.execute("""
                INSERT INTO audit_logs (admin_id, action, target_type, target_id, details)
                VALUES (?, ?, ?, ?, ?)
            """, (admin_id, action, target_type, target_id, details))
            await db.commit()

    async def update_user_currency(self, telegram_id: int, currency: str):
        db = await self.connect()
        async with self._lock:
            await db.execute("UPDATE users SET currency = ? WHERE telegram_id = ?", (currency, telegram_id))
            await db.commit()

db_manager = DatabaseManager(DB_PATH)
