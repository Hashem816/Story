import aiosqlite
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
try:
    from .models import (
        CREATE_USERS_TABLE, CREATE_USERS_INDEX, CREATE_CATEGORIES_TABLE, CREATE_PRODUCTS_TABLE,
        CREATE_ORDERS_TABLE, CREATE_FINANCIAL_LOGS_TABLE, CREATE_TRUST_LOGS_TABLE,
        CREATE_SETTINGS_TABLE, CREATE_PAYMENT_METHODS_TABLE, CREATE_PROVIDERS_TABLE,
        CREATE_COUPONS_TABLE, CREATE_COUPON_USAGE_TABLE, CREATE_AUDIT_LOGS_TABLE,
        CREATE_BROADCAST_HISTORY_TABLE, CREATE_RATE_LIMITS_TABLE, CREATE_ADMIN_SESSIONS_TABLE,
        DEFAULT_SETTINGS
    )
except ImportError:
    from database.models import (
        CREATE_USERS_TABLE, CREATE_USERS_INDEX, CREATE_CATEGORIES_TABLE, CREATE_PRODUCTS_TABLE,
        CREATE_ORDERS_TABLE, CREATE_FINANCIAL_LOGS_TABLE, CREATE_TRUST_LOGS_TABLE,
        CREATE_SETTINGS_TABLE, CREATE_PAYMENT_METHODS_TABLE, CREATE_PROVIDERS_TABLE,
        CREATE_COUPONS_TABLE, CREATE_COUPON_USAGE_TABLE, CREATE_AUDIT_LOGS_TABLE,
        CREATE_BROADCAST_HISTORY_TABLE, CREATE_RATE_LIMITS_TABLE, CREATE_ADMIN_SESSIONS_TABLE,
        DEFAULT_SETTINGS
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
        """تهيئة قاعدة البيانات بجميع الجداول والفهارس"""
        async with self._lock:
            db = await self.connect()
            
            # الجداول الأساسية
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
            
            # الجداول الجديدة
            await db.execute(CREATE_COUPONS_TABLE)
            await db.execute(CREATE_COUPON_USAGE_TABLE)
            await db.execute(CREATE_AUDIT_LOGS_TABLE)
            await db.execute(CREATE_BROADCAST_HISTORY_TABLE)
            await db.execute(CREATE_RATE_LIMITS_TABLE)
            await db.execute(CREATE_ADMIN_SESSIONS_TABLE)
            
            # تحديث جدول المستخدمين لإضافة الأعمدة الجديدة إن لم تكن موجودة
            try:
                await db.execute("ALTER TABLE users ADD COLUMN first_name TEXT")
            except: pass
            try:
                await db.execute("ALTER TABLE users ADD COLUMN last_name TEXT")
            except: pass
            try:
                await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ar'")
            except: pass
            
            # الإعدادات الافتراضية
            for key, val in DEFAULT_SETTINGS:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
            
            await db.commit()

    # --- عمليات المستخدمين والرتب ---
    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def create_user(self, telegram_id: int, username: str, first_name: str = None, last_name: str = None, role: str = 'USER', language: str = 'ar'):
        """إنشاء مستخدم جديد مع دعم اللغة"""
        db = await self.connect()
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_name, role, language) VALUES (?, ?, ?, ?, ?, ?)",
            (telegram_id, username, first_name, last_name, role, language)
        )
        await db.commit()

    async def update_user_role(self, telegram_id: int, role: str):
        db = await self.connect()
        await db.execute("UPDATE users SET role = ? WHERE telegram_id = ?", (role, telegram_id))
        await db.commit()

    async def update_user_language(self, telegram_id: int, language: str):
        """تحديث لغة المستخدم"""
        db = await self.connect()
        await db.execute("UPDATE users SET language = ? WHERE telegram_id = ?", (language, telegram_id))
        await db.commit()

    async def search_users(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """بحث متقدم عن المستخدمين بـ ID أو Username أو الاسم"""
        db = await self.connect()
        
        if query.isdigit():
            # البحث بـ ID
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ? LIMIT ?",
                (int(query), limit)
            )
        else:
            # البحث بـ Username أو الاسم
            search_pattern = f"%{query}%"
            cursor = await db.execute(
                """SELECT * FROM users 
                   WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                   ORDER BY created_at DESC LIMIT ?""",
                (search_pattern, search_pattern, search_pattern, limit)
            )
        
        return [dict(row) for row in await cursor.fetchall()]

    async def get_users_paginated(self, page: int = 1, per_page: int = 10, filter_blocked: bool = None) -> Dict[str, Any]:
        """جلب المستخدمين مع Pagination"""
        db = await self.connect()
        offset = (page - 1) * per_page
        
        query = "SELECT * FROM users"
        count_query = "SELECT COUNT(*) as total FROM users"
        params = []
        
        if filter_blocked is not None:
            query += " WHERE is_blocked = ?"
            count_query += " WHERE is_blocked = ?"
            params.append(1 if filter_blocked else 0)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        cursor = await db.execute(query, params)
        users = [dict(row) for row in await cursor.fetchall()]
        
        cursor = await db.execute(count_query, params[:1] if filter_blocked is not None else [])
        total = (await cursor.fetchone())['total']
        
        return {
            'users': users,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        }

    async def get_user_orders_count(self, user_id: int) -> int:
        """عدد طلبات المستخدم"""
        db = await self.connect()
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE user_id = ?", (user_id,))
        return (await cursor.fetchone())['count']

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

    async def get_user_orders(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """جلب طلبات مستخدم معين"""
        db = await self.connect()
        cursor = await db.execute("""
            SELECT o.*, p.name as product_name
            FROM orders o
            JOIN products p ON o.product_id = p.id
            WHERE o.user_id = ?
            ORDER BY o.created_at DESC LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in await cursor.fetchall()]

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

    # --- الإحصائيات المحسّنة ---
    async def get_stats(self) -> Dict[str, Any]:
        """إحصائيات شاملة للمتجر"""
        db = await self.connect()
        stats = {}
        
        # إحصائيات الطلبات
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE date(created_at) = date('now')")
        stats['today_orders'] = (await cursor.fetchone())['count']
        
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE execution_type = 'MANUAL'")
        stats['manual_count'] = (await cursor.fetchone())['count']
        
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE execution_type = 'AUTO'")
        stats['auto_count'] = (await cursor.fetchone())['count']
        
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE status = ?", (OrderStatus.COMPLETED,))
        stats['completed_orders'] = (await cursor.fetchone())['count']
        
        # إحصائيات المستخدمين
        cursor = await db.execute("SELECT COUNT(*) as count FROM users")
        stats['total_users'] = (await cursor.fetchone())['count']
        
        cursor = await db.execute("SELECT COUNT(*) as count FROM users WHERE is_blocked = 1")
        stats['blocked_users'] = (await cursor.fetchone())['count']
        
        cursor = await db.execute("SELECT COUNT(*) as count FROM users WHERE date(created_at) = date('now')")
        stats['new_users_today'] = (await cursor.fetchone())['count']
        
        # إحصائيات مالية
        cursor = await db.execute("SELECT COALESCE(SUM(balance), 0) as total FROM users")
        stats['total_balance'] = (await cursor.fetchone())['total']
        
        cursor = await db.execute("""
            SELECT COALESCE(SUM(price_usd), 0) as revenue 
            FROM orders 
            WHERE status = ? AND date(created_at) = date('now')
        """, (OrderStatus.COMPLETED,))
        stats['today_revenue'] = (await cursor.fetchone())['revenue']
        
        return stats

    async def get_trust_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM trust_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in await cursor.fetchall()]

    async def get_active_users(self, language: str = None) -> List[int]:
        """جلب المستخدمين النشطين (مع فلترة اختيارية باللغة)"""
        db = await self.connect()
        query = "SELECT telegram_id FROM users WHERE is_blocked = 0"
        params = []
        if language:
            query += " AND language = ?"
            params.append(language)
        cursor = await db.execute(query, params)
        return [row['telegram_id'] for row in await cursor.fetchall()]

    # --- نظام الكوبونات ---
    async def create_coupon(self, code: str, type: str, value: float, max_uses: int, min_amount: float, expires_at: str, created_by: int):
        """إنشاء كوبون جديد"""
        db = await self.connect()
        await db.execute("""
            INSERT INTO coupons (code, type, value, max_uses, min_amount, expires_at, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code, type, value, max_uses, min_amount, expires_at, created_by))
        await db.commit()

    async def get_coupon(self, code: str) -> Optional[Dict[str, Any]]:
        """جلب كوبون بالكود"""
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM coupons WHERE code = ?", (code,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def validate_coupon(self, code: str, user_id: int, amount: float) -> tuple[bool, str, float]:
        """التحقق من صلاحية الكوبون وحساب الخصم"""
        coupon = await self.get_coupon(code)
        if not coupon:
            return False, "الكوبون غير موجود", 0
        
        if not coupon['is_active']:
            return False, "الكوبون غير نشط", 0
        
        if coupon['used_count'] >= coupon['max_uses']:
            return False, "تم استخدام الكوبون بالكامل", 0
        
        if coupon['expires_at']:
            if datetime.now() > datetime.fromisoformat(coupon['expires_at']):
                return False, "الكوبون منتهي الصلاحية", 0
        
        if amount < coupon['min_amount']:
            return False, f"الحد الأدنى للطلب {coupon['min_amount']}$", 0
        
        # حساب الخصم
        if coupon['type'] == 'PERCENTAGE':
            discount = amount * (coupon['value'] / 100)
        else:  # FIXED
            discount = coupon['value']
        
        return True, "الكوبون صالح", discount

    async def use_coupon(self, code: str, user_id: int, order_id: int, discount_amount: float):
        """تسجيل استخدام الكوبون"""
        db = await self.connect()
        coupon = await self.get_coupon(code)
        if coupon:
            await db.execute("""
                INSERT INTO coupon_usage (coupon_id, user_id, order_id, discount_amount)
                VALUES (?, ?, ?, ?)
            """, (coupon['id'], user_id, order_id, discount_amount))
            await db.execute("UPDATE coupons SET used_count = used_count + 1 WHERE id = ?", (coupon['id'],))
            await db.commit()

    async def get_all_coupons(self) -> List[Dict[str, Any]]:
        """جلب جميع الكوبونات"""
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM coupons ORDER BY created_at DESC")
        return [dict(row) for row in await cursor.fetchall()]

    async def delete_coupon(self, coupon_id: int):
        """حذف كوبون"""
        db = await self.connect()
        await db.execute("DELETE FROM coupons WHERE id = ?", (coupon_id,))
        await db.commit()

    # --- سجل العمليات (Audit Log) ---
    async def log_admin_action(self, admin_id: int, action: str, target_type: str = None, target_id: int = None, details: str = None):
        """تسجيل عملية إدارية"""
        db = await self.connect()
        await db.execute("""
            INSERT INTO audit_logs (admin_id, action, target_type, target_id, details)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_id, action, target_type, target_id, details))
        await db.commit()

    async def get_audit_logs(self, limit: int = 50, admin_id: int = None) -> List[Dict[str, Any]]:
        """جلب سجل العمليات"""
        db = await self.connect()
        query = "SELECT * FROM audit_logs"
        params = []
        if admin_id:
            query += " WHERE admin_id = ?"
            params.append(admin_id)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]

    # --- سجل البث الجماعي ---
    async def save_broadcast(self, admin_id: int, message_text: str, target_count: int, success_count: int, fail_count: int):
        """حفظ سجل البث الجماعي"""
        db = await self.connect()
        await db.execute("""
            INSERT INTO broadcast_history (admin_id, message_text, target_count, success_count, fail_count)
            VALUES (?, ?, ?, ?, ?)
        """, (admin_id, message_text, target_count, success_count, fail_count))
        await db.commit()

    async def get_broadcast_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """جلب سجل البث الجماعي"""
        db = await self.connect()
        cursor = await db.execute("SELECT * FROM broadcast_history ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in await cursor.fetchall()]

    # --- Rate Limiting ---
    async def check_rate_limit(self, user_id: int, action_type: str, max_count: int, window_minutes: int) -> bool:
        """التحقق من معدل الطلبات"""
        db = await self.connect()
        window_start = datetime.now() - timedelta(minutes=window_minutes)
        
        cursor = await db.execute("""
            SELECT SUM(count) as total FROM rate_limits
            WHERE user_id = ? AND action_type = ? AND window_start > ?
        """, (user_id, action_type, window_start.isoformat()))
        
        result = await cursor.fetchone()
        total = result['total'] if result['total'] else 0
        
        if total >= max_count:
            return False
        
        # تسجيل الطلب
        await db.execute("""
            INSERT INTO rate_limits (user_id, action_type, count)
            VALUES (?, ?, 1)
        """, (user_id, action_type))
        await db.commit()
        
        return True

db_manager = DatabaseManager(DB_PATH)
