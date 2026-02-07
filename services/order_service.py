"""
Order Service Layer - طبقة خدمات الطلبات
التحسينات:
- التحقق من المخزون
- التحقق من السعر
- التحقق من طريقة الدفع
- التحقق من حالة المنتج
- إنشاء طلب آمن مع Transaction
- دعم الوضع اليدوي والتلقائي
"""

import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from database.manager import db_manager
from config.settings import OrderStatus, ProductType, StoreMode

logger = logging.getLogger(__name__)


class OrderValidationError(Exception):
    """استثناء مخصص لأخطاء التحقق من الطلبات"""
    pass


class OrderService:
    """خدمة إدارة الطلبات"""
    
    @staticmethod
    async def validate_order(
        user_id: int,
        product_id: int,
        player_id: str,
        payment_method_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        التحقق من صلاحية الطلب قبل إنشائه
        
        Returns:
            (success: bool, message: str, order_data: dict)
        """
        try:
            # 1. التحقق من المستخدم
            user = await db_manager.get_user(user_id)
            if not user:
                return False, "المستخدم غير موجود", None
            
            if user.get('is_blocked'):
                return False, "حسابك محظور. يرجى التواصل مع الدعم.", None
            
            # 2. التحقق من المنتج
            product = await db_manager.get_product(product_id)
            if not product:
                return False, "المنتج غير موجود", None
            
            if not product.get('is_active'):
                return False, "المنتج غير متاح حالياً", None
            
            if product.get('type') == ProductType.DISABLED:
                return False, "المنتج معطل", None
            
            # 3. التحقق من حالة المتجر
            store_mode = await db_manager.get_setting('store_mode', StoreMode.MANUAL)
            emergency_stop = await db_manager.get_setting('emergency_stop', '0')
            
            if emergency_stop == '1':
                return False, "⚠️ عذراً، المتجر في وضع الطوارئ حالياً لحماية العمليات. يرجى المحاولة لاحقاً.", None
            
            if store_mode == StoreMode.MAINTENANCE:
                return False, "🛠 عذراً، المتجر في وضع الصيانة حالياً للتحديث. سنعود للعمل قريباً!", None
            
            # 4. التحقق من وجود طلب مفتوح
            has_open = await db_manager.has_open_order(user_id)
            if has_open:
                return False, "لديك طلب قيد المعالجة. يرجى انتظار إتمامه أولاً.", None
            
            # 5. التحقق من طريقة الدفع (إذا كانت محددة)
            if payment_method_id:
                payment_method = await db_manager.get_payment_method(payment_method_id)
                if not payment_method:
                    return False, "طريقة الدفع غير موجودة", None
                
                if not payment_method.get('is_active'):
                    return False, "طريقة الدفع غير نشطة", None
            
            # 6. حساب السعر
            dollar_rate = float(await db_manager.get_setting('dollar_rate', '12500'))
            price_usd = product['price_usd']
            price_local = price_usd * dollar_rate
            
            # 7. التحقق من الرصيد (إذا كان الدفع من الرصيد)
            if payment_method_id is None:  # الدفع من الرصيد
                if user['balance'] < price_usd:
                    return False, f"رصيدك غير كافٍ. تحتاج إلى {price_usd}$ ورصيدك الحالي {user['balance']:.2f}$", None
            
            # 8. التحقق من معرف اللاعب
            if not player_id or len(player_id.strip()) == 0:
                return False, "يرجى إدخال معرف اللاعب", None
            
            # إعداد بيانات الطلب
            order_data = {
                'user_id': user_id,
                'product_id': product_id,
                'product': product,
                'player_id': player_id.strip(),
                'price_usd': price_usd,
                'price_local': price_local,
                'exchange_rate': dollar_rate,
                'payment_method_id': payment_method_id,
                'execution_type': product['type']  # MANUAL or AUTOMATIC
            }
            
            return True, "الطلب صالح", order_data
            
        except Exception as e:
            logger.error(f"Error validating order: {e}", exc_info=True)
            return False, f"خطأ في التحقق من الطلب: {str(e)}", None
    
    
    @staticmethod
    async def create_order(
        user_id: int,
        product_id: int,
        player_id: str,
        payment_method_id: Optional[int] = None,
        coupon_code: Optional[str] = None
    ) -> Tuple[bool, str, Optional[int]]:
        """
        إنشاء طلب جديد مع جميع عمليات التحقق
        
        Returns:
            (success: bool, message: str, order_id: int)
        """
        try:
            # 1. التحقق من صلاحية الطلب
            is_valid, message, order_data = await OrderService.validate_order(
                user_id, product_id, player_id, payment_method_id
            )
            
            if not is_valid:
                return False, message, None
            
            # 2. تطبيق الكوبون (إذا وجد)
            discount_amount = 0
            final_price_usd = order_data['price_usd']
            
            if coupon_code:
                is_valid_coupon, coupon_msg, discount = await db_manager.validate_coupon(
                    coupon_code, user_id, final_price_usd
                )
                
                if is_valid_coupon:
                    discount_amount = discount
                    final_price_usd = max(0, final_price_usd - discount)
                    logger.info(f"Coupon {coupon_code} applied: discount={discount}, final_price={final_price_usd}")
                else:
                    logger.warning(f"Invalid coupon {coupon_code}: {coupon_msg}")
            
            # 3. تحديد حالة الطلب الأولية
            if payment_method_id is None:
                # الدفع من الرصيد
                initial_status = OrderStatus.PAID
            else:
                # الدفع عبر طريقة دفع خارجية
                initial_status = OrderStatus.PENDING_PAYMENT
            
            # 4. إنشاء الطلب في قاعدة البيانات
            db = await db_manager.connect()
            await db.execute("BEGIN")
            
            try:
                # إنشاء الطلب
                cursor = await db.execute("""
                    INSERT INTO orders (
                        user_id, product_id, player_id, 
                        price_usd, price_local, exchange_rate,
                        status, payment_method_id, execution_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id,
                    product_id,
                    order_data['player_id'],
                    final_price_usd,
                    final_price_usd * order_data['exchange_rate'],
                    order_data['exchange_rate'],
                    initial_status,
                    payment_method_id,
                    order_data['execution_type']
                ))
                
                order_id = cursor.lastrowid
                
                # إذا كان الدفع من الرصيد، خصم المبلغ
                if payment_method_id is None:
                    success, result = await db_manager.update_user_balance(
                        user_id=user_id,
                        amount=-final_price_usd,
                        log_type="PURCHASE",
                        reason=f"شراء منتج: {order_data['product']['name']}",
                        order_id=order_id
                    )
                    
                    if not success:
                        await db.rollback()
                        return False, f"فشل خصم الرصيد: {result}", None
                
                # تسجيل استخدام الكوبون
                if coupon_code and discount_amount > 0:
                    await db_manager.use_coupon(coupon_code, user_id, order_id, discount_amount)
                
                # تسجيل في trust_logs
                await db.execute("""
                    INSERT INTO trust_logs (order_id, user_id, action_text, execution_type)
                    VALUES (?, ?, ?, ?)
                """, (
                    order_id,
                    user_id,
                    f"إنشاء طلب جديد #{order_id}",
                    order_data['execution_type']
                ))
                
                await db.commit()
                
                logger.info(f"Order created successfully: order_id={order_id}, user_id={user_id}, product_id={product_id}")
                
                return True, "تم إنشاء الطلب بنجاح", order_id
                
            except Exception as e:
                await db.rollback()
                logger.error(f"Error creating order in database: {e}", exc_info=True)
                return False, f"خطأ في إنشاء الطلب: {str(e)}", None
                
        except Exception as e:
            logger.error(f"Error in create_order: {e}", exc_info=True)
            return False, f"خطأ غير متوقع: {str(e)}", None
    
    
    @staticmethod
    async def finalize_order(
        order_id: int,
        status: str,
        admin_id: Optional[int] = None,
        admin_notes: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        إنهاء الطلب (إكمال أو فشل أو إلغاء)
        
        Returns:
            (success: bool, message: str)
        """
        try:
            # التحقق من الطلب
            order = await db_manager.get_order(order_id)
            if not order:
                return False, "الطلب غير موجود"
            
            # التحقق من الحالة
            if status not in [OrderStatus.COMPLETED, OrderStatus.FAILED, OrderStatus.CANCELED]:
                return False, "حالة غير صالحة"
            
            # تحديث حالة الطلب
            await db_manager.update_order_status(
                order_id=order_id,
                status=status,
                admin_notes=admin_notes,
                execution_type=order.get('execution_type', 'MANUAL'),
                operator_id=admin_id
            )
            
            # إذا فشل الطلب أو تم إلغاؤه، إرجاع الرصيد (إذا كان الدفع من الرصيد)
            if status in [OrderStatus.FAILED, OrderStatus.CANCELED]:
                if order.get('payment_method_id') is None:  # الدفع كان من الرصيد
                    await db_manager.update_user_balance(
                        user_id=order['user_id'],
                        amount=order['price_usd'],
                        log_type="REFUND",
                        admin_id=admin_id,
                        reason=f"إرجاع رصيد الطلب #{order_id} - {status}",
                        order_id=order_id
                    )
            
            # تسجيل العملية
            if admin_id:
                await db_manager.log_admin_action(
                    admin_id=admin_id,
                    action=f"FINALIZE_ORDER_{status}",
                    target_type="ORDER",
                    target_id=order_id,
                    details=f"إنهاء الطلب #{order_id} بحالة {status}"
                )
            
            logger.info(f"Order finalized: order_id={order_id}, status={status}")
            
            return True, f"تم إنهاء الطلب بحالة: {status}"
            
        except Exception as e:
            logger.error(f"Error finalizing order: {e}", exc_info=True)
            return False, f"خطأ في إنهاء الطلب: {str(e)}"
    
    
    @staticmethod
    async def get_order_summary(order_id: int) -> Optional[Dict[str, Any]]:
        """
        الحصول على ملخص كامل للطلب
        
        Returns:
            dict مع جميع تفاصيل الطلب
        """
        try:
            order = await db_manager.get_order(order_id)
            if not order:
                return None
            
            # إضافة معلومات إضافية
            product = await db_manager.get_product(order['product_id'])
            user = await db_manager.get_user(order['telegram_id'])
            
            payment_method = None
            if order.get('payment_method_id'):
                payment_method = await db_manager.get_payment_method(order['payment_method_id'])
            
            summary = {
                **dict(order),
                'product_details': product,
                'user_details': user,
                'payment_method_details': payment_method
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting order summary: {e}", exc_info=True)
            return None


# إنشاء instance واحد من OrderService
order_service = OrderService()
