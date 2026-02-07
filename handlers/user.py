"""
معالج المستخدمين - محسّن
التحسينات:
- استخدام OrderService لإنشاء الطلبات
- تحسين معالجة الأخطاء
- دعم الكوبونات
"""

from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from services.order_service import order_service
from utils.keyboards import get_main_menu, get_categories_keyboard, get_products_keyboard, get_order_confirm_keyboard
from utils.translations import get_text, get_user_language, TRANSLATIONS
from config.settings import OrderStatus, UserRole
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

router = Router()
logger = logging.getLogger(__name__)

# ===== FSM States =====
class OrderProcess(StatesGroup):
    waiting_for_player_id = State()
    confirming = State()
    waiting_for_coupon = State()
    waiting_for_receipt = State()
    waiting_for_coupon_main = State()

class RechargeProcess(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()


# ===== الأوامر الأساسية =====
@router.message(CommandStart())
async def cmd_start(message: types.Message, user_role: str, user: dict):
    """رسالة الترحيب مع اختيار اللغة للمستخدمين الجدد"""
    lang = get_user_language(user)
    
    # إذا كان المستخدم جديد، عرض اختيار اللغة
    if not lang:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
        )
        return await message.answer(
            get_text("welcome", "ar"),
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    
    await message.answer(
        get_text("welcome", lang or "ar"),
        reply_markup=get_main_menu(user_role, lang or "ar")
    )

@router.message(F.text == "🌐 Language / اللغة")
async def change_language_cmd(message: types.Message):
    """تغيير اللغة من القائمة الرئيسية"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
    )
    await message.answer(
        "🌐 *اختر لغتك المفضلة / Choose your language*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


# ===== المتجر والمنتجات =====
@router.message(F.text.in_(["🛒 المتجر", "🛒 Store"]))
async def show_categories(message: types.Message, user: dict):
    """عرض أقسام المتجر"""
    lang = get_user_language(user) or "ar"
    
    if await db_manager.has_open_order(user['telegram_id']):
        return await message.answer(
            get_text("error_open_order", lang) if "error_open_order" in TRANSLATIONS 
            else "⚠️ لديك طلب مفتوح بالفعل، يرجى انتظاره."
        )
    
    categories = await db_manager.get_categories()
    await message.answer(
        get_text("choose_category", lang) if "choose_category" in TRANSLATIONS 
        else "📁 اختر القسم:", 
        reply_markup=get_categories_keyboard(categories)
    )


@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: types.CallbackQuery):
    """العودة لأقسام المتجر"""
    categories = await db_manager.get_categories()
    await callback.message.edit_text("📁 اختر القسم:", reply_markup=get_categories_keyboard(categories))


@router.callback_query(F.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    """عرض منتجات قسم معين"""
    cat_id = int(callback.data.split("_")[1])
    products = await db_manager.get_products(category_id=cat_id)
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    await callback.message.edit_text("📦 اختر المنتج:", reply_markup=get_products_keyboard(products, cat_id, rate))


@router.callback_query(F.data.startswith("prod_"))
async def product_details(callback: types.CallbackQuery, state: FSMContext):
    """عرض تفاصيل منتج وطلب معرف اللاعب"""
    prod_id = int(callback.data.split("_")[1])
    product = await db_manager.get_product(prod_id)
    
    if not product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return
    
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    local_price = product['price_usd'] * rate
    
    await state.update_data(
        selected_prod_id=prod_id, 
        price_usd=product['price_usd'], 
        price_local=local_price, 
        rate=rate
    )
    await state.set_state(OrderProcess.waiting_for_player_id)
    
    text = (
        f"📝 *{product['name']}*\n\n"
        f"📄 {product['description']}\n\n"
        f"💰 السعر: {product['price_usd']}$\n"
        f"💵 السعر بالليرة: {local_price:,.0f} ل.س\n"
        f"📊 سعر الصرف: {rate} ل.س\n\n"
        f"🆔 أدخل معرف اللاعب (Player ID):"
    )
    await callback.message.edit_text(text, parse_mode="Markdown")


@router.message(OrderProcess.waiting_for_player_id)
async def process_player_id(message: types.Message, state: FSMContext, user: dict):
    """معالجة معرف اللاعب وعرض تأكيد الطلب"""
    player_id = message.text.strip()
    
    if len(player_id) == 0:
        await message.answer("⚠️ يرجى إدخال معرف اللاعب")
        return
    
    await state.update_data(player_id=player_id)
    await state.set_state(OrderProcess.confirming)
    
    data = await state.get_data()
    product = await db_manager.get_product(data['selected_prod_id'])
    
    lang = get_user_language(user)
    text = (
        f"⚠️ *تأكيد الطلب*\n\n"
        f"📦 المنتج: {product['name']}\n"
        f"🆔 المعرف: `{player_id}`\n"
        f"💰 السعر: {data['price_local']:,.0f} ل.س ({data['price_usd']}$)\n\n"
        f"سيتم الخصم من رصيدك الداخلي عند التأكيد.\n"
        f"💰 رصيدك الحالي: {user['balance']:.2f}$"
    )
    await message.answer(text, reply_markup=get_order_confirm_keyboard(product['id'], lang), parse_mode="Markdown")


# ===== الكوبونات =====
@router.callback_query(F.data.startswith("use_coupon_"))
async def use_coupon_start(callback: types.CallbackQuery, state: FSMContext, user: dict):
    """بدء استخدام كوبون"""
    lang = get_user_language(user)
    await state.set_state(OrderProcess.waiting_for_coupon)
    await callback.message.edit_text(
        get_text("coupon_prompt", lang) if "coupon_prompt" in TRANSLATIONS 
        else "🎟️ أدخل كود الكوبون:"
    )


@router.message(OrderProcess.waiting_for_coupon)
async def process_coupon(message: types.Message, state: FSMContext, user: dict):
    """معالجة كود الكوبون"""
    lang = get_user_language(user)
    coupon_code = message.text.strip().upper()
    data = await state.get_data()
    
    # التحقق من الكوبون
    is_valid, msg, discount = await db_manager.validate_coupon(coupon_code, user['telegram_id'], data['price_usd'])
    
    if not is_valid:
        return await message.answer(f"❌ {msg}")
    
    # حساب السعر الجديد
    new_price_usd = max(0, data['price_usd'] - discount)
    new_price_local = new_price_usd * data['rate']
    
    await state.update_data(
        price_usd=new_price_usd, 
        price_local=new_price_local, 
        coupon_code=coupon_code, 
        discount_amount=discount
    )
    await state.set_state(OrderProcess.confirming)
    
    product = await db_manager.get_product(data['selected_prod_id'])
    text = (
        f"✅ تم تطبيق الكوبون! خصم: {discount:.2f}$\n\n"
        f"⚠️ *تأكيد الطلب (بعد الخصم)*\n\n"
        f"📦 المنتج: {product['name']}\n"
        f"🆔 المعرف: `{data['player_id']}`\n"
        f"💰 السعر الأصلي: {data.get('original_price_usd', data['price_usd'] + discount):.2f}$\n"
        f"🎟️ الخصم: -{discount:.2f}$\n"
        f"💵 السعر النهائي: {new_price_local:,.0f} ل.س ({new_price_usd:.2f}$)\n\n"
        f"سيتم الخصم من رصيدك الداخلي عند التأكيد.\n"
        f"💰 رصيدك الحالي: {user['balance']:.2f}$"
    )
    await message.answer(text, reply_markup=get_order_confirm_keyboard(product['id'], lang), parse_mode="Markdown")


# ===== تأكيد الشراء =====
@router.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_purchase(callback: types.CallbackQuery, state: FSMContext, user: dict, bot: Bot):
    """تأكيد الشراء باستخدام OrderService"""
    data = await state.get_data()
    product_id = data['selected_prod_id']
    player_id = data['player_id']
    coupon_code = data.get('coupon_code')
    
    # إنشاء الطلب باستخدام OrderService
    success, message, order_id = await order_service.create_order(
        user_id=user['telegram_id'],
        product_id=product_id,
        player_id=player_id,
        payment_method_id=None,  # الدفع من الرصيد
        coupon_code=coupon_code
    )
    
    if success:
        product = await db_manager.get_product(product_id)
        await callback.message.edit_text(
            f"✅ تم إنشاء الطلب بنجاح!\n"
            f"📦 رقم الطلب: `#{order_id}`\n"
            f"💰 تم الخصم من رصيدك\n"
            f"⏳ جاري التنفيذ...",
            parse_mode="Markdown"
        )
        
        # إشعار الأدمن
        from config.settings import ADMIN_ID
        from utils.keyboards import get_admin_order_actions
        try:
            await bot.send_message(
                ADMIN_ID,
                f"🆕 *طلب جديد (مدفوع من الرصيد)*\n\n"
                f"🆔 رقم الطلب: `#{order_id}`\n"
                f"👤 المستخدم: @{user.get('username', 'N/A')} (`{user['telegram_id']}`)\n"
                f"📦 المنتج: {product['name']}\n"
                f"🆔 معرف اللاعب: `{player_id}`\n"
                f"💰 المبلغ: {data.get('price_usd', 0):.2f}$",
                reply_markup=get_admin_order_actions(order_id, OrderStatus.PAID),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
    else:
        await callback.answer(f"❌ {message}", show_alert=True)
    
    await state.clear()


# ===== شحن الرصيد =====
@router.message(F.text.in_(["💰 شحن رصيد", "💰 Add Balance"]))
@router.callback_query(F.data == "user_recharge_start")
async def start_recharge(event, state: FSMContext):
    """بدء عملية شحن الرصيد"""
    methods = await db_manager.get_payment_methods()
    if not methods:
        msg = "⚠️ لا توجد طرق شحن متاحة حالياً."
        if isinstance(event, types.Message):
            await event.answer(msg)
        else:
            await event.message.edit_text(msg)
        return

    text = "💰 *شحن رصيد الحساب*\n\nأدخل المبلغ الذي ترغب في شحنه بالدولار ($):"
    if isinstance(event, types.Message):
        await event.answer(text, parse_mode="Markdown")
    else:
        await event.message.edit_text(text, parse_mode="Markdown")
    
    await state.set_state(RechargeProcess.waiting_for_amount)


@router.message(RechargeProcess.waiting_for_amount)
async def recharge_amount(message: types.Message, state: FSMContext):
    """استقبال مبلغ الشحن"""
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        
        await state.update_data(amount=amount)
        
        methods = await db_manager.get_payment_methods()
        from utils.keyboards import get_payment_methods_keyboard
        await message.answer("💳 اختر وسيلة الدفع للتحويل:", reply_markup=get_payment_methods_keyboard(methods))
        await state.set_state(RechargeProcess.waiting_for_receipt)
    except ValueError:
        await message.answer("⚠️ يرجى إدخال مبلغ صحيح.")


@router.callback_query(F.data.startswith("pay_method_"), RechargeProcess.waiting_for_receipt)
async def recharge_method(callback: types.CallbackQuery, state: FSMContext):
    """اختيار طريقة الدفع"""
    method_id = int(callback.data.split("_")[2])
    method = await db_manager.get_payment_method(method_id)
    
    if not method:
        await callback.answer("❌ طريقة الدفع غير موجودة", show_alert=True)
        return
    
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    data = await state.get_data()
    local_amount = data['amount'] * rate
    
    await state.update_data(method_id=method_id, local_amount=local_amount)
    await callback.message.edit_text(
        f"💳 *{method['name']}*\n\n"
        f"{method['description']}\n\n"
        f"💵 المبلغ المطلوب: {local_amount:,.0f} ل.س\n"
        f"📸 يرجى إرسال صورة الإيصال الآن:",
        parse_mode="Markdown"
    )


@router.message(RechargeProcess.waiting_for_receipt, F.photo)
async def recharge_receipt(message: types.Message, state: FSMContext, bot: Bot):
    """استقبال إيصال الشحن"""
    data = await state.get_data()
    from config.settings import ADMIN_ID
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="✅ قبول", callback_data=f"admin_pay_approve_{message.from_user.id}_{data['amount']}"),
            types.InlineKeyboardButton(text="❌ رفض", callback_data=f"admin_pay_reject_{message.from_user.id}")
        ]
    ])
    
    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=(
            f"💰 *طلب شحن رصيد جديد*\n\n"
            f"👤 المستخدم: @{message.from_user.username or 'N/A'} (`{message.from_user.id}`)\n"
            f"💵 المبلغ: {data['amount']}$\n"
            f"🪙 ما يعادل: {data['local_amount']:,.0f} ل.س"
        ),
        reply_markup=builder,
        parse_mode="Markdown"
    )
    
    await message.answer("⏳ تم إرسال طلب الشحن للإدارة. سيتم إخطارك فور تأكيد الطلب.")
    await state.clear()


# ===== الدعم والحساب =====
@router.message(F.text.in_(["❓ الدعم", "❓ Support"]))
async def show_support(message: types.Message):
    """عرض معلومات الدعم"""
    support_msg = await db_manager.get_setting("support_message", "تواصل مع الدعم الفني.")
    await message.answer(f"❓ *الدعم الفني*\n\n{support_msg}", parse_mode="Markdown")


@router.message(F.text.in_(["👤 حسابي", "👤 My Account"]))
async def show_account(message: types.Message, user: dict):
    """عرض معلومات الحساب مع العملة المفضلة"""
    lang = get_user_language(user)
    currency = user.get('currency', 'USD')
    balance = user['balance']
    
    # تحويل الرصيد إذا كانت العملة ليرة سورية
    if currency == 'SYP':
        rate = float(await db_manager.get_setting('dollar_rate', '12500'))
        display_balance = f"{balance * rate:,.0f} ل.س"
    else:
        display_balance = f"{balance:.2f}$"
        
    text = (
        f"👤 *معلومات الحساب*\n\n"
        f"🆔 معرفك: `{message.from_user.id}`\n"
        f"💰 الرصيد الحالي: `{display_balance}`\n"
        f"🎖 الرتبة: `{user.get('role', 'USER')}`\n"
        f"💵 العملة المفضلة: `{currency}`\n"
        f"📅 انضممت في: `{user.get('created_at', 'N/A')}`"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💵 تغيير العملة", callback_data="select_currency"))
    builder.row(InlineKeyboardButton(text="🎟️ استخدام كوبون", callback_data="use_coupon_main"))
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "select_currency")
async def select_currency_menu(callback: types.CallbackQuery):
    """قائمة اختيار العملة"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇺🇸 دولار (USD)", callback_data="set_currency_USD"),
        InlineKeyboardButton(text="🇸🇾 ليرة سورية (SYP)", callback_data="set_currency_SYP")
    )
    await callback.message.edit_text("💵 اختر العملة التي تفضل عرض الأسعار بها:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("set_currency_"))
async def set_currency_execute(callback: types.CallbackQuery):
    """تنفيذ تغيير العملة"""
    currency = callback.data.split("_")[2]
    await db_manager.update_user_currency(callback.from_user.id, currency)
    await callback.answer(f"✅ تم تغيير العملة المفضلة إلى {currency}")
    # إعادة عرض الحساب
    user = await db_manager.get_user(callback.from_user.id)
    await show_account(callback.message, user)

@router.callback_query(F.data == "use_coupon_main")
async def use_coupon_prompt(callback: types.CallbackQuery, state: FSMContext):
    """طلب رمز الكوبون من المستخدم"""
    await state.set_state(OrderProcess.waiting_for_coupon_main)
    await callback.message.edit_text("🎟️ أرسل رمز الكوبون الذي تملكه لشحن رصيدك أو الحصول على خصم:")

@router.message(F.text, OrderProcess.waiting_for_coupon_main)
async def use_coupon_execute(message: types.Message, state: FSMContext):
    """تنفيذ استخدام الكوبون"""
    code = message.text.strip().upper()
    user_id = message.from_user.id
    
    # التحقق من الكوبون
    coupon = await db_manager.get_coupon(code)
    if not coupon or not coupon['is_active']:
        return await message.answer("❌ الكوبون غير صحيح أو منتهي الصلاحية.")
        
    if coupon['used_count'] >= coupon['max_uses']:
        return await message.answer("❌ تم استهلاك جميع استخدامات هذا الكوبون.")
        
    # هنا يمكن تحديد إذا كان الكوبون يعطي رصيداً مباشراً
    if coupon['type'] == 'FIXED':
        amount = coupon['value']
        success, new_bal = await db_manager.update_user_balance(
            user_id=user_id,
            amount=amount,
            log_type="COUPON",
            reason=f"استخدام كوبون: {code}"
        )
        if success:
            # تحديث عدد مرات استخدام الكوبون
            db = await db_manager.connect()
            await db.execute("UPDATE coupons SET used_count = used_count + 1 WHERE id = ?", (coupon['id'],))
            await db.commit()
            
            await message.answer(f"✅ تم استخدام الكوبون بنجاح! تم إضافة {amount}$ إلى رصيدك.")
            await state.clear()
        else:
            await message.answer(f"❌ حدث خطأ: {new_bal}")
    else:
        await message.answer("ℹ️ هذا الكوبون مخصص للخصم عند الشراء فقط، وليس للشحن المباشر.")
        await state.clear()


@router.message(F.text.in_(["📦 طلباتي", "📦 My Orders"]))
async def show_my_orders(message: types.Message, user: dict):
    """عرض طلبات المستخدم"""
    orders = await db_manager.get_user_orders(user['telegram_id'], limit=10)
    
    if not orders:
        return await message.answer("📭 ليس لديك طلبات.")
    
    text = "📦 *آخر طلباتك:*\n\n"
    for ord in orders:
        status_icon = {
            OrderStatus.NEW: "🆕",
            OrderStatus.PENDING_PAYMENT: "⏳",
            OrderStatus.PAID: "💰",
            OrderStatus.IN_PROGRESS: "⚙️",
            OrderStatus.COMPLETED: "✅",
            OrderStatus.FAILED: "❌",
            OrderStatus.CANCELED: "🚫"
        }.get(ord['status'], "❓")
        
        text += (
            f"🔹 #{ord['id']} | {ord['product_name']}\n"
            f"{status_icon} الحالة: `{ord['status']}`\n"
            f"💰 السعر: {ord['price_local']:,.0f} ل.س\n\n"
        )
    
    await message.answer(text, parse_mode="Markdown")


@router.message(F.text == "🌐 Language / اللغة")
async def change_language_start(message: types.Message):
    """تغيير اللغة"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
    )
    await message.answer(
        "🌐 *اختر اللغة / Choose Language*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
