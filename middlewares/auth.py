from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from config.settings import ADMIN_ID, StoreMode, UserRole
from database.manager import db_manager

class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        user = await db_manager.get_user(user_id)
        
        # Super Admin هو المعرف في ملف .env أو من له رتبة SUPER_ADMIN
        is_super_admin = (user_id == ADMIN_ID) or (user and user['role'] == UserRole.SUPER_ADMIN)
        is_operator = user and user['role'] in [UserRole.SUPER_ADMIN, UserRole.OPERATOR]
        is_support = user and user['role'] in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]
        
        data['is_admin'] = is_super_admin
        data['is_operator'] = is_operator
        data['is_support'] = is_support
        data['user_role'] = user['role'] if user else UserRole.USER
        
        if isinstance(event, CallbackQuery):
            if event.data.startswith('admin_') and not is_support:
                return await event.answer("⚠️ غير مصرح لك بهذا الإجراء.", show_alert=True)
            
            # حماية إجراءات معينة للـ Super Admin فقط
            super_only = ['admin_set_mode_', 'admin_toggle_emergency', 'admin_set_rate', 'admin_users']
            if any(event.data.startswith(prefix) for prefix in super_only) and not is_super_admin:
                return await event.answer("⚠️ هذا الإجراء متاح لمدير النظام فقط.", show_alert=True)
        
        return await handler(event, data)

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        
        # التحقق من وجود المستخدم أو إنشاؤه
        user = await db_manager.get_user(user_id)
        if not user:
            role = UserRole.SUPER_ADMIN if user_id == ADMIN_ID else UserRole.USER
            await db_manager.create_user(user_id, event.from_user.username or "Unknown", role=role)
            user = await db_manager.get_user(user_id)
            
        is_admin_staff = user['role'] in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]
        
        # التحقق من إيقاف الطوارئ ووضع الصيانة (لغير الطاقم الإداري)
        if not is_admin_staff:
            emergency = await db_manager.get_setting("emergency_stop", "0")
            store_mode = await db_manager.get_setting("store_mode", StoreMode.MANUAL)
            
            if emergency == "1":
                msg = "🚨 عذراً، المتجر متوقف حالياً لحالة طوارئ. سنعود قريباً."
                if isinstance(event, Message): return await event.answer(msg)
                return await event.answer(msg, show_alert=True)
                
            if store_mode == StoreMode.MAINTENANCE:
                m_msg = await db_manager.get_setting("maintenance_message", "🛠 المتجر في وضع الصيانة.")
                if isinstance(event, Message): return await event.answer(m_msg)
                return await event.answer(m_msg, show_alert=True)

        if user['is_blocked']:
            msg = "🚫 حسابك محظور."
            if isinstance(event, Message): return await event.answer(msg)
            return await event.answer(msg, show_alert=True)
            
        data['user'] = user
        return await handler(event, data)
