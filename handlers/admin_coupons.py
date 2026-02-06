"""
نظام إدارة الكوبونات
يسمح للأدمن بإنشاء وإدارة كوبونات الخصم
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.manager import db_manager
from utils.translations import get_text, get_user_language
from datetime import datetime, timedelta
import logging

router = Router()
logger = logging.getLogger(__name__)

class CouponStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_type = State()
    waiting_for_value = State()
    waiting_for_max_uses = State()
    waiting_for_min_amount = State()
    waiting_for_expires_days = State()

@router.callback_query(F.data == "admin_coupons")
async def admin_coupons_main(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """القائمة الرئيسية لإدارة الكوبونات"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ إنشاء كوبون جديد", callback_data="admin_coupon_create_start"))
    builder.row(InlineKeyboardButton(text="📋 عرض الكوبونات", callback_data="admin_coupon_list"))
    builder.row(InlineKeyboardButton(text="📊 إحصائيات الكوبونات", callback_data="admin_coupon_stats"))
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="admin_main"))
    
    await callback.message.edit_text(
        "🎟️ *نظام إدارة الكوبونات المطور*\n\nيمكنك إنشاء كوبونات خصم بنسبة مئوية أو بمبلغ ثابت، وتحديد الحد الأدنى للشراء وعدد مرات الاستخدام.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_coupon_stats")
async def admin_coupon_stats(callback: types.CallbackQuery, is_admin: bool):
    """إحصائيات الكوبونات"""
    if not is_admin: return
    
    db = await db_manager.connect()
    cursor = await db.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(used_count) as total_uses,
            SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) as active
        FROM coupons
    """)
    stats = await cursor.fetchone()
    
    text = (
        f"📊 *إحصائيات الكوبونات*\n\n"
        f"🎟️ إجمالي الكوبونات: `{stats['total']}`\n"
        f"✅ كوبونات نشطة: `{stats['active']}`\n"
        f"📈 إجمالي مرات الاستخدام: `{stats['total_uses']}`"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="admin_coupons"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_coupon_create_start")
async def admin_coupon_create_start(callback: types.CallbackQuery, state: FSMContext, is_admin: bool, user: dict):
    """بدء إنشاء كوبون جديد"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    await state.set_state(CouponStates.waiting_for_code)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn_cancel", lang),
        callback_data="admin_coupons"
    ))
    
    await callback.message.edit_text(
        "🎟️ *إنشاء كوبون جديد*\n\n"
        "الخطوة 1/5: أرسل كود الكوبون (مثال: WELCOME2024)",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.message(CouponStates.waiting_for_code)
async def admin_coupon_code_received(message: types.Message, state: FSMContext, is_admin: bool, user: dict):
    """استقبال كود الكوبون"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    code = message.text.strip().upper()
    
    # التحقق من عدم وجود الكوبون مسبقاً
    existing = await db_manager.get_coupon(code)
    if existing:
        return await message.answer("❌ هذا الكوبون موجود مسبقاً! أرسل كوداً آخر.")
    
    await state.update_data(code=code)
    await state.set_state(CouponStates.waiting_for_type)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💯 نسبة مئوية (%)", callback_data="coupon_type_PERCENTAGE"),
        InlineKeyboardButton(text="💵 مبلغ ثابت ($)", callback_data="coupon_type_FIXED")
    )
    builder.row(InlineKeyboardButton(
        text=get_text("btn_cancel", lang),
        callback_data="admin_coupons"
    ))
    
    await message.answer(
        f"✅ الكود: `{code}`\n\n"
        "الخطوة 2/5: اختر نوع الخصم:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("coupon_type_"))
async def admin_coupon_type_selected(callback: types.CallbackQuery, state: FSMContext, is_admin: bool, user: dict):
    """اختيار نوع الكوبون"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    coupon_type = callback.data.split("_")[2]
    await state.update_data(type=coupon_type)
    await state.set_state(CouponStates.waiting_for_value)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn_cancel", lang),
        callback_data="admin_coupons"
    ))
    
    if coupon_type == "PERCENTAGE":
        prompt = "الخطوة 3/5: أرسل نسبة الخصم (مثال: 10 لخصم 10%)"
    else:
        prompt = "الخطوة 3/5: أرسل قيمة الخصم بالدولار (مثال: 5)"
    
    await callback.message.edit_text(
        prompt,
        reply_markup=builder.as_markup()
    )

@router.message(CouponStates.waiting_for_value)
async def admin_coupon_value_received(message: types.Message, state: FSMContext, is_admin: bool, user: dict):
    """استقبال قيمة الخصم"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    
    try:
        value = float(message.text)
        if value <= 0:
            raise ValueError
        
        data = await state.get_data()
        if data['type'] == 'PERCENTAGE' and value > 100:
            return await message.answer("❌ النسبة يجب أن تكون بين 1 و 100")
        
        await state.update_data(value=value)
        await state.set_state(CouponStates.waiting_for_max_uses)
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="♾️ غير محدود", callback_data="coupon_uses_unlimited"))
        builder.row(InlineKeyboardButton(
            text=get_text("btn_cancel", lang),
            callback_data="admin_coupons"
        ))
        
        await message.answer(
            "الخطوة 4/5: أرسل الحد الأقصى لعدد الاستخدامات (أو اضغط 'غير محدود'):",
            reply_markup=builder.as_markup()
        )
    except ValueError:
        await message.answer(get_text("error_invalid_input", lang))

@router.callback_query(F.data == "coupon_uses_unlimited")
async def admin_coupon_unlimited_uses(callback: types.CallbackQuery, state: FSMContext, is_admin: bool):
    """تعيين استخدامات غير محدودة"""
    if not is_admin:
        return
    
    await state.update_data(max_uses=999999)
    await admin_coupon_ask_min_amount(callback, state)

@router.message(CouponStates.waiting_for_max_uses)
async def admin_coupon_max_uses_received(message: types.Message, state: FSMContext, is_admin: bool, user: dict):
    """استقبال عدد الاستخدامات"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    
    try:
        max_uses = int(message.text)
        if max_uses <= 0:
            raise ValueError
        
        await state.update_data(max_uses=max_uses)
        
        # الانتقال للخطوة التالية
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="0️⃣ بدون حد أدنى", callback_data="coupon_min_zero"))
        builder.row(InlineKeyboardButton(
            text=get_text("btn_cancel", "ar"),
            callback_data="admin_coupons"
        ))
        
        await message.answer(
            "الخطوة 5/5: أرسل الحد الأدنى لمبلغ الطلب بالدولار (أو اضغط 'بدون حد أدنى'):",
            reply_markup=builder.as_markup()
        )
        await state.set_state(CouponStates.waiting_for_min_amount)
        
    except ValueError:
        await message.answer(get_text("error_invalid_input", lang))

async def admin_coupon_ask_min_amount(callback_or_message, state: FSMContext):
    """طلب الحد الأدنى للمبلغ"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="0️⃣ بدون حد أدنى", callback_data="coupon_min_zero"))
    builder.row(InlineKeyboardButton(text=get_text("btn_cancel", "ar"), callback_data="admin_coupons"))
    
    text = "الخطوة 5/5: أرسل الحد الأدنى لمبلغ الطلب بالدولار (أو اضغط 'بدون حد أدنى'):"
    
    if isinstance(callback_or_message, types.CallbackQuery):
        await callback_or_message.message.edit_text(text, reply_markup=builder.as_markup())
    else:
        await callback_or_message.answer(text, reply_markup=builder.as_markup())
    
    await state.set_state(CouponStates.waiting_for_min_amount)

@router.callback_query(F.data == "coupon_min_zero")
async def admin_coupon_min_zero(callback: types.CallbackQuery, state: FSMContext, is_admin: bool):
    """تعيين حد أدنى صفر"""
    if not is_admin:
        return
    
    await state.update_data(min_amount=0)
    await admin_coupon_finalize(callback, state)

@router.message(CouponStates.waiting_for_min_amount)
async def admin_coupon_min_amount_received(message: types.Message, state: FSMContext, is_admin: bool, user: dict):
    """استقبال الحد الأدنى"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    
    try:
        min_amount = float(message.text)
        if min_amount < 0:
            raise ValueError
        
        await state.update_data(min_amount=min_amount)
        await admin_coupon_finalize(message, state)
        
    except ValueError:
        await message.answer(get_text("error_invalid_input", lang))

async def admin_coupon_finalize(message_or_callback, state: FSMContext):
    """إنهاء إنشاء الكوبون"""
    data = await state.get_data()
    
    # تعيين تاريخ انتهاء افتراضي (30 يوم)
    expires_at = (datetime.now() + timedelta(days=30)).isoformat()
    
    # إنشاء الكوبون
    try:
        user_id = message_or_callback.from_user.id if isinstance(message_or_callback, types.Message) else message_or_callback.from_user.id
        
        await db_manager.create_coupon(
            code=data['code'],
            type=data['type'],
            value=data['value'],
            max_uses=data['max_uses'],
            min_amount=data['min_amount'],
            expires_at=expires_at,
            created_by=user_id
        )
        
        # تسجيل العملية
        await db_manager.log_admin_action(
            admin_id=user_id,
            action="COUPON_CREATE",
            target_type="COUPON",
            details=f"إنشاء كوبون: {data['code']}"
        )
        
        summary = (
            f"✅ *تم إنشاء الكوبون بنجاح!*\n\n"
            f"🎟️ الكود: `{data['code']}`\n"
            f"💰 النوع: {'نسبة مئوية' if data['type'] == 'PERCENTAGE' else 'مبلغ ثابت'}\n"
            f"📊 القيمة: {data['value']}{'%' if data['type'] == 'PERCENTAGE' else '$'}\n"
            f"🔢 الاستخدامات: {data['max_uses'] if data['max_uses'] < 999999 else 'غير محدود'}\n"
            f"💵 الحد الأدنى: {data['min_amount']}$\n"
            f"📅 ينتهي في: 30 يوم"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="admin_coupons"))
        
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(summary, reply_markup=builder.as_markup(), parse_mode="Markdown")
        else:
            await message_or_callback.message.answer(summary, reply_markup=builder.as_markup(), parse_mode="Markdown")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating coupon: {e}")
        error_msg = f"❌ حدث خطأ أثناء إنشاء الكوبون: {str(e)}"
        
        if isinstance(message_or_callback, types.Message):
            await message_or_callback.answer(error_msg)
        else:
            await message_or_callback.message.answer(error_msg)

@router.callback_query(F.data == "admin_coupon_list")
async def admin_coupon_list(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض قائمة الكوبونات"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    coupons = await db_manager.get_all_coupons()
    
    if not coupons:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="admin_coupons"
        ))
        return await callback.message.edit_text(
            "📭 لا توجد كوبونات حالياً",
            reply_markup=builder.as_markup()
        )
    
    builder = InlineKeyboardBuilder()
    for coupon in coupons:
        status_icon = "✅" if coupon['is_active'] else "❌"
        usage = f"{coupon['used_count']}/{coupon['max_uses']}"
        builder.row(InlineKeyboardButton(
            text=f"{status_icon} {coupon['code']} ({usage})",
            callback_data=f"admin_coupon_view_{coupon['id']}"
        ))
    
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_coupons"
    ))
    
    await callback.message.edit_text(
        f"🎟️ *قائمة الكوبونات* ({len(coupons)})",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("admin_coupon_view_"))
async def admin_coupon_view(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض تفاصيل كوبون"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    coupon_id = int(callback.data.split("_")[3])
    
    # جلب الكوبون من قاعدة البيانات
    db = await db_manager.connect()
    cursor = await db.execute("SELECT * FROM coupons WHERE id = ?", (coupon_id,))
    coupon = await cursor.fetchone()
    
    if not coupon:
        return await callback.answer("❌ الكوبون غير موجود", show_alert=True)
    
    coupon = dict(coupon)
    status = "✅ نشط" if coupon['is_active'] else "❌ معطل"
    
    text = (
        f"🎟️ *تفاصيل الكوبون*\n\n"
        f"الكود: `{coupon['code']}`\n"
        f"النوع: {'نسبة مئوية' if coupon['type'] == 'PERCENTAGE' else 'مبلغ ثابت'}\n"
        f"القيمة: {coupon['value']}{'%' if coupon['type'] == 'PERCENTAGE' else '$'}\n"
        f"الاستخدامات: {coupon['used_count']}/{coupon['max_uses']}\n"
        f"الحد الأدنى: {coupon['min_amount']}$\n"
        f"الحالة: {status}\n"
        f"تاريخ الإنشاء: {coupon['created_at']}\n"
        f"ينتهي في: {coupon['expires_at'] or 'غير محدد'}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔄 تفعيل/تعطيل",
        callback_data=f"admin_coupon_toggle_{coupon_id}"
    ))
    builder.row(InlineKeyboardButton(
        text="🗑 حذف",
        callback_data=f"admin_coupon_delete_{coupon_id}"
    ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_coupon_list"
    ))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_coupon_toggle_"))
async def admin_coupon_toggle(callback: types.CallbackQuery, is_admin: bool):
    """تفعيل/تعطيل كوبون"""
    if not is_admin:
        return
    
    coupon_id = int(callback.data.split("_")[3])
    
    db = await db_manager.connect()
    cursor = await db.execute("SELECT is_active FROM coupons WHERE id = ?", (coupon_id,))
    coupon = await cursor.fetchone()
    
    if not coupon:
        return await callback.answer("❌ الكوبون غير موجود", show_alert=True)
    
    new_status = 0 if coupon['is_active'] else 1
    await db.execute("UPDATE coupons SET is_active = ? WHERE id = ?", (new_status, coupon_id))
    await db.commit()
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} الكوبون")
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="COUPON_TOGGLE",
        target_type="COUPON",
        target_id=coupon_id,
        details=f"{'تفعيل' if new_status else 'تعطيل'} الكوبون"
    )
    
    # إعادة عرض التفاصيل
    await admin_coupon_view(callback, is_admin, {})

@router.callback_query(F.data.startswith("admin_coupon_delete_"))
async def admin_coupon_delete(callback: types.CallbackQuery, is_admin: bool):
    """حذف كوبون"""
    if not is_admin:
        return
    
    coupon_id = int(callback.data.split("_")[3])
    
    await db_manager.delete_coupon(coupon_id)
    await callback.answer("✅ تم حذف الكوبون")
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="COUPON_DELETE",
        target_type="COUPON",
        target_id=coupon_id,
        details="حذف كوبون"
    )
    
    # العودة لقائمة الكوبونات
    await admin_coupon_list(callback, is_admin, {})
