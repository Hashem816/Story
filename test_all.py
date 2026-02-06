"""
اختبار شامل لجميع المكونات
"""
import sys
sys.path.insert(0, '.')

def test_imports():
    """اختبار الاستيرادات"""
    print("🔍 اختبار الاستيرادات...")
    try:
        from database import manager, models
        from services import order_service, permission_service, analytics_service
        from config import settings
        from utils import keyboards, translations
        print("✅ جميع الاستيرادات ناجحة")
        return True
    except Exception as e:
        print(f"❌ فشل الاستيراد: {e}")
        return False

def test_services():
    """اختبار الخدمات"""
    print("\n🔍 اختبار الخدمات...")
    try:
        from services.order_service import order_service
        from services.permission_service import permission_service
        from services.analytics_service import analytics_service
        
        # اختبار Permission Service
        assert permission_service.is_super_admin('SUPER_ADMIN') == True
        assert permission_service.is_operator('OPERATOR') == True
        assert permission_service.is_support('SUPPORT') == True
        assert permission_service.has_permission('SUPER_ADMIN', 'manage_products') == True
        assert permission_service.has_permission('USER', 'manage_products') == False
        
        print("✅ جميع الخدمات تعمل بشكل صحيح")
        return True
    except Exception as e:
        print(f"❌ فشل اختبار الخدمات: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config():
    """اختبار الإعدادات"""
    print("\n🔍 اختبار الإعدادات...")
    try:
        from config.settings import UserRole, OrderStatus, ProductType, StoreMode
        
        assert hasattr(UserRole, 'SUPER_ADMIN')
        assert hasattr(OrderStatus, 'COMPLETED')
        assert hasattr(ProductType, 'MANUAL')
        assert hasattr(StoreMode, 'MAINTENANCE')
        
        print("✅ جميع الإعدادات موجودة")
        return True
    except Exception as e:
        print(f"❌ فشل اختبار الإعدادات: {e}")
        return False

def test_handlers():
    """اختبار المعالجات"""
    print("\n🔍 اختبار المعالجات...")
    try:
        from handlers import products, payments, user, admin_stats
        
        # التحقق من وجود الـ routers
        assert hasattr(products, 'router')
        assert hasattr(payments, 'router')
        assert hasattr(user, 'router')
        assert hasattr(admin_stats, 'router')
        
        print("✅ جميع المعالجات موجودة")
        return True
    except Exception as e:
        print(f"❌ فشل اختبار المعالجات: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """تشغيل جميع الاختبارات"""
    print("=" * 50)
    print("🚀 بدء الاختبار الشامل")
    print("=" * 50)
    
    results = []
    results.append(("الاستيرادات", test_imports()))
    results.append(("الخدمات", test_services()))
    results.append(("الإعدادات", test_config()))
    results.append(("المعالجات", test_handlers()))
    
    print("\n" + "=" * 50)
    print("📊 نتائج الاختبار")
    print("=" * 50)
    
    for name, result in results:
        status = "✅ نجح" if result else "❌ فشل"
        print(f"{name}: {status}")
    
    all_passed = all(r[1] for r in results)
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 جميع الاختبارات نجحت!")
    else:
        print("⚠️ بعض الاختبارات فشلت")
    print("=" * 50)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
