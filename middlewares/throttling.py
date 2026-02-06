"""
Middleware للتحكم بمعدل الطلبات (Rate Limiting)
تم تحسينه لـ:
- Rate limiting لكل مستخدم بشكل منفصل
- تتبع أنواع مختلفة من الإجراءات
- منع محاولات الإغراق (Flood)
"""

import time
import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from config.settings import UserRole

logger = logging.getLogger(__name__)

class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware للتحكم بمعدل الطلبات
    يمنع المستخدمين من إرسال رسائل متكررة بسرعة
    """
    
    def __init__(self, slow_mode_delay: float = 0.5, flood_threshold: int = 10):
        """
        Args:
            slow_mode_delay: الحد الأدنى للوقت بين الرسائل (بالثواني)
            flood_threshold: عدد الرسائل المسموح بها في دقيقة واحدة
        """
        self.slow_mode_delay = slow_mode_delay
        self.flood_threshold = flood_threshold
        
        # تتبع آخر رسالة لكل مستخدم
        self.user_last_message_time: Dict[int, float] = {}
        
        # تتبع عدد الرسائل في الدقيقة الأخيرة
        self.user_message_count: Dict[int, list] = {}
        
        # تتبع المستخدمين المحظورين مؤقتاً
        self.temp_blocked: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        # تطبيق Rate Limiting فقط على الرسائل
        if not isinstance(event, Message):
            return await handler(event, data)
        
        user_id = event.from_user.id
        current_time = time.time()
        
        # استثناء الطاقم الإداري من Rate Limiting
        user_role = data.get('user_role', UserRole.USER)
        if user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]:
            return await handler(event, data)
        
        # التحقق من الحظر المؤقت
        if user_id in self.temp_blocked:
            block_until = self.temp_blocked[user_id]
            if current_time < block_until:
                remaining = int(block_until - current_time)
                logger.warning(f"User {user_id} is temporarily blocked for {remaining}s")
                return await event.answer(
                    f"⚠️ تم حظرك مؤقتاً لمدة {remaining} ثانية بسبب إرسال رسائل متكررة بسرعة."
                )
            else:
                # انتهى الحظر المؤقت
                del self.temp_blocked[user_id]
                self.user_message_count[user_id] = []
        
        # التحقق من Slow Mode
        last_time = self.user_last_message_time.get(user_id, 0)
        if current_time - last_time < self.slow_mode_delay:
            logger.debug(f"User {user_id} throttled (slow mode)")
            return  # تجاهل الرسالة بصمت
        
        # التحقق من Flood Protection
        if user_id not in self.user_message_count:
            self.user_message_count[user_id] = []
        
        # تنظيف الرسائل القديمة (أكثر من دقيقة)
        self.user_message_count[user_id] = [
            msg_time for msg_time in self.user_message_count[user_id]
            if current_time - msg_time < 60
        ]
        
        # إضافة الرسالة الحالية
        self.user_message_count[user_id].append(current_time)
        
        # التحقق من تجاوز الحد
        if len(self.user_message_count[user_id]) > self.flood_threshold:
            # حظر مؤقت لمدة 30 ثانية
            self.temp_blocked[user_id] = current_time + 30
            logger.warning(f"User {user_id} temporarily blocked for flooding ({len(self.user_message_count[user_id])} messages/min)")
            
            # تسجيل في قاعدة البيانات
            from database.manager import db_manager
            await db_manager.log_admin_action(
                admin_id=user_id,
                action="FLOOD_DETECTED",
                details=f"Sent {len(self.user_message_count[user_id])} messages in 1 minute"
            )
            
            return await event.answer(
                "⚠️ تم اكتشاف إرسال رسائل متكررة بسرعة.\n"
                "تم حظرك مؤقتاً لمدة 30 ثانية."
            )
        
        # تحديث آخر وقت رسالة
        self.user_last_message_time[user_id] = current_time
        
        return await handler(event, data)
    
    def cleanup_old_data(self):
        """تنظيف البيانات القديمة لتوفير الذاكرة"""
        current_time = time.time()
        
        # تنظيف الحظر المؤقت المنتهي
        expired_blocks = [
            user_id for user_id, block_until in self.temp_blocked.items()
            if current_time >= block_until
        ]
        for user_id in expired_blocks:
            del self.temp_blocked[user_id]
        
        # تنظيف عدادات الرسائل القديمة
        for user_id in list(self.user_message_count.keys()):
            self.user_message_count[user_id] = [
                msg_time for msg_time in self.user_message_count[user_id]
                if current_time - msg_time < 60
            ]
            if not self.user_message_count[user_id]:
                del self.user_message_count[user_id]
