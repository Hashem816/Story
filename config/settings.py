import os
from dotenv import load_dotenv
from pathlib import Path

# تحميل متغيرات البيئة من ملف .env
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# إعدادات البوت الأساسية
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0")) # Super Admin ID من ملف البيئة

# إعدادات قاعدة البيانات
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(BASE_DIR / "store_v2.db")
DATABASE_PATH = DB_PATH # Alias for compatibility

# إعدادات API (Item4Gamer)
ITEM4GAMER_API_KEY = os.getenv("ITEM4GAMER_API_KEY")
ITEM4GAMER_BASE_URL = "https://item4gamer.com/wp-json/reseller/v1"

# أوضاع المتجر العالمية
class StoreMode:
    AUTO = "AUTO"
    MANUAL = "MANUAL"
    MAINTENANCE = "MAINTENANCE"

# رتب المستخدمين
class UserRole:
    SUPER_ADMIN = "SUPER_ADMIN"
    OPERATOR = "OPERATOR"
    SUPPORT = "SUPPORT"
    USER = "USER"

# دورة حياة الطلب الكاملة
class OrderStatus:
    NEW = "NEW"
    PENDING_PAYMENT = "PENDING_PAYMENT" # بانتظار إرسال الإيصال
    PAID = "PAID" # تم الدفع (بانتظار مراجعة الإيصال)
    PENDING_REVIEW = "PENDING_REVIEW" # بانتظار مراجعة الأدمن قبل الدفع (للمنتجات اليدوية)
    IN_PROGRESS = "IN_PROGRESS" # قيد التنفيذ
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

# أنواع المنتجات
class ProductType:
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    DISABLED = "DISABLED"
