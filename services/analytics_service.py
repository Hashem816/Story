"""
Analytics Service - نظام الإحصائيات المحسّن
التحسينات:
- إحصائيات شاملة للطلبات والإيرادات
- إحصائيات المستخدمين وعمليات الشحن
- تقارير زمنية (يومية، أسبوعية، شهرية)
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from database.manager import db_manager
from config.settings import OrderStatus
import logging

logger = logging.getLogger(__name__)


class AnalyticsService:
    """خدمة الإحصائيات والتحليلات"""
    
    @staticmethod
    async def get_dashboard_stats() -> Dict[str, Any]:
        """
        إحصائيات لوحة التحكم الرئيسية
        
        Returns:
            dict مع جميع الإحصائيات الأساسية
        """
        try:
            db = await db_manager.connect()
            stats = {}
            
            # === إحصائيات المستخدمين ===
            cursor = await db.execute("SELECT COUNT(*) as count FROM users")
            stats['total_users'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM users WHERE is_blocked = 1")
            stats['blocked_users'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM users WHERE date(created_at) = date('now')")
            stats['new_users_today'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM users WHERE date(created_at) >= date('now', '-7 days')")
            stats['new_users_week'] = (await cursor.fetchone())['count']
            
            # === إحصائيات الطلبات ===
            cursor = await db.execute("SELECT COUNT(*) as count FROM orders")
            stats['total_orders'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE date(created_at) = date('now')")
            stats['orders_today'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE date(created_at) >= date('now', '-7 days')")
            stats['orders_week'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE status = ?", (OrderStatus.COMPLETED,))
            stats['completed_orders'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE status = ?", (OrderStatus.FAILED,))
            stats['failed_orders'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE status = ?", (OrderStatus.IN_PROGRESS,))
            stats['pending_orders'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE execution_type = 'MANUAL'")
            stats['manual_orders'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE execution_type = 'AUTO'")
            stats['auto_orders'] = (await cursor.fetchone())['count']
            
            # === الإحصائيات المالية ===
            cursor = await db.execute("SELECT COALESCE(SUM(balance), 0) as total FROM users")
            stats['total_balance'] = (await cursor.fetchone())['total']
            
            cursor = await db.execute("""
                SELECT COALESCE(SUM(price_usd), 0) as revenue 
                FROM orders 
                WHERE status = ?
            """, (OrderStatus.COMPLETED,))
            stats['total_revenue'] = (await cursor.fetchone())['revenue']
            
            cursor = await db.execute("""
                SELECT COALESCE(SUM(price_usd), 0) as revenue 
                FROM orders 
                WHERE status = ? AND date(created_at) = date('now')
            """, (OrderStatus.COMPLETED,))
            stats['revenue_today'] = (await cursor.fetchone())['revenue']
            
            cursor = await db.execute("""
                SELECT COALESCE(SUM(price_usd), 0) as revenue 
                FROM orders 
                WHERE status = ? AND date(created_at) >= date('now', '-7 days')
            """, (OrderStatus.COMPLETED,))
            stats['revenue_week'] = (await cursor.fetchone())['revenue']
            
            cursor = await db.execute("""
                SELECT COALESCE(SUM(price_usd), 0) as revenue 
                FROM orders 
                WHERE status = ? AND date(created_at) >= date('now', '-30 days')
            """, (OrderStatus.COMPLETED,))
            stats['revenue_month'] = (await cursor.fetchone())['revenue']
            
            # === إحصائيات الشحن ===
            cursor = await db.execute("""
                SELECT COUNT(*) as count FROM financial_logs WHERE type = 'DEPOSIT'
            """)
            stats['total_deposits'] = (await cursor.fetchone())['count']
            
            cursor = await db.execute("""
                SELECT COALESCE(SUM(amount), 0) as total FROM financial_logs 
                WHERE type = 'DEPOSIT'
            """)
            stats['total_deposit_amount'] = (await cursor.fetchone())['total']
            
            cursor = await db.execute("""
                SELECT COALESCE(SUM(amount), 0) as total FROM financial_logs 
                WHERE type = 'DEPOSIT' AND date(created_at) = date('now')
            """)
            stats['deposits_today'] = (await cursor.fetchone())['total']
            
            # === معدلات النجاح ===
            if stats['total_orders'] > 0:
                stats['success_rate'] = (stats['completed_orders'] / stats['total_orders']) * 100
            else:
                stats['success_rate'] = 0
            
            # === متوسط قيمة الطلب ===
            if stats['completed_orders'] > 0:
                stats['avg_order_value'] = stats['total_revenue'] / stats['completed_orders']
            else:
                stats['avg_order_value'] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}", exc_info=True)
            return {}
    
    
    @staticmethod
    async def get_orders_by_status() -> Dict[str, int]:
        """إحصائيات الطلبات حسب الحالة"""
        try:
            db = await db_manager.connect()
            cursor = await db.execute("""
                SELECT status, COUNT(*) as count 
                FROM orders 
                GROUP BY status
            """)
            
            results = await cursor.fetchall()
            return {row['status']: row['count'] for row in results}
            
        except Exception as e:
            logger.error(f"Error getting orders by status: {e}", exc_info=True)
            return {}
    
    
    @staticmethod
    async def get_top_products(limit: int = 10) -> list:
        """أكثر المنتجات مبيعاً"""
        try:
            db = await db_manager.connect()
            cursor = await db.execute("""
                SELECT p.name, COUNT(o.id) as order_count, SUM(o.price_usd) as total_revenue
                FROM orders o
                JOIN products p ON o.product_id = p.id
                WHERE o.status = ?
                GROUP BY o.product_id
                ORDER BY order_count DESC
                LIMIT ?
            """, (OrderStatus.COMPLETED, limit))
            
            return [dict(row) for row in await cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Error getting top products: {e}", exc_info=True)
            return []
    
    
    @staticmethod
    async def get_revenue_chart(days: int = 7) -> Dict[str, float]:
        """رسم بياني للإيرادات اليومية"""
        try:
            db = await db_manager.connect()
            cursor = await db.execute("""
                SELECT date(created_at) as date, COALESCE(SUM(price_usd), 0) as revenue
                FROM orders
                WHERE status = ? AND date(created_at) >= date('now', ?)
                GROUP BY date(created_at)
                ORDER BY date(created_at)
            """, (OrderStatus.COMPLETED, f'-{days} days'))
            
            results = await cursor.fetchall()
            return {row['date']: row['revenue'] for row in results}
            
        except Exception as e:
            logger.error(f"Error getting revenue chart: {e}", exc_info=True)
            return {}
    
    
    @staticmethod
    async def get_user_activity() -> Dict[str, Any]:
        """نشاط المستخدمين"""
        try:
            db = await db_manager.connect()
            
            # المستخدمون النشطون (لديهم طلبات)
            cursor = await db.execute("""
                SELECT COUNT(DISTINCT user_id) as count 
                FROM orders 
                WHERE date(created_at) >= date('now', '-30 days')
            """)
            active_users = (await cursor.fetchone())['count']
            
            # متوسط الطلبات لكل مستخدم
            cursor = await db.execute("""
                SELECT AVG(order_count) as avg_orders
                FROM (
                    SELECT user_id, COUNT(*) as order_count
                    FROM orders
                    GROUP BY user_id
                )
            """)
            avg_orders_per_user = (await cursor.fetchone())['avg_orders'] or 0
            
            return {
                'active_users_month': active_users,
                'avg_orders_per_user': round(avg_orders_per_user, 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting user activity: {e}", exc_info=True)
            return {}


# إنشاء instance واحد
analytics_service = AnalyticsService()
