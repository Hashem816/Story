from aiogram import Router, F, types, Bot
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_main_menu, get_categories_keyboard, get_products_keyboard, get_order_confirm_keyboard
from utils.translations import get_text, get_user_language, TRANSLATIONS
from config.settings import OrderStatus, UserRole
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()

class OrderProcess(StatesGroup):
    waiting_for_player_id = State()
    confirming = State()
    waiting_for_receipt = State()

class RechargeProcess(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()

@router.message(CommandStart())
async def cmd_start(message: types.Message, user_role: str, user: dict):
    """رسالة الترحيب مع اختيار اللغة للمستخدمين الجدد"""
    lang = get_user_language(user)
    
    # إذا كان المستخدم جديد، عرض اختيار اللغة
    if not user.get('language'):
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
        get_text("welcome", lang),
        reply_markup=get_main_menu(user_role, lang)
    )

@router.message(F.text.in_(["🛒 المتجر", "🛒 Store"]))
async def show_categories(message: types.Message, user: dict):
    lang = get_user_language(user)
    if await db_manager.has_open_order(user['telegram_id']):
        return await message.answer(get_text("error_open_order", lang) if "error_open_order" in TRANSLATIONS else "⚠️ لديك طلب مفتوح بالفعل، يرجى انتظاره.")
    categories = await db_manager.get_categories()
    await message.answer(get_text("choose_category", lang) if "choose_category" in TRANSLATIONS else "📁 اختر القسم:", reply_markup=get_categories_keyboard(categories))

@router.callback_query(F.data == "back_to_categories")
async def back_to_categories(callback: types.CallbackQuery):
    categories = await db_manager.get_categories()
    await callback.message.edit_text("📁 اختر القسم:", reply_markup=get_categories_keyboard(categories))

@router.callback_query(F.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    products = await db_manager.get_products(category_id=cat_id)
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    await callback.message.edit_text("📦 اختر المنتج:", reply_markup=get_products_keyboard(products, cat_id, rate))

@router.callback_query(F.data.startswith("prod_"))
async def product_details(callback: types.CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[1])
    product = await db_manager.get_product(prod_id)
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    local_price = product['price_usd'] * rate
    
    await state.update_data(selected_prod_id=prod_id, price_usd=product['price_usd'], price_local=local_price, rate=rate)
    await state.set_state(OrderProcess.waiting_for_player_id)
    
    text = (
        f"📝 *{product['name']}*\n\n"
        f"💰 السعر: {product['price_usd']}$\n"
        f"💵 السعر بالليرة: {local_price:,.0f} ل.س\n"
        f"📊 سعر الصرف: {rate} ل.س\n\n"
        f"🆔 أدخل معرف اللاعب (Player ID):"
    )
    await callback.message.edit_text(text, parse_mode="Markdown")

@router.message(OrderProcess.waiting_for_player_id)
async def process_player_id(message: types.Message, state: FSMContext):
    await state.update_data(player_id=message.text)
    await state.set_state(OrderProcess.confirming)
    data = await state.get_data()
    product = await db_manager.get_product(data['selected_prod_id'])
    
    text = (
        f"⚠️ *تأكيد الطلب*\n\n"
        f"📦 المنتج: {product['name']}\n"
        f"🆔 المعرف: `{message.text}`\n"
        f"💰 السعر: {data['price_local']:,.0f} ل.س\n\n"
        f"سيتم الخصم من رصيدك الداخلي عند التأكيد."
    )
    await message.answer(text, reply_markup=get_order_confirm_keyboard(product['id']), parse_mode="Markdown")

@router.callback_query(F.data.startswith("confirm_buy_"))
async def confirm_purchase(callback: types.CallbackQuery, state: FSMContext, user: dict, bot: Bot):
    data = await state.get_data()
    # التحقق من الرصيد
    if user['balance'] < data['price_usd']:
        return await callback.message.edit_text(
            f"❌ رصيدك غير كافٍ!\n\n"
            f"💰 رصيدك: {user['balance']:.2f}$\n"
            f"💵 المبلغ المطلوب: {data['price_usd']}$\n\n"
            f"يرجى شحن رصيدك أولاً.",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="💰 شحن رصيد", callback_data="user_recharge_start")]])
        )
    
    # الخصم من الرصيد
    success, result = await db_manager.update_user_balance(user['telegram_id'], -data['price_usd'], "PURCHASE", reason=f"شراء منتج: {data['selected_prod_id']}")
    
    if success:
        order_id = await db_manager.create_order(
            user['telegram_id'], data['selected_prod_id'], data['player_id'], 
            data['price_usd'], data['price_local'], data['rate'], 
            status=OrderStatus.IN_PROGRESS # مدفوع وجاري التنفيذ
        )
        
        await callback.message.edit_text(f"✅ تم الدفع بنجاح من رصيدك!\n📦 رقم الطلب: `#{order_id}`\nجاري التنفيذ الآن...")
        
        # إشعار الأدمن
        from config.settings import ADMIN_ID
        from utils.keyboards import get_admin_order_actions
        await bot.send_message(
            ADMIN_ID,
            f"🆕 *طلب جديد (مدفوع من الرصيد)*\n\n"
            f"🆔 رقم الطلب: `#{order_id}`\n"
            f"👤 المستخدم: @{user['username']}\n"
            f"💰 المبلغ: {data['price_usd']}$\n"
            f"🆔 المعرف: `{data['player_id']}`",
            reply_markup=get_admin_order_actions(order_id, OrderStatus.IN_PROGRESS),
            parse_mode="Markdown"
        )
    else:
        await callback.answer(f"❌ خطأ: {result}", show_alert=True)
    
    await state.clear()

# --- شحن الرصيد ---
@router.message(F.text.in_(["💰 شحن رصيد", "💰 Add Balance"]))
@router.callback_query(F.data == "user_recharge_start")
async def start_recharge(event, state: FSMContext):
    methods = await db_manager.get_payment_methods()
    if not methods:
        msg = "⚠️ لا توجد طرق شحن متاحة حالياً."
        if isinstance(event, types.Message): await event.answer(msg)
        else: await event.message.edit_text(msg)
        return

    text = "💰 *شحن رصيد الحساب*\n\nأدخل المبلغ الذي ترغب في شحنه بالدولار ($):"
    if isinstance(event, types.Message): await event.answer(text, parse_mode="Markdown")
    else: await event.message.edit_text(text, parse_mode="Markdown")
    await state.set_state(RechargeProcess.waiting_for_amount)

@router.message(RechargeProcess.waiting_for_amount)
async def recharge_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0: raise ValueError
        await state.update_data(amount=amount)
        
        methods = await db_manager.get_payment_methods()
        from utils.keyboards import get_payment_methods_keyboard
        await message.answer("💳 اختر وسيلة الدفع للتحويل:", reply_markup=get_payment_methods_keyboard(methods))
        await state.set_state(RechargeProcess.waiting_for_receipt)
    except ValueError:
        await message.answer("⚠️ يرجى إدخال مبلغ صحيح.")

@router.callback_query(F.data.startswith("pay_method_"), RechargeProcess.waiting_for_receipt)
async def recharge_method(callback: types.CallbackQuery, state: FSMContext):
    method_id = int(callback.data.split("_")[2])
    method = await db_manager.get_payment_method(method_id)
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
        caption=f"💰 *طلب شحن رصيد جديد*\n\n👤 المستخدم: @{message.from_user.username} (`{message.from_user.id}`)\n💵 المبلغ: {data['amount']}$\n🪙 ما يعادل: {data['local_amount']:,.0f} ل.س",
        reply_markup=builder,
        parse_mode="Markdown"
    )
    
    await message.answer("⏳ تم إرسال طلب الشحن للإدارة. سيتم إخطارك فور تأكيد الطلب.")
    await state.clear()

@router.message(F.text.in_(["❓ الدعم", "❓ Support"]))
async def show_support(message: types.Message):
    support_msg = await db_manager.get_setting("support_message", "تواصل مع الدعم الفني.")
    await message.answer(f"❓ *الدعم الفني*\n\n{support_msg}", parse_mode="Markdown")

@router.message(F.text.in_(["👤 حسابي", "👤 My Account"]))
async def show_account(message: types.Message, user: dict):
    await message.answer(
        f"👤 *معلومات الحساب*\n\n🆔 معرفك: `{user['telegram_id']}`\n💰 الرصيد: `{user['balance']:.2f}$`",
        parse_mode="Markdown"
    )

@router.message(F.text.in_(["📦 طلباتي", "📦 My Orders"]))
async def show_my_orders(message: types.Message, user: dict):
    db = await db_manager.connect()
    cursor = await db.execute("""
        SELECT o.id, o.status, o.price_local, p.name 
        FROM orders o 
        JOIN products p ON o.product_id = p.id 
        WHERE o.user_id = ? 
        ORDER BY o.created_at DESC LIMIT 10
    """, (user['telegram_id'],))
    orders = await cursor.fetchall()
    
    if not orders: return await message.answer("📭 ليس لديك طلبات.")
    
    text = "📦 *آخر طلباتك:*\n\n"
    for ord in orders:
        text += f"🔹 #{ord['id']} | {ord['name']}\n📍 الحالة: `{ord['status']}`\n💰 السعر: {ord['price_local']:,.0f} ل.س\n\n"
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "🌐 Language / اللغة")
async def change_language_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
    )
    await message.answer("🌐 اختر لغتك المفضلة / Choose your language:", reply_markup=builder.as_markup())
