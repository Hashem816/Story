"""
Permission Service - نظام الصلاحيات المحسّن
التحسينات:
- SUPER_ADMIN يرث كل الصلاحيات
- OPERATOR يرث SUPPORT
- SUPPORT يرث USER
- دوال مركزية للتحقق من الصلاحيات
"""

from typing import Dict, Any
from config.settings import UserRole
import logging

logger = logging.getLogger(__name__)


class PermissionService:
    """خدمة إدارة الصلاحيات"""
    
    # تعريف الصلاحيات لكل رتبة
    PERMISSIONS = {
        UserRole.SUPER_ADMIN: {
            'manage_products': True,
            'manage_payment_methods': True,
            'manage_orders': True,
            'manage_users': True,
            'manage_coupons': True,
            'view_stats': True,
            'broadcast': True,
            'manage_settings': True,
            'view_audit_logs': True,
            'manage_roles': True,
            'emergency_stop': True
        },
        UserRole.OPERATOR: {
            'manage_products': True,
            'manage_payment_methods': True,
            'manage_orders': True,
            'manage_users': False,
            'manage_coupons': False,
            'view_stats': True,
            'broadcast': False,
            'manage_settings': False,
            'view_audit_logs': False,
            'manage_roles': False,
            'emergency_stop': False
        },
        UserRole.SUPPORT: {
            'manage_products': False,
            'manage_payment_methods': False,
            'manage_orders': True,
            'manage_users': False,
            'manage_coupons': False,
            'view_stats': False,
            'broadcast': False,
            'manage_settings': False,
            'view_audit_logs': False,
            'manage_roles': False,
            'emergency_stop': False
        },
        UserRole.USER: {
            'manage_products': False,
            'manage_payment_methods': False,
            'manage_orders': False,
            'manage_users': False,
            'manage_coupons': False,
            'view_stats': False,
            'broadcast': False,
            'manage_settings': False,
            'view_audit_logs': False,
            'manage_roles': False,
            'emergency_stop': False
        }
    }
    
    @staticmethod
    def has_permission(user_role: str, permission: str) -> bool:
        """
        التحقق من صلاحية معينة
        
        Args:
            user_role: رتبة المستخدم
            permission: اسم الصلاحية
            
        Returns:
            bool: True إذا كان لديه الصلاحية
        """
        if user_role not in PermissionService.PERMISSIONS:
            logger.warning(f"Unknown role: {user_role}")
            return False
        
        return PermissionService.PERMISSIONS[user_role].get(permission, False)
    
    @staticmethod
    def is_super_admin(user_role: str) -> bool:
        """التحقق من أن المستخدم Super Admin"""
        return user_role == UserRole.SUPER_ADMIN
    
    @staticmethod
    def is_operator(user_role: str) -> bool:
        """التحقق من أن المستخدم Operator أو أعلى"""
        return user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR]
    
    @staticmethod
    def is_support(user_role: str) -> bool:
        """التحقق من أن المستخدم Support أو أعلى"""
        return user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]
    
    @staticmethod
    def is_staff(user_role: str) -> bool:
        """التحقق من أن المستخدم من الطاقم الإداري"""
        return user_role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT]
    
    @staticmethod
    def get_all_permissions(user_role: str) -> Dict[str, bool]:
        """الحصول على جميع صلاحيات رتبة معينة"""
        return PermissionService.PERMISSIONS.get(user_role, PermissionService.PERMISSIONS[UserRole.USER])
    
    @staticmethod
    def can_manage_user(admin_role: str, target_role: str) -> bool:
        """
        التحقق من إمكانية إدارة مستخدم معين
        القاعدة: لا يمكن إدارة مستخدم برتبة أعلى أو مساوية
        """
        role_hierarchy = {
            UserRole.USER: 0,
            UserRole.SUPPORT: 1,
            UserRole.OPERATOR: 2,
            UserRole.SUPER_ADMIN: 3
        }
        
        admin_level = role_hierarchy.get(admin_role, 0)
        target_level = role_hierarchy.get(target_role, 0)
        
        return admin_level > target_level


# إنشاء instance واحد
permission_service = PermissionService()
