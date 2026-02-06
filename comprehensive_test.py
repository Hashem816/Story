#!/usr/bin/env python3.11
"""
اختبار شامل لمشروع Telegram Bot
يختبر جميع المكونات الرئيسية للتأكد من سلامة المشروع
"""

import sys
import os
import asyncio
from typing import Dict, List, Tuple

# إضافة المسار الحالي
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ألوان للطباعة
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

test_results: Dict[str, bool] = {}


def print_header(text: str):
    """طباعة رأس القسم"""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text.center(60)}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_test(name: str, passed: bool, details: str = ""):
    """طباعة نتيجة اختبار"""
    status = f"{GREEN}✅ نجح{RESET}" if passed else f"{RED}❌ فشل{RESET}"
    print(f"{status} - {name}")
    if details:
        print(f"   {YELLOW}التفاصيل: {details}{RESET}")
    test_results[name] = passed


# ===== اختبار 1: الاستيرادات =====
def test_imports():
    """اختبار جميع الاستيرادات الأساسية"""
    print_header("اختبار 1: الاستيرادات")
    
    try:
        import aiogram
        print_test("aiogram", True, f"الإصدار: {aiogram.__version__}")
    except Exception as e:
        print_test("aiogram", False, str(e))
    
    try:
        import aiosqlite
        print_test("aiosqlite", True)
    except Exception as e:
        print_test("aiosqlite", False, str(e))
    
    try:
        import aiohttp
        print_test("aiohttp", True, f"الإصدار: {aiohttp.__version__}")
    except Exception as e:
        print_test("aiohttp", False, str(e))
    
    try:
        from dotenv import load_dotenv
        print_test("python-dotenv", True)
    except Exception as e:
        print_test("python-dotenv", False, str(e))


# ===== اختبار 2: الإعدادات =====
def test_settings():
    """اختبار ملف الإعدادات"""
    print_header("اختبار 2: الإعدادات")
    
    try:
        from config.settings import (
            BOT_TOKEN, DATABASE_PATH, OrderStatus, 
            ProductType, StoreMode, UserRole
        )
        print_test("استيراد الإعدادات", True)
        
        # التحقق من وجود BOT_TOKEN
        if BOT_TOKEN and len(BOT_TOKEN) > 10:
            print_test("BOT_TOKEN", True, "موجود وصالح")
        else:
            print_test("BOT_TOKEN", False, "غير موجود أو غير صالح")
        
        # التحقق من OrderStatus
        statuses = ["PENDING", "PROCESSING", "COMPLETED", "FAILED", "CANCELLED"]
        all_exist = all(hasattr(OrderStatus, s) for s in statuses)
        print_test("OrderStatus", all_exist, f"الحالات: {', '.join(statuses)}")
        
        # التحقق من ProductType
        types = ["MANUAL", "AUTO", "DISABLED"]
        all_exist = all(hasattr(ProductType, t) for t in types)
        print_test("ProductType", all_exist, f"الأنواع: {', '.join(types)}")
        
        # التحقق من StoreMode
        modes = ["MANUAL", "AUTO", "MAINTENANCE", "EMERGENCY"]
        all_exist = all(hasattr(StoreMode, m) for m in modes)
        print_test("StoreMode", all_exist, f"الأوضاع: {', '.join(modes)}")
        
        # التحقق من UserRole
        roles = ["USER", "SUPPORT", "OPERATOR", "SUPER_ADMIN"]
        all_exist = all(hasattr(UserRole, r) for r in roles)
        print_test("UserRole", all_exist, f"الرتب: {', '.join(roles)}")
        
    except Exception as e:
        print_test("استيراد الإعدادات", False, str(e))


# ===== اختبار 3: قاعدة البيانات =====
async def test_database():
    """اختبار مدير قاعدة البيانات"""
    print_header("اختبار 3: قاعدة البيانات")
    
    try:
        from database.manager import db_manager
        print_test("استيراد db_manager", True)
        
        # التحقق من وجود الدوال الأساسية
        functions = [
            "init_db", "get_user", "create_user", "update_user_balance",
            "get_product", "create_product", "update_product", "delete_product",
            "get_payment_method", "create_payment_method", "soft_delete_payment_method",
            "create_order", "get_order", "update_order_status",
            "get_setting", "set_setting", "log_admin_action"
        ]
        
        for func in functions:
            exists = hasattr(db_manager, func)
            print_test(f"دالة {func}", exists)
        
    except Exception as e:
        print_test("استيراد db_manager", False, str(e))


# ===== اختبار 4: الخدمات =====
def test_services():
    """اختبار طبقة الخدمات"""
    print_header("اختبار 4: الخدمات (Services Layer)")
    
    try:
        from services.order_service import OrderService
        print_test("OrderService", True)
        
        # التحقق من الدوال
        methods = ["validate_order", "create_order", "finalize_order", "get_order_summary"]
        for method in methods:
            exists = hasattr(OrderService, method)
            print_test(f"OrderService.{method}", exists)
        
    except Exception as e:
        print_test("OrderService", False, str(e))
    
    try:
        from services.permission_service import PermissionService
        print_test("PermissionService", True)
        
        # التحقق من الدوال
        methods = ["has_permission", "is_super_admin", "is_operator", "is_support", "can_manage_user"]
        for method in methods:
            exists = hasattr(PermissionService, method)
            print_test(f"PermissionService.{method}", exists)
        
    except Exception as e:
        print_test("PermissionService", False, str(e))
    
    try:
        from services.analytics_service import AnalyticsService
        print_test("AnalyticsService", True)
        
        # التحقق من الدوال
        methods = ["get_user_stats", "get_order_stats", "get_revenue_stats", "get_deposit_stats"]
        for method in methods:
            exists = hasattr(AnalyticsService, method)
            print_test(f"AnalyticsService.{method}", exists)
        
    except Exception as e:
        print_test("AnalyticsService", False, str(e))


# ===== اختبار 5: المعالجات =====
def test_handlers():
    """اختبار معالجات البوت"""
    print_header("اختبار 5: المعالجات (Handlers)")
    
    handlers_list = [
        "user", "admin", "products", "payments", 
        "admin_modes", "admin_orders", "admin_stats",
        "admin_broadcast", "admin_coupons", "admin_audit",
        "language"
    ]
    
    for handler_name in handlers_list:
        try:
            module = __import__(f"handlers.{handler_name}", fromlist=[handler_name])
            has_router = hasattr(module, "router")
            print_test(f"handlers.{handler_name}", has_router, "يحتوي على router" if has_router else "لا يحتوي على router")
        except Exception as e:
            print_test(f"handlers.{handler_name}", False, str(e))


# ===== اختبار 6: الميدلوير =====
def test_middlewares():
    """اختبار الميدلوير"""
    print_header("اختبار 6: الميدلوير (Middlewares)")
    
    try:
        from middlewares.auth import AuthMiddleware, AdminMiddleware
        print_test("AuthMiddleware", True)
        print_test("AdminMiddleware", True)
    except Exception as e:
        print_test("Middlewares", False, str(e))
    
    try:
        from middlewares.throttling import ThrottlingMiddleware
        print_test("ThrottlingMiddleware", True)
    except Exception as e:
        print_test("ThrottlingMiddleware", False, str(e))


# ===== اختبار 7: الأدوات المساعدة =====
def test_utils():
    """اختبار الأدوات المساعدة"""
    print_header("اختبار 7: الأدوات المساعدة (Utils)")
    
    utils_list = ["api_client", "helpers", "keyboards", "notifications", "translations"]
    
    for util_name in utils_list:
        try:
            __import__(f"utils.{util_name}", fromlist=[util_name])
            print_test(f"utils.{util_name}", True)
        except Exception as e:
            print_test(f"utils.{util_name}", False, str(e))


# ===== اختبار 8: الملف الرئيسي =====
def test_main():
    """اختبار الملف الرئيسي"""
    print_header("اختبار 8: الملف الرئيسي (main.py)")
    
    try:
        # قراءة محتوى main.py
        with open("main.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # التحقق من وجود المكونات الأساسية
        checks = {
            "health_server": "async def health_server" in content,
            "error_handler": "async def error_handler" in content,
            "shutdown": "async def shutdown" in content,
            "main": "async def main" in content,
            "Bot": "Bot(token=" in content,
            "Dispatcher": "Dispatcher(storage=" in content,
            "routers": "dp.include_router" in content,
            "middlewares": "dp.message.middleware" in content,
        }
        
        for check_name, result in checks.items():
            print_test(f"main.py - {check_name}", result)
        
    except Exception as e:
        print_test("main.py", False, str(e))


# ===== اختبار 9: بنية المشروع =====
def test_project_structure():
    """اختبار بنية المشروع"""
    print_header("اختبار 9: بنية المشروع")
    
    required_dirs = ["config", "database", "handlers", "services", "middlewares", "utils"]
    required_files = ["main.py", "requirements.txt", "Procfile", "runtime.txt"]
    
    for dir_name in required_dirs:
        exists = os.path.isdir(dir_name)
        print_test(f"مجلد {dir_name}", exists)
    
    for file_name in required_files:
        exists = os.path.isfile(file_name)
        print_test(f"ملف {file_name}", exists)


# ===== اختبار 10: الملفات الفارغة =====
def test_empty_files():
    """اختبار الملفات الفارغة أو غير المستخدمة"""
    print_header("اختبار 10: الملفات الفارغة")
    
    # فحص orders.py في الجذر
    if os.path.exists("orders.py"):
        size = os.path.getsize("orders.py")
        if size == 0:
            print_test("orders.py (جذر)", False, "⚠️ ملف فارغ - يجب حذفه")
        else:
            print_test("orders.py (جذر)", True, f"الحجم: {size} بايت")
    
    # فحص handlers/orders.py
    if os.path.exists("handlers/orders.py"):
        size = os.path.getsize("handlers/orders.py")
        if size <= 10:  # أقل من 10 بايت يعتبر فارغ
            print_test("handlers/orders.py", False, "⚠️ ملف فارغ - يجب حذفه أو ملؤه")
        else:
            print_test("handlers/orders.py", True, f"الحجم: {size} بايت")


# ===== الدالة الرئيسية =====
async def main():
    """تشغيل جميع الاختبارات"""
    print(f"\n{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}🚀 بدء الاختبار الشامل لمشروع Telegram Bot{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}")
    
    # تشغيل الاختبارات
    test_imports()
    test_settings()
    await test_database()
    test_services()
    test_handlers()
    test_middlewares()
    test_utils()
    test_main()
    test_project_structure()
    test_empty_files()
    
    # عرض النتائج النهائية
    print_header("النتائج النهائية")
    
    total = len(test_results)
    passed = sum(1 for v in test_results.values() if v)
    failed = total - passed
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"إجمالي الاختبارات: {total}")
    print(f"{GREEN}✅ نجح: {passed}{RESET}")
    print(f"{RED}❌ فشل: {failed}{RESET}")
    print(f"معدل النجاح: {success_rate:.1f}%\n")
    
    if failed == 0:
        print(f"{GREEN}🎉 جميع الاختبارات نجحت! المشروع في حالة ممتازة.{RESET}\n")
        return 0
    else:
        print(f"{YELLOW}⚠️ بعض الاختبارات فشلت. يرجى مراجعة التفاصيل أعلاه.{RESET}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
