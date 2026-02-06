from aiogram.types import KeyboardButton, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from config.settings import UserRole

from utils.translations import get_text

def get_main_menu(user_role: str = UserRole.USER, lang: str = "ar"):
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text=get_text("btn_store", lang)), 
        KeyboardButton(text=get_text("btn_account", lang))
    )
    builder.row(
        KeyboardButton(text=get_text("btn_orders", lang)), 
        KeyboardButton(text=get_text("btn_balance", lang))
    )
    builder.row(
        KeyboardButton(text=get_text("btn_support", lang)),
        KeyboardButton(text="🌐 Language / اللغة")
    )
    
    # التحقق من الرتبة لظهور لوحة التحكم
    is_staff = user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]
    if is_staff:
        builder.row(KeyboardButton(text=get_text("btn_admin_panel", lang)))
        
    return builder.as_markup(resize_keyboard=True)

def get_admin_main_menu(user_role: str, lang: str = "ar"):
    builder = InlineKeyboardBuilder()
    
    # الطلبات (الكل)
    builder.row(InlineKeyboardButton(text=get_text("admin_orders", lang), callback_data="admin_orders"))
    
    # إدارة المنتجات والدفع (Operator + Super Admin)
    if user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR]:
        builder.row(InlineKeyboardButton(text=get_text("admin_products", lang), callback_data="admin_products"))
        builder.row(InlineKeyboardButton(text="💳 طرق الدفع", callback_data="admin_payment_methods"))
    
    # الإعدادات المتقدمة (Super Admin فقط)
    if user_role == UserRole.SUPER_ADMIN:
        builder.row(InlineKeyboardButton(text="🔌 وضع التشغيل", callback_data="admin_store_status"))
        builder.row(InlineKeyboardButton(text="💵 سعر الدولار", callback_data="admin_dollar_settings"))
        builder.row(InlineKeyboardButton(text=get_text("admin_users", lang), callback_data="admin_users_manage"))
        builder.row(InlineKeyboardButton(text=get_text("admin_coupons", lang), callback_data="admin_coupons"))
        builder.row(InlineKeyboardButton(text=get_text("admin_stats", lang), callback_data="admin_stats"))
        builder.row(InlineKeyboardButton(text=get_text("admin_broadcast", lang), callback_data="admin_broadcast"))
        builder.row(InlineKeyboardButton(text="📋 سجل العمليات", callback_data="admin_audit_logs"))
        builder.row(InlineKeyboardButton(text="❓ إعداد رسالة الدعم", callback_data="admin_support_msg"))
        
    return builder.as_markup()

def get_categories_keyboard(categories, is_admin=False):
    builder = InlineKeyboardBuilder()
    prefix = "admin_cat_view_" if is_admin else "cat_"
    for cat in categories:
        builder.row(InlineKeyboardButton(text=cat['name'], callback_data=f"{prefix}{cat['id']}"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="➕ إضافة قسم", callback_data="admin_cat_add"))
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="admin_main"))
    return builder.as_markup()

def get_products_keyboard(products, category_id, dollar_rate, is_admin=False):
    builder = InlineKeyboardBuilder()
    prefix = "admin_prod_view_" if is_admin else "prod_"
    for prod in products:
        local_price = prod['price_usd'] * dollar_rate
        builder.row(InlineKeyboardButton(text=f"{prod['name']} - {local_price:,.0f} ل.س", callback_data=f"{prefix}{prod['id']}"))
    
    if is_admin:
        builder.row(InlineKeyboardButton(text="➕ إضافة منتج", callback_data=f"admin_prod_add_{category_id}"))
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="admin_products"))
    else:
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="back_to_categories"))
    return builder.as_markup()

def get_payment_methods_keyboard(methods, is_admin=False):
    builder = InlineKeyboardBuilder()
    prefix = "admin_view_pay_" if is_admin else "pay_method_"
    for method in methods:
        status = "✅" if method.get('is_active', 1) else "❌"
        text = f"{status} {method['name']}" if is_admin else method['name']
        builder.row(InlineKeyboardButton(text=text, callback_data=f"{prefix}{method['id']}"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="➕ إضافة طريقة", callback_data="admin_add_pay_start"))
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="admin_main"))
    return builder.as_markup()

def get_admin_order_actions(order_id: int, status: str):
    builder = InlineKeyboardBuilder()
    if status == "PAID":
        builder.row(InlineKeyboardButton(text="✅ تأكيد الدفع", callback_data=f"aord_approve_pay_{order_id}"))
        builder.row(InlineKeyboardButton(text="❌ رفض الإيصال", callback_data=f"aord_reject_pay_{order_id}"))
    elif status == "IN_PROGRESS":
        builder.row(InlineKeyboardButton(text="✅ إكمال التنفيذ", callback_data=f"aord_complete_{order_id}"))
    elif status == "PENDING_REVIEW":
        builder.row(InlineKeyboardButton(text="👍 موافقة على الطلب", callback_data=f"aord_approve_order_{order_id}"))
    
    builder.row(InlineKeyboardButton(text="❌ إلغاء الطلب", callback_data=f"aord_cancel_{order_id}"))
    builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="admin_orders"))
    return builder.as_markup()

def get_order_confirm_keyboard(product_id, lang: str = "ar"):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=get_text("btn_confirm_buy", lang) if "btn_confirm_buy" in TRANSLATIONS else "✅ تأكيد الشراء", callback_data=f"confirm_buy_{product_id}"),
        InlineKeyboardButton(text=get_text("btn_use_coupon", lang) if "btn_use_coupon" in TRANSLATIONS else "🎟️ استخدام كوبون", callback_data=f"use_coupon_{product_id}")
    )
    builder.row(
        InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="back_to_categories")
    )
    return builder.as_markup()
