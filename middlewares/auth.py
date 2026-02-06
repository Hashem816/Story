"""
Middleware للمصادقة والصلاحيات
تم تحسينه لضمان:
- توارث الصلاحيات بشكل صحيح (SUPER_ADMIN > OPERATOR > SUPPORT)
- تسجيل محاولات الوصول غير المصرح بها
- حماية الإجراءات الحساسة
"""

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from config.settings import ADMIN_ID, StoreMode, UserRole
from database.manager import db_manager
import logging

logger = logging.getLogger(__name__)

class AdminMiddleware(BaseMiddleware):
    """
    Middleware للتحقق من صلاحيات المستخدم
    يضيف المتغيرات التالية إلى data:
    - is_super_admin: True إذا كان المستخدم Super Admin
    - is_admin: نفس is_super_admin (للتوافق مع الكود القديم)
    - is_operator: True إذا كان المستخدم Operator أو أعلى
    - is_support: True إذا كان المستخدم Support أو أعلى
    - user_role: رتبة المستخدم الفعلية
    """
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        user = await db_manager.get_user(user_id)
        
        # تحديد الصلاحيات بشكل متدرج
        # SUPER_ADMIN يرث جميع الصلاحيات
        # OPERATOR يرث صلاحيات SUPPORT
        # SUPPORT لديه صلاحيات الدعم فقط
        
        is_super_admin = (user_id == ADMIN_ID) or (user and user['role'] == UserRole.SUPER_ADMIN)
        is_operator = is_super_admin or (user and user['role'] == UserRole.OPERATOR)
        is_support = is_operator or (user and user['role'] == UserRole.SUPPORT)
        
        # إضافة الصلاحيات إلى data
        data['is_super_admin'] = is_super_admin
        data['is_admin'] = is_super_admin  # للتوافق مع الكود القديم
        data['is_operator'] = is_operator
        data['is_support'] = is_support
        data['user_role'] = user['role'] if user else UserRole.USER
        
        # حماية Callback Queries الإدارية
        if isinstance(event, CallbackQuery):
            # التحقق من الوصول للوحة التحكم
            if event.data.startswith('admin_'):
                # الإجراءات التي تحتاج صلاحيات Support على الأقل
                if not is_support:
                    logger.warning(f"Unauthorized admin access attempt by user {user_id}: {event.data}")
                    await db_manager.log_admin_action(
                        admin_id=user_id,
                        action="UNAUTHORIZED_ACCESS_ATTEMPT",
                        details=f"Callback: {event.data}"
                    )
                    return await event.answer("⚠️ غير مصرح لك بهذا الإجراء.", show_alert=True)
                
                # الإجراءات التي تحتاج صلاحيات Operator
                operator_only = [
                    'admin_orders_', 'admin_order_', 'admin_products_',
                    'admin_categories_', 'admin_pay_approve', 'admin_pay_reject'
                ]
                if any(event.data.startswith(prefix) for prefix in operator_only) and not is_operator:
                    logger.warning(f"Operator action attempted by {user_id} (role: {data['user_role']}): {event.data}")
                    await db_manager.log_admin_action(
                        admin_id=user_id,
                        action="UNAUTHORIZED_OPERATOR_ACTION",
                        details=f"Callback: {event.data}"
                    )
                    return await event.answer("⚠️ هذا الإجراء متاح للمشغلين فقط.", show_alert=True)
                
                # الإجراءات التي تحتاج صلاحيات Super Admin فقط
                super_only = [
                    'admin_set_mode_', 'admin_toggle_emergency', 'admin_set_rate',
                    'admin_users_manage', 'admin_user_setrole_', 'admin_user_block_',
                    'admin_user_unblock_', 'admin_coupons', 'admin_coupon_',
                    'admin_broadcast', 'admin_support_msg', 'admin_balance_'
                ]
                if any(event.data.startswith(prefix) for prefix in super_only) and not is_super_admin:
                    logger.warning(f"Super admin action attempted by {user_id} (role: {data['user_role']}): {event.data}")
                    await db_manager.log_admin_action(
                        admin_id=user_id,
                        action="UNAUTHORIZED_SUPER_ADMIN_ACTION",
                        details=f"Callback: {event.data}"
                    )
                    return await event.answer("⚠️ هذا الإجراء متاح لمدير النظام فقط.", show_alert=True)
        
        return await handler(event, data)


class AuthMiddleware(BaseMiddleware):
    """
    Middleware للمصادقة العامة
    يتحقق من:
    - وجود المستخدم في قاعدة البيانات
    - حالة الحظر
    - وضع الطوارئ والصيانة
    - اختيار اللغة (للمستخدمين الجدد)
    """
    
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        user_id = event.from_user.id
        
        # التحقق من وجود المستخدم أو إنشاؤه
        user = await db_manager.get_user(user_id)
        if not user:
            role = UserRole.SUPER_ADMIN if user_id == ADMIN_ID else UserRole.USER
            first_name = event.from_user.first_name if hasattr(event.from_user, 'first_name') else None
            last_name = event.from_user.last_name if hasattr(event.from_user, 'last_name') else None
            
            # إنشاء المستخدم بدون لغة افتراضية لإجباره على الاختيار
            await db_manager.create_user(
                user_id,
                event.from_user.username or "Unknown",
                first_name=first_name,
                last_name=last_name,
                role=role,
                language=None  # لإجبار اختيار اللغة
            )
            user = await db_manager.get_user(user_id)
        
        # التحقق من اختيار اللغة (للمستخدمين الجدد)
        # السماح فقط بأوامر /start واختيار اللغة
        if not user.get('language'):
            if isinstance(event, Message):
                if not event.text or not event.text.startswith('/start'):
                    return await event.answer("🌐 يرجى اختيار اللغة أولاً / Please select language first")
            elif isinstance(event, CallbackQuery):
                if not event.data.startswith('lang_'):
                    return await event.answer("🌐 يرجى اختيار اللغة أولاً / Please select language first", show_alert=True)
        
        # التحقق من الطاقم الإداري
        is_admin_staff = user['role'] in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]
        
        # التحقق من إيقاف الطوارئ ووضع الصيانة (لغير الطاقم الإداري)
        if not is_admin_staff:
            emergency = await db_manager.get_setting("emergency_stop", "0")
            store_mode = await db_manager.get_setting("store_mode", StoreMode.MANUAL)
            
            if emergency == "1":
                msg = "🚨 عذراً، المتجر متوقف حالياً لحالة طوارئ. سنعود قريباً."
                if isinstance(event, Message):
                    return await event.answer(msg)
                return await event.answer(msg, show_alert=True)
                
            if store_mode == StoreMode.MAINTENANCE:
                m_msg = await db_manager.get_setting("maintenance_message", "🛠 المتجر في وضع الصيانة.")
                if isinstance(event, Message):
                    return await event.answer(m_msg)
                return await event.answer(m_msg, show_alert=True)
        
        # التحقق من الحظر
        if user['is_blocked']:
            msg = "🚫 حسابك محظور. للاستفسار تواصل مع الدعم."
            if isinstance(event, Message):
                return await event.answer(msg)
            return await event.answer(msg, show_alert=True)
        
        # إضافة بيانات المستخدم إلى data
        data['user'] = user
        
        return await handler(event, data)
