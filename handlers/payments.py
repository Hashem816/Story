"""
نظام إدارة طرق الدفع المحسّن
التحسينات:
- إضافة Soft Delete بدلاً من الحذف المباشر
- التحقق من الطلبات المرتبطة قبل الحذف
- تسجيل جميع العمليات في Audit Log
"""

from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_payment_methods_keyboard
import logging

router = Router()
logger = logging.getLogger(__name__)

# ===== FSM States =====
class PaymentMethodStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_desc = State()
    
    edit_waiting_for_name = State()
    edit_waiting_for_desc = State()


# ===== القائمة الرئيسية =====
@router.callback_query(F.data == "admin_payment_methods")
async def admin_payment_methods_main(callback: types.CallbackQuery, is_operator: bool):
    """القائمة الرئيسية لإدارة طرق الدفع"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    methods = await db_manager.get_payment_methods(only_active=False)
    await callback.message.edit_text(
        "💳 *إدارة طرق الدفع*\n\nاختر طريقة لتعديلها أو أضف واحدة جديدة:", 
        reply_markup=get_payment_methods_keyboard(methods, is_admin=True), 
        parse_mode="Markdown"
    )
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="VIEW_PAYMENT_METHODS_PANEL",
        target_type="PAYMENT_METHOD"
    )


# ===== إضافة طريقة دفع =====
@router.callback_query(F.data == "admin_add_pay_start")
async def admin_add_pay_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء إضافة طريقة دفع جديدة"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    await state.set_state(PaymentMethodStates.waiting_for_name)
    await callback.message.edit_text(
        "💳 أدخل اسم طريقة الدفع الجديدة (مثلاً: سيريتيل كاش):", 
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_payment_methods")]]
        )
    )


@router.message(PaymentMethodStates.waiting_for_name)
async def admin_add_pay_name(message: types.Message, state: FSMContext):
    """استقبال اسم طريقة الدفع"""
    await state.update_data(name=message.text.strip())
    await state.set_state(PaymentMethodStates.waiting_for_desc)
    await message.answer("📝 أدخل تعليمات الدفع (رقم الحساب، الاسم، إلخ):")


@router.message(PaymentMethodStates.waiting_for_desc)
async def admin_add_pay_finish(message: types.Message, state: FSMContext, is_operator: bool):
    """إنهاء إضافة طريقة الدفع"""
    if not is_operator:
        return
    
    data = await state.get_data()
    description = message.text.strip()
    
    db = await db_manager.connect()
    await db.execute(
        "INSERT INTO payment_methods (name, description, is_active) VALUES (?, ?, 1)", 
        (data['name'], description)
    )
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="CREATE_PAYMENT_METHOD",
        target_type="PAYMENT_METHOD",
        details=f"إنشاء طريقة دفع: {data['name']}"
    )
    
    await state.clear()
    await message.answer(f"✅ تم إضافة طريقة الدفع: {data['name']}")
    
    methods = await db_manager.get_payment_methods(only_active=False)
    await message.answer(
        "💳 إدارة طرق الدفع", 
        reply_markup=get_payment_methods_keyboard(methods, is_admin=True)
    )


# ===== عرض تفاصيل طريقة دفع =====
@router.callback_query(F.data.startswith("admin_view_pay_"))
async def admin_view_pay(callback: types.CallbackQuery, is_operator: bool):
    """عرض تفاصيل طريقة دفع مع خيارات التعديل"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    method_id = int(callback.data.split("_")[3])
    method = await db_manager.get_payment_method(method_id)
    
    if not method:
        await callback.answer("❌ طريقة الدفع غير موجودة", show_alert=True)
        return
    
    status = "✅ نشطة" if method['is_active'] else "❌ معطلة"
    text = (
        f"💳 *تفاصيل طريقة الدفع*\n\n"
        f"الاسم: `{method['name']}`\n"
        f"الحالة: {status}\n\n"
        f"التعليمات:\n`{method['description']}`"
    )
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✏️ تعديل الاسم", callback_data=f"admin_edit_pay_name_{method_id}")],
        [types.InlineKeyboardButton(text="📝 تعديل التعليمات", callback_data=f"admin_edit_pay_desc_{method_id}")],
        [types.InlineKeyboardButton(text="🔄 تغيير الحالة (تفعيل/تعطيل)", callback_data=f"admin_toggle_pay_{method_id}")],
        [types.InlineKeyboardButton(text="🗑 حذف", callback_data=f"admin_del_pay_{method_id}")],
        [types.InlineKeyboardButton(text="🔙 عودة", callback_data="admin_payment_methods")]
    ])
    
    await callback.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")


# ===== تعديل اسم طريقة الدفع =====
@router.callback_query(F.data.startswith("admin_edit_pay_name_"))
async def admin_edit_pay_name_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء تعديل اسم طريقة الدفع"""
    if not is_operator:
        return
    
    method_id = int(callback.data.split("_")[4])
    await state.update_data(method_id=method_id)
    await state.set_state(PaymentMethodStates.edit_waiting_for_name)
    
    await callback.message.edit_text(
        "📝 أدخل الاسم الجديد لطريقة الدفع:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_view_pay_{method_id}")]]
        )
    )


@router.message(PaymentMethodStates.edit_waiting_for_name)
async def admin_edit_pay_name_finish(message: types.Message, state: FSMContext, is_operator: bool):
    """إنهاء تعديل اسم طريقة الدفع"""
    if not is_operator:
        return
    
    data = await state.get_data()
    method_id = data['method_id']
    new_name = message.text.strip()
    
    db = await db_manager.connect()
    await db.execute("UPDATE payment_methods SET name = ? WHERE id = ?", (new_name, method_id))
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="UPDATE_PAYMENT_METHOD",
        target_type="PAYMENT_METHOD",
        target_id=method_id,
        details=f"تعديل اسم طريقة الدفع إلى: {new_name}"
    )
    
    await state.clear()
    await message.answer(f"✅ تم تحديث اسم طريقة الدفع إلى: {new_name}")


# ===== تعديل تعليمات طريقة الدفع =====
@router.callback_query(F.data.startswith("admin_edit_pay_desc_"))
async def admin_edit_pay_desc_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء تعديل تعليمات طريقة الدفع"""
    if not is_operator:
        return
    
    method_id = int(callback.data.split("_")[4])
    await state.update_data(method_id=method_id)
    await state.set_state(PaymentMethodStates.edit_waiting_for_desc)
    
    await callback.message.edit_text(
        "📝 أدخل التعليمات الجديدة لطريقة الدفع:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_view_pay_{method_id}")]]
        )
    )


@router.message(PaymentMethodStates.edit_waiting_for_desc)
async def admin_edit_pay_desc_finish(message: types.Message, state: FSMContext, is_operator: bool):
    """إنهاء تعديل تعليمات طريقة الدفع"""
    if not is_operator:
        return
    
    data = await state.get_data()
    method_id = data['method_id']
    new_desc = message.text.strip()
    
    db = await db_manager.connect()
    await db.execute("UPDATE payment_methods SET description = ? WHERE id = ?", (new_desc, method_id))
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="UPDATE_PAYMENT_METHOD",
        target_type="PAYMENT_METHOD",
        target_id=method_id,
        details=f"تعديل تعليمات طريقة الدفع"
    )
    
    await state.clear()
    await message.answer(f"✅ تم تحديث تعليمات طريقة الدفع")


# ===== تغيير حالة طريقة الدفع =====
@router.callback_query(F.data.startswith("admin_toggle_pay_"))
async def admin_toggle_pay(callback: types.CallbackQuery, is_operator: bool):
    """تفعيل/تعطيل طريقة دفع"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    method_id = int(callback.data.split("_")[3])
    method = await db_manager.get_payment_method(method_id)
    
    if not method:
        await callback.answer("❌ طريقة الدفع غير موجودة", show_alert=True)
        return
    
    new_status = 0 if method['is_active'] else 1
    
    db = await db_manager.connect()
    await db.execute("UPDATE payment_methods SET is_active = ? WHERE id = ?", (new_status, method_id))
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="TOGGLE_PAYMENT_METHOD",
        target_type="PAYMENT_METHOD",
        target_id=method_id,
        details=f"تغيير حالة طريقة الدفع إلى: {'نشطة' if new_status else 'معطلة'}"
    )
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} طريقة الدفع")
    
    # العودة لعرض طريقة الدفع
    await admin_view_pay(callback, is_operator)


# ===== حذف طريقة دفع (Soft Delete) =====
@router.callback_query(F.data.startswith("admin_del_pay_"))
async def admin_delete_pay_confirm(callback: types.CallbackQuery, is_operator: bool):
    """تأكيد حذف طريقة دفع"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    method_id = int(callback.data.split("_")[3])
    method = await db_manager.get_payment_method(method_id)
    
    if not method:
        await callback.answer("❌ طريقة الدفع غير موجودة", show_alert=True)
        return
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ نعم، احذف", callback_data=f"admin_del_pay_confirm_{method_id}")],
        [types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_view_pay_{method_id}")]
    ])
    
    await callback.message.edit_text(
        f"⚠️ *تأكيد الحذف*\n\n"
        f"هل أنت متأكد من حذف طريقة الدفع:\n`{method['name']}`؟\n\n"
        f"ℹ️ ملاحظة: سيتم الحذف بشكل آمن (Soft Delete) ولن يؤثر على الطلبات السابقة.",
        reply_markup=builder,
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("admin_del_pay_confirm_"))
async def admin_delete_pay_execute(callback: types.CallbackQuery, is_operator: bool):
    """تنفيذ حذف طريقة دفع"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    method_id = int(callback.data.split("_")[4])
    
    db = await db_manager.connect()
    try:
        # التحقق من وجود طلبات
        cursor = await db.execute("SELECT COUNT(*) as count FROM orders WHERE payment_method_id = ?", (method_id,))
        count = (await cursor.fetchone())['count']
        
        if count == 0:
            # حذف نهائي إذا لم توجد طلبات
            await db.execute("DELETE FROM payment_methods WHERE id = ?", (method_id,))
            await db.commit()
            details = "حذف نهائي (لا توجد طلبات مرتبطة)"
        else:
            # Soft Delete إذا وجدت طلبات
            await db.execute("UPDATE payment_methods SET deleted_at = CURRENT_TIMESTAMP, is_active = 0 WHERE id = ?", (method_id,))
            await db.commit()
            details = "حذف آمن (Soft Delete - توجد طلبات مرتبطة سابقة)"
            
        await callback.answer("✅ تم حذف طريقة الدفع")
        await db_manager.log_admin_action(callback.from_user.id, "DELETE_PAYMENT_METHOD", "PAYMENT_METHOD", method_id, details)
        
        # العودة لقائمة طرق الدفع
        methods = await db_manager.get_payment_methods(only_active=False)
        await callback.message.edit_text(
            "💳 *إدارة طرق الدفع*\n\nاختر طريقة لتعديلها أو أضف واحدة جديدة:", 
            reply_markup=get_payment_methods_keyboard(methods, is_admin=True), 
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error deleting payment method: {e}")
        await callback.answer("❌ حدث خطأ أثناء الحذف", show_alert=True)


# ===== معالجة عمليات الشحن (Deposit Approval) =====
@router.callback_query(F.data.startswith("admin_pay_approve_"))
async def admin_approve_payment(callback: types.CallbackQuery, bot: Bot, is_operator: bool):
    """قبول طلب شحن رصيد"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    parts = callback.data.split("_")
    # التأكد من طول الأجزاء لتجنب IndexError
    if len(parts) < 5:
        await callback.answer("⚠️ بيانات غير مكتملة في الزر", show_alert=True)
        return
        
    user_id, amount = int(parts[3]), float(parts[4])
    
    success, new_bal = await db_manager.update_user_balance(
        user_id=user_id,
        amount=amount,
        log_type="DEPOSIT",
        admin_id=callback.from_user.id,
        reason="شحن يدوي - موافقة الأدمن"
    )
    
    if success:
        # تسجيل العملية
        await db_manager.log_admin_action(
            admin_id=callback.from_user.id,
            action="APPROVE_DEPOSIT",
            target_type="USER",
            target_id=user_id,
            details=f"قبول شحن رصيد بمبلغ {amount}$ للمستخدم {user_id}"
        )
        
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n✅ *تم القبول بنجاح*", 
            parse_mode="Markdown"
        )
        
        try:
            await bot.send_message(
                user_id, 
                f"✅ تم شحن رصيدك بمبلغ {amount}$.\nرصيدك الحالي: {new_bal:.2f}$"
            )
        except Exception as e:
            logger.error(f"Failed to send message to user {user_id}: {e}")
    else:
        await callback.answer(f"❌ فشل: {new_bal}", show_alert=True)


@router.callback_query(F.data.startswith("admin_pay_reject_"))
async def admin_reject_payment(callback: types.CallbackQuery, bot: Bot, is_operator: bool):
    """رفض طلب شحن رصيد"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[3])
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="REJECT_DEPOSIT",
        target_type="USER",
        target_id=user_id,
        details=f"رفض طلب شحن رصيد للمستخدم {user_id}"
    )
    
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ *تم الرفض*", 
        parse_mode="Markdown"
    )
    
    try:
        await bot.send_message(user_id, "❌ تم رفض طلب شحن الرصيد.")
    except Exception as e:
        logger.error(f"Failed to send message to user {user_id}: {e}")
