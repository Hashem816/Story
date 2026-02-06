"""
معالج الإحصائيات - محسّن
التحسينات:
- استخدام Analytics Service
- عرض إحصائيات شاملة ومفصلة
"""

from aiogram import Router, F, types
from database.manager import db_manager
from services.analytics_service import analytics_service
import logging

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery, is_admin: bool):
    """عرض الإحصائيات الشاملة"""
    if not is_admin:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    try:
        # جلب الإحصائيات من Analytics Service
        stats = await analytics_service.get_dashboard_stats()
        
        if not stats:
            await callback.answer("❌ فشل جلب الإحصائيات", show_alert=True)
            return
        
        text = (
            f"📊 *إحصائيات المتجر الشاملة*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 *المستخدمون*\n"
            f"• إجمالي المستخدمين: `{stats.get('total_users', 0)}`\n"
            f"• مستخدمون جدد اليوم: `{stats.get('new_users_today', 0)}`\n"
            f"• مستخدمون جدد هذا الأسبوع: `{stats.get('new_users_week', 0)}`\n"
            f"• محظورون: `{stats.get('blocked_users', 0)}`\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *الطلبات*\n"
            f"• إجمالي الطلبات: `{stats.get('total_orders', 0)}`\n"
            f"• طلبات اليوم: `{stats.get('orders_today', 0)}`\n"
            f"• طلبات الأسبوع: `{stats.get('orders_week', 0)}`\n"
            f"• مكتملة: `{stats.get('completed_orders', 0)}`\n"
            f"• فاشلة: `{stats.get('failed_orders', 0)}`\n"
            f"• قيد التنفيذ: `{stats.get('pending_orders', 0)}`\n"
            f"• معدل النجاح: `{stats.get('success_rate', 0):.1f}%`\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 *الإيرادات*\n"
            f"• إجمالي الإيرادات: `{stats.get('total_revenue', 0):.2f}$`\n"
            f"• إيرادات اليوم: `{stats.get('revenue_today', 0):.2f}$`\n"
            f"• إيرادات الأسبوع: `{stats.get('revenue_week', 0):.2f}$`\n"
            f"• إيرادات الشهر: `{stats.get('revenue_month', 0):.2f}$`\n"
            f"• متوسط قيمة الطلب: `{stats.get('avg_order_value', 0):.2f}$`\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 *الشحن*\n"
            f"• إجمالي عمليات الشحن: `{stats.get('total_deposits', 0)}`\n"
            f"• إجمالي المبالغ المشحونة: `{stats.get('total_deposit_amount', 0):.2f}$`\n"
            f"• شحن اليوم: `{stats.get('deposits_today', 0):.2f}$`\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💵 *الأرصدة*\n"
            f"• إجمالي أرصدة المستخدمين: `{stats.get('total_balance', 0):.2f}$`\n\n"
            
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚙️ *نوع التنفيذ*\n"
            f"• يدوي: `{stats.get('manual_orders', 0)}`\n"
            f"• تلقائي: `{stats.get('auto_orders', 0)}`\n\n"
            
            f"📅 تم التحديث الآن"
        )
        
        builder = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="📈 تفاصيل إضافية", callback_data="admin_stats_details")],
            [types.InlineKeyboardButton(text="🔄 تحديث", callback_data="admin_stats")],
            [types.InlineKeyboardButton(text="🔙 عودة للرئيسية", callback_data="admin_main")]
        ])
        
        await callback.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")
        
        # تسجيل العملية
        await db_manager.log_admin_action(
            admin_id=callback.from_user.id,
            action="VIEW_STATS",
            target_type="SYSTEM"
        )
        
    except Exception as e:
        logger.error(f"Error showing stats: {e}", exc_info=True)
        await callback.answer("❌ حدث خطأ أثناء جلب الإحصائيات", show_alert=True)


@router.callback_query(F.data == "admin_stats_details")
async def show_stats_details(callback: types.CallbackQuery, is_admin: bool):
    """عرض تفاصيل إضافية للإحصائيات"""
    if not is_admin:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    try:
        # أكثر المنتجات مبيعاً
        top_products = await analytics_service.get_top_products(limit=5)
        
        # إحصائيات حسب الحالة
        orders_by_status = await analytics_service.get_orders_by_status()
        
        # نشاط المستخدمين
        user_activity = await analytics_service.get_user_activity()
        
        text = (
            f"📈 *تفاصيل الإحصائيات*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🏆 *أكثر المنتجات مبيعاً*\n"
        )
        
        if top_products:
            for i, product in enumerate(top_products, 1):
                text += f"{i}. {product['name']}: `{product['order_count']}` طلب (`{product['total_revenue']:.2f}$`)\n"
        else:
            text += "لا توجد بيانات\n"
        
        text += (
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"📊 *الطلبات حسب الحالة*\n"
        )
        
        if orders_by_status:
            for status, count in orders_by_status.items():
                text += f"• {status}: `{count}`\n"
        else:
            text += "لا توجد بيانات\n"
        
        text += (
            f"\n━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 *نشاط المستخدمين*\n"
            f"• مستخدمون نشطون (30 يوم): `{user_activity.get('active_users_month', 0)}`\n"
            f"• متوسط الطلبات لكل مستخدم: `{user_activity.get('avg_orders_per_user', 0)}`\n"
        )
        
        builder = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🔙 عودة للإحصائيات", callback_data="admin_stats")]
        ])
        
        await callback.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error showing stats details: {e}", exc_info=True)
        await callback.answer("❌ حدث خطأ أثناء جلب التفاصيل", show_alert=True)
