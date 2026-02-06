# نظام الإشعارات الموحد
import logging
from typing import Optional, List
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from config.settings import ADMIN_ID

logger = logging.getLogger(__name__)

class NotificationManager:
    """مدير الإشعارات المركزي"""
    
    @staticmethod
    async def notify_user(bot: Bot, user_id: int, message: str, parse_mode: str = "Markdown", reply_markup=None) -> bool:
        """
        إرسال إشعار لمستخدم
        
        Args:
            bot: كائن البوت
            user_id: معرف المستخدم
            message: نص الرسالة
            parse_mode: نمط التنسيق
            reply_markup: لوحة المفاتيح
        
        Returns:
            True إذا تم الإرسال بنجاح، False إذا فشل
        """
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            logger.info(f"Notification sent to user {user_id}")
            return True
        except TelegramForbiddenError:
            logger.warning(f"User {user_id} blocked the bot")
            return False
        except TelegramBadRequest as e:
            logger.error(f"Bad request when sending to {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send notification to {user_id}: {e}")
            return False
    
    @staticmethod
    async def notify_admins(bot: Bot, admin_ids: List[int], message: str, parse_mode: str = "Markdown") -> int:
        """
        إرسال إشعار لجميع الأدمن
        
        Args:
            bot: كائن البوت
            admin_ids: قائمة معرفات الأدمن
            message: نص الرسالة
            parse_mode: نمط التنسيق
        
        Returns:
            عدد الأدمن الذين تم إرسال الإشعار لهم بنجاح
        """
        success_count = 0
        for admin_id in admin_ids:
            if await NotificationManager.notify_user(bot, admin_id, message, parse_mode):
                success_count += 1
        return success_count
    
    @staticmethod
    async def notify_order_created(bot: Bot, admin_ids: List[int], order_id: int, user_id: int, username: str, product_name: str):
        """إشعار بإنشاء طلب جديد"""
        message = (
            f"🆕 *طلب جديد #{order_id}*\n\n"
            f"👤 المستخدم: @{username} (`{user_id}`)\n"
            f"📦 المنتج: {product_name}\n"
            f"⏰ الوقت: الآن"
        )
        await NotificationManager.notify_admins(bot, admin_ids, message)
    
    @staticmethod
    async def notify_order_status_change(bot: Bot, user_id: int, order_id: int, status: str, details: str = None):
        """إشعار بتغيير حالة الطلب"""
        status_messages = {
            "PAID": "✅ تم تأكيد الدفع",
            "IN_PROGRESS": "⏳ جاري تنفيذ طلبك",
            "COMPLETED": "✅ تم إكمال طلبك بنجاح",
            "FAILED": "❌ فشل تنفيذ الطلب",
            "CANCELED": "❌ تم إلغاء الطلب"
        }
        
        message = f"📦 *الطلب #{order_id}*\n\n{status_messages.get(status, status)}"
        if details:
            message += f"\n\n📝 {details}"
        
        await NotificationManager.notify_user(bot, user_id, message)
    
    @staticmethod
    async def notify_balance_change(bot: Bot, user_id: int, amount: float, new_balance: float, reason: str):
        """إشعار بتغيير الرصيد"""
        sign = "+" if amount > 0 else ""
        message = (
            f"💰 *تحديث الرصيد*\n\n"
            f"المبلغ: `{sign}{amount:.2f}$`\n"
            f"الرصيد الجديد: `{new_balance:.2f}$`\n"
            f"السبب: {reason}"
        )
        await NotificationManager.notify_user(bot, user_id, message)
    
    @staticmethod
    async def notify_error(bot: Bot, admin_id: int, error_type: str, details: str):
        """إشعار بخطأ في النظام"""
        message = (
            f"⚠️ *خطأ في النظام*\n\n"
            f"النوع: `{error_type}`\n"
            f"التفاصيل: {details}\n"
            f"⏰ الوقت: الآن"
        )
        await NotificationManager.notify_user(bot, admin_id, message)
    
    @staticmethod
    async def notify_new_user(bot: Bot, admin_ids: List[int], user_id: int, username: str):
        """إشعار بمستخدم جديد"""
        message = (
            f"🆕 *مستخدم جديد*\n\n"
            f"👤 @{username}\n"
            f"🆔 ID: `{user_id}`\n"
            f"⏰ الآن"
        )
        await NotificationManager.notify_admins(bot, admin_ids, message)
    
    @staticmethod
    async def notify_suspicious_activity(bot: Bot, admin_ids: List[int], user_id: int, activity: str):
        """إشعار بنشاط مشبوه"""
        message = (
            f"🚨 *نشاط مشبوه*\n\n"
            f"👤 المستخدم: `{user_id}`\n"
            f"النشاط: {activity}\n"
            f"⏰ الآن"
        )
        await NotificationManager.notify_admins(bot, admin_ids, message)

# إنشاء instance عام
notification_manager = NotificationManager()
