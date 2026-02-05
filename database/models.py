# تعريف أوامر إنشاء الجداول لقاعدة بيانات SQLite v2.2 - Ultimate
# تحديث لدعم الرتب، المزودين، والتسعير المرن

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    username TEXT,
    balance REAL DEFAULT 0,
    role TEXT DEFAULT 'USER', -- SUPER_ADMIN, OPERATOR, SUPPORT, USER
    is_blocked INTEGER DEFAULT 0,
    daily_order_limit INTEGER DEFAULT 10,
    internal_notes TEXT,
    is_active INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CATEGORIES_TABLE = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
);
"""

CREATE_PROVIDERS_TABLE = """
CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    api_key TEXT,
    base_url TEXT,
    is_active INTEGER DEFAULT 1
);
"""

CREATE_PRODUCTS_TABLE = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER,
    provider_id INTEGER,
    name TEXT NOT NULL,
    description TEXT,
    price_usd REAL NOT NULL, -- السعر بالدولار دائماً
    type TEXT DEFAULT 'MANUAL', -- AUTOMATIC, MANUAL, DISABLED
    variation_id TEXT, 
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY(category_id) REFERENCES categories(id),
    FOREIGN KEY(provider_id) REFERENCES providers(id)
);
"""

CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_id INTEGER,
    player_id TEXT,
    price_usd REAL, -- السعر بالدولار وقت الطلب
    price_local REAL, -- السعر بالعملة المحلية وقت الطلب
    exchange_rate REAL, -- سعر الصرف وقت الطلب
    status TEXT DEFAULT 'NEW', -- NEW, PENDING_PAYMENT, PAID, PENDING_REVIEW, IN_PROGRESS, COMPLETED, FAILED, CANCELED
    payment_method_id INTEGER,
    payment_receipt_file_id TEXT, -- صورة الإيصال
    execution_type TEXT DEFAULT 'MANUAL',
    admin_notes TEXT,
    operator_id INTEGER, -- من قام بتأكيد الطلب
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(product_id) REFERENCES products(id),
    FOREIGN KEY(payment_method_id) REFERENCES payment_methods(id)
);
"""

CREATE_FINANCIAL_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS financial_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    order_id INTEGER,
    type TEXT, -- DEPOSIT, WITHDRAWAL, REFUND, PURCHASE, EXCHANGE_CHANGE
    amount REAL,
    balance_before REAL,
    balance_after REAL,
    admin_id INTEGER,
    reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""

CREATE_TRUST_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS trust_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER,
    user_id INTEGER,
    action_text TEXT,
    execution_type TEXT, 
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(order_id) REFERENCES orders(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);
"""

CREATE_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

CREATE_PAYMENT_METHODS_TABLE = """
CREATE TABLE IF NOT EXISTS payment_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    is_active INTEGER DEFAULT 1
);
"""

# الإعدادات الافتراضية للنظام المطور
DEFAULT_SETTINGS = [
    ('store_mode', 'MANUAL'), # AUTO, MANUAL, MAINTENANCE
    ('dollar_rate', '12500'), # سعر الصرف الافتراضي
    ('auto_update_rate', '0'),
    ('global_daily_limit', '10'),
    ('emergency_stop', '0'),
    ('maintenance_message', '🛠 المتجر في حالة صيانة حالياً، سنعود قريباً.'),
    ('support_message', 'تواصل معنا عبر المعرف التالي: @Support')
]
