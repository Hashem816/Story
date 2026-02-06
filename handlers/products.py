"""
نظام إدارة المنتجات المحسّن - CRUD كامل
التحسينات:
- إضافة تعديل المنتجات (Update)
- إضافة حذف المنتجات (Delete)
- إضافة FSM لتعديل المنتجات
- التأكد من وجود product_id في callback_data
"""

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_categories_keyboard, get_products_keyboard
from config.settings import UserRole
import logging

router = Router()
logger = logging.getLogger(__name__)

# ===== FSM States =====
class ProductWizard(StatesGroup):
    # إضافة قسم
    waiting_for_cat_name = State()
    
    # إضافة منتج
    waiting_for_prod_name = State()
    waiting_for_prod_desc = State()
    waiting_for_prod_price = State()
    waiting_for_prod_provider = State()
    waiting_for_prod_variation = State()
    
    # تعديل منتج
    edit_waiting_for_field = State()
    edit_waiting_for_name = State()
    edit_waiting_for_desc = State()
    edit_waiting_for_price = State()
    edit_waiting_for_type = State()
    edit_waiting_for_provider = State()
    edit_waiting_for_variation = State()

    # إدارة المزودين
    waiting_for_provider_name = State()
    waiting_for_provider_url = State()
    waiting_for_provider_key = State()


# ===== إدارة الأقسام =====
@router.callback_query(F.data == "admin_products")
async def admin_products_main(callback: types.CallbackQuery, is_operator: bool):
    """القائمة الرئيسية لإدارة الأقسام والمنتجات"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    categories = await db_manager.get_categories(only_active=False)
    await callback.message.edit_text(
        "🛒 *إدارة الأقسام والمنتجات*\n\nاختر قسماً لعرض منتجاته أو إدارتها:", 
        reply_markup=get_categories_keyboard(categories, is_admin=True), 
        parse_mode="Markdown"
    )
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="VIEW_PRODUCTS_PANEL",
        target_type="PRODUCT"
    )


@router.callback_query(F.data == "admin_cat_add")
async def admin_cat_add_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء إضافة قسم جديد"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    await state.set_state(ProductWizard.waiting_for_cat_name)
    await callback.message.edit_text(
        "📂 أدخل اسم القسم الجديد:", 
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_products")]]
        )
    )


@router.message(ProductWizard.waiting_for_cat_name)
async def admin_cat_add_finish(message: types.Message, state: FSMContext, is_operator: bool):
    """إنهاء إضافة قسم جديد"""
    if not is_operator:
        return
    
    category_name = message.text.strip()
    await db_manager.add_category(category_name)
    await state.clear()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="CREATE_CATEGORY",
        target_type="CATEGORY",
        details=f"إنشاء قسم: {category_name}"
    )
    
    await message.answer(f"✅ تم إضافة القسم: {category_name}")
    
    categories = await db_manager.get_categories(only_active=False)
    await message.answer(
        "🛒 إدارة الأقسام", 
        reply_markup=get_categories_keyboard(categories, is_admin=True)
    )


@router.callback_query(F.data.startswith("admin_cat_view_"))
async def admin_cat_view(callback: types.CallbackQuery, is_operator: bool):
    """عرض منتجات قسم معين"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    cat_id = int(callback.data.split("_")[3])
    products = await db_manager.get_products(category_id=cat_id, only_active=False)
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    
    await callback.message.edit_text(
        f"📦 *منتجات القسم:*", 
        reply_markup=get_products_keyboard(products, cat_id, rate, is_admin=True), 
        parse_mode="Markdown"
    )


# ===== إضافة منتج =====
@router.callback_query(F.data.startswith("admin_prod_add_"))
async def admin_prod_add_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء إضافة منتج جديد"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    cat_id = int(callback.data.split("_")[3])
    await state.update_data(cat_id=cat_id)
    await state.set_state(ProductWizard.waiting_for_prod_name)
    
    await callback.message.edit_text(
        "📦 أدخل اسم المنتج الجديد:", 
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_cat_view_{cat_id}")]]
        )
    )


@router.message(ProductWizard.waiting_for_prod_name)
async def admin_prod_name(message: types.Message, state: FSMContext):
    """استقبال اسم المنتج"""
    await state.update_data(name=message.text.strip())
    await state.set_state(ProductWizard.waiting_for_prod_desc)
    await message.answer("📝 أدخل وصف المنتج:")


@router.message(ProductWizard.waiting_for_prod_desc)
async def admin_prod_desc(message: types.Message, state: FSMContext):
    """استقبال وصف المنتج"""
    await state.update_data(desc=message.text.strip())
    await state.set_state(ProductWizard.waiting_for_prod_price)
    await message.answer("💰 أدخل سعر المنتج بالدولار (مثلاً: 5.5):")


@router.message(ProductWizard.waiting_for_prod_price)
async def admin_prod_price(message: types.Message, state: FSMContext):
    """استقبال سعر المنتج واختيار نوع التنفيذ"""
    try:
        price = float(message.text.strip())
        if price <= 0:
            await message.answer("⚠️ السعر يجب أن يكون أكبر من صفر.")
            return
        
        await state.update_data(price=price)
        
        builder = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="🤖 تلقائي (API)", callback_data="admin_prod_type_AUTO")],
            [types.InlineKeyboardButton(text="👤 يدوي", callback_data="admin_prod_type_MANUAL")],
            [types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_products")]
        ])
        
        await message.answer("⚙️ اختر نوع تنفيذ المنتج:", reply_markup=builder)
    except ValueError:
        await message.answer("⚠️ يرجى إدخال سعر صحيح (رقم).")

@router.callback_query(F.data.startswith("admin_prod_type_"))
async def admin_prod_type_select(callback: types.CallbackQuery, state: FSMContext):
    """اختيار نوع المنتج (تلقائي/يدوي)"""
    prod_type = callback.data.split("_")[3]
    await state.update_data(type=prod_type)
    
    if prod_type == "AUTO":
        providers = await db_manager.get_providers()
        if not providers:
            await callback.answer("⚠️ لا يوجد مزودين مضافين. سيتم تحويل المنتج ليدوي.", show_alert=True)
            await state.update_data(type="MANUAL")
            await finish_product_creation(callback.message, state)
        else:
            builder = types.InlineKeyboardBuilder()
            for p in providers:
                builder.row(types.InlineKeyboardButton(text=p['name'], callback_data=f"admin_prod_prov_{p['id']}"))
            builder.row(types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_products"))
            await callback.message.edit_text("🔌 اختر المزود:", reply_markup=builder.as_markup())
    else:
        await finish_product_creation(callback.message, state)

@router.callback_query(F.data.startswith("admin_prod_prov_"))
async def admin_prod_provider_select(callback: types.CallbackQuery, state: FSMContext):
    """اختيار المزود للمنتج التلقائي"""
    provider_id = int(callback.data.split("_")[3])
    await state.update_data(provider_id=provider_id)
    await state.set_state(ProductWizard.waiting_for_prod_variation)
    await callback.message.edit_text("🆔 أدخل معرف المنتج لدى المزود (Variation ID):")

@router.message(ProductWizard.waiting_for_prod_variation)
async def admin_prod_variation_finish(message: types.Message, state: FSMContext):
    """استقبال معرف المنتج لدى المزود وإنهاء الإضافة"""
    await state.update_data(variation_id=message.text.strip())
    await finish_product_creation(message, state)

async def finish_product_creation(message_or_callback, state: FSMContext):
    """دالة مساعدة لإنهاء إضافة المنتج"""
    data = await state.get_data()
    user_id = message_or_callback.from_user.id
    
    await db_manager.add_product(
        category_id=data['cat_id'],
        name=data['name'],
        description=data['desc'],
        price_usd=data['price'],
        provider_id=data.get('provider_id'),
        variation_id=data.get('variation_id'),
        type=data.get('type', 'MANUAL')
    )
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=user_id,
        action="CREATE_PRODUCT",
        target_type="PRODUCT",
        details=f"إنشاء منتج: {data['name']} - {data['price']}$ ({data.get('type')})"
    )
    
    await state.clear()
    msg_text = f"✅ تم إضافة المنتج: {data['name']}"
    
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(msg_text)
    else:
        await message_or_callback.message.answer(msg_text)
    
    products = await db_manager.get_products(category_id=data['cat_id'], only_active=False)
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    
    reply_markup = get_products_keyboard(products, data['cat_id'], rate, is_admin=True)
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer("📦 قائمة المنتجات", reply_markup=reply_markup)
    else:
        await message_or_callback.message.edit_text("📦 قائمة المنتجات", reply_markup=reply_markup)


# ===== عرض تفاصيل منتج =====
@router.callback_query(F.data.startswith("admin_prod_view_"))
async def admin_prod_view(callback: types.CallbackQuery, is_operator: bool):
    """عرض تفاصيل منتج مع خيارات التعديل والحذف"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    product_id = int(callback.data.split("_")[3])
    product = await db_manager.get_product(product_id)
    
    if not product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return
    
    status = "✅ نشط" if product['is_active'] else "❌ معطل"
    type_text = {"MANUAL": "يدوي", "AUTO": "تلقائي (API)", "DISABLED": "معطل"}.get(product['type'], product['type'])
    
    text = (
        f"📦 *تفاصيل المنتج*\n\n"
        f"الاسم: `{product['name']}`\n"
        f"الوصف: `{product['description']}`\n"
        f"السعر: `{product['price_usd']}$`\n"
        f"النوع: `{type_text}`\n"
        f"الحالة: {status}\n"
    )
    
    if product['type'] == "AUTO":
        provider = await db_manager.get_provider(product['provider_id']) if product.get('provider_id') else None
        prov_name = provider['name'] if provider else "غير محدد"
        text += f"المزود: `{prov_name}`\n"
        text += f"معرف المزود: `{product.get('variation_id', 'N/A')}`\n"
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✏️ تعديل البيانات", callback_data=f"admin_prod_edit_{product_id}")],
        [types.InlineKeyboardButton(text="🔄 تغيير الحالة", callback_data=f"admin_prod_toggle_{product_id}")],
        [types.InlineKeyboardButton(text="🗑 حذف", callback_data=f"admin_prod_delete_{product_id}")],
        [types.InlineKeyboardButton(text="🔙 عودة", callback_data=f"admin_cat_view_{product['category_id']}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")


# ===== تعديل منتج =====
@router.callback_query(F.data.startswith("admin_prod_edit_"))
async def admin_prod_edit_menu(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """قائمة تعديل المنتج"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    product_id = int(callback.data.split("_")[3])
    product = await db_manager.get_product(product_id)
    
    if not product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return
    
    await state.update_data(product_id=product_id, category_id=product['category_id'])
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📝 تعديل الاسم", callback_data=f"admin_prod_edit_name_{product_id}"))
    builder.row(types.InlineKeyboardButton(text="📄 تعديل الوصف", callback_data=f"admin_prod_edit_desc_{product_id}"))
    builder.row(types.InlineKeyboardButton(text="💰 تعديل السعر", callback_data=f"admin_prod_edit_price_{product_id}"))
    builder.row(types.InlineKeyboardButton(text="⚙️ تعديل النوع", callback_data=f"admin_prod_edit_type_{product_id}"))
    
    if product['type'] == "AUTO":
        builder.row(types.InlineKeyboardButton(text="🔌 تعديل المزود", callback_data=f"admin_prod_edit_prov_{product_id}"))
        builder.row(types.InlineKeyboardButton(text="🆔 تعديل معرف المزود", callback_data=f"admin_prod_edit_var_{product_id}"))
        
    builder.row(types.InlineKeyboardButton(text="🔙 عودة", callback_data=f"admin_prod_view_{product_id}"))
    
    builder = builder.as_markup()
    
    await callback.message.edit_text(
        f"✏️ *تعديل المنتج: {product['name']}*\n\nاختر ما تريد تعديله:",
        reply_markup=builder,
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("admin_prod_edit_name_"))
async def admin_prod_edit_name_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء تعديل اسم المنتج"""
    if not is_operator:
        return
    
    product_id = int(callback.data.split("_")[4])
    await state.update_data(product_id=product_id)
    await state.set_state(ProductWizard.edit_waiting_for_name)
    
    await callback.message.edit_text(
        "📝 أدخل الاسم الجديد للمنتج:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_prod_edit_{product_id}")]]
        )
    )


@router.message(ProductWizard.edit_waiting_for_name)
async def admin_prod_edit_name_finish(message: types.Message, state: FSMContext, is_operator: bool):
    """إنهاء تعديل اسم المنتج"""
    if not is_operator:
        return
    
    data = await state.get_data()
    product_id = data['product_id']
    new_name = message.text.strip()
    
    db = await db_manager.connect()
    await db.execute("UPDATE products SET name = ? WHERE id = ?", (new_name, product_id))
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="UPDATE_PRODUCT",
        target_type="PRODUCT",
        target_id=product_id,
        details=f"تعديل اسم المنتج إلى: {new_name}"
    )
    
    await state.clear()
    await message.answer(f"✅ تم تحديث اسم المنتج إلى: {new_name}")
    
    # العودة لعرض المنتج
    product = await db_manager.get_product(product_id)
    await admin_prod_view(types.CallbackQuery(
        id="dummy",
        from_user=message.from_user,
        data=f"admin_prod_view_{product_id}",
        chat_instance="dummy",
        message=message
    ), is_operator)


@router.callback_query(F.data.startswith("admin_prod_edit_desc_"))
async def admin_prod_edit_desc_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء تعديل وصف المنتج"""
    if not is_operator:
        return
    
    product_id = int(callback.data.split("_")[4])
    await state.update_data(product_id=product_id)
    await state.set_state(ProductWizard.edit_waiting_for_desc)
    
    await callback.message.edit_text(
        "📄 أدخل الوصف الجديد للمنتج:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_prod_edit_{product_id}")]]
        )
    )


@router.message(ProductWizard.edit_waiting_for_desc)
async def admin_prod_edit_desc_finish(message: types.Message, state: FSMContext, is_operator: bool):
    """إنهاء تعديل وصف المنتج"""
    if not is_operator:
        return
    
    data = await state.get_data()
    product_id = data['product_id']
    new_desc = message.text.strip()
    
    db = await db_manager.connect()
    await db.execute("UPDATE products SET description = ? WHERE id = ?", (new_desc, product_id))
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="UPDATE_PRODUCT",
        target_type="PRODUCT",
        target_id=product_id,
        details=f"تعديل وصف المنتج"
    )
    
    await state.clear()
    await message.answer(f"✅ تم تحديث وصف المنتج")


@router.callback_query(F.data.startswith("admin_prod_edit_price_"))
async def admin_prod_edit_price_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء تعديل سعر المنتج"""
    if not is_operator:
        return
    
    product_id = int(callback.data.split("_")[4])
    await state.update_data(product_id=product_id)
    await state.set_state(ProductWizard.edit_waiting_for_price)
    
    await callback.message.edit_text(
        "💰 أدخل السعر الجديد بالدولار:",
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_prod_edit_{product_id}")]]
        )
    )


@router.message(ProductWizard.edit_waiting_for_price)
async def admin_prod_edit_price_finish(message: types.Message, state: FSMContext, is_operator: bool):
    """إنهاء تعديل سعر المنتج"""
    if not is_operator:
        return
    
    try:
        new_price = float(message.text.strip())
        
        if new_price <= 0:
            await message.answer("⚠️ السعر يجب أن يكون أكبر من صفر.")
            return
        
        data = await state.get_data()
        product_id = data['product_id']
        
        db = await db_manager.connect()
        await db.execute("UPDATE products SET price_usd = ? WHERE id = ?", (new_price, product_id))
        await db.commit()
        
        # تسجيل العملية
        await db_manager.log_admin_action(
            admin_id=message.from_user.id,
            action="UPDATE_PRODUCT",
            target_type="PRODUCT",
            target_id=product_id,
            details=f"تعديل سعر المنتج إلى: {new_price}$"
        )
        
        await state.clear()
        await message.answer(f"✅ تم تحديث سعر المنتج إلى: {new_price}$")
        
    except ValueError:
        await message.answer("⚠️ يرجى إدخال سعر صحيح (رقم).")


@router.callback_query(F.data.startswith("admin_prod_edit_type_"))
async def admin_prod_edit_type_menu(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """قائمة تعديل نوع المنتج"""
    if not is_operator:
        return
    
    product_id = int(callback.data.split("_")[4])
    await state.update_data(product_id=product_id)
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🤖 تلقائي", callback_data=f"admin_prod_settype_AUTOMATIC_{product_id}")],
        [types.InlineKeyboardButton(text="👤 يدوي", callback_data=f"admin_prod_settype_MANUAL_{product_id}")],
        [types.InlineKeyboardButton(text="❌ معطل", callback_data=f"admin_prod_settype_DISABLED_{product_id}")],
        [types.InlineKeyboardButton(text="🔙 عودة", callback_data=f"admin_prod_edit_{product_id}")]
    ])
    
    await callback.message.edit_text(
        "⚙️ اختر نوع المنتج:",
        reply_markup=builder
    )


@router.callback_query(F.data.startswith("admin_prod_settype_"))
async def admin_prod_set_type(callback: types.CallbackQuery, is_operator: bool):
    """تعيين نوع المنتج"""
    if not is_operator:
        return
    
    parts = callback.data.split("_")
    new_type = parts[3]
    product_id = int(parts[4])
    
    db = await db_manager.connect()
    await db.execute("UPDATE products SET type = ? WHERE id = ?", (new_type, product_id))
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="UPDATE_PRODUCT",
        target_type="PRODUCT",
        target_id=product_id,
        details=f"تعديل نوع المنتج إلى: {new_type}"
    )
    
    await callback.answer(f"✅ تم تحديث نوع المنتج إلى: {new_type}")
    
    # العودة لعرض المنتج
    await admin_prod_view(callback, is_operator)


# ===== تغيير حالة منتج =====
@router.callback_query(F.data.startswith("admin_prod_toggle_"))
async def admin_prod_toggle(callback: types.CallbackQuery, is_operator: bool):
    """تفعيل/تعطيل منتج"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    product_id = int(callback.data.split("_")[3])
    product = await db_manager.get_product(product_id)
    
    if not product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return
    
    new_status = 0 if product['is_active'] else 1
    
    db = await db_manager.connect()
    await db.execute("UPDATE products SET is_active = ? WHERE id = ?", (new_status, product_id))
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="TOGGLE_PRODUCT",
        target_type="PRODUCT",
        target_id=product_id,
        details=f"تغيير حالة المنتج إلى: {'نشط' if new_status else 'معطل'}"
    )
    
    await callback.answer(f"✅ تم {'تفعيل' if new_status else 'تعطيل'} المنتج")
    
    # العودة لعرض المنتج
    await admin_prod_view(callback, is_operator)


# ===== حذف منتج =====
@router.callback_query(F.data.startswith("admin_prod_delete_"))
async def admin_prod_delete_confirm(callback: types.CallbackQuery, is_operator: bool):
    """تأكيد حذف منتج"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    product_id = int(callback.data.split("_")[3])
    product = await db_manager.get_product(product_id)
    
    if not product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ نعم، احذف", callback_data=f"admin_prod_delete_confirm_{product_id}")],
        [types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_prod_view_{product_id}")]
    ])
    
    await callback.message.edit_text(
        f"⚠️ *تأكيد الحذف*\n\nهل أنت متأكد من حذف المنتج:\n`{product['name']}`؟\n\n"
        f"⚠️ تحذير: سيتم حذف المنتج نهائياً!",
        reply_markup=builder,
        parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("admin_prod_delete_confirm_"))
async def admin_prod_delete_execute(callback: types.CallbackQuery, is_operator: bool):
    """تنفيذ حذف منتج"""
    if not is_operator:
        await callback.answer("⛔️ غير مصرح لك", show_alert=True)
        return
    
    product_id = int(callback.data.split("_")[4])
    product = await db_manager.get_product(product_id)
    
    if not product:
        await callback.answer("❌ المنتج غير موجود", show_alert=True)
        return
    
    category_id = product['category_id']
    product_name = product['name']
    
    # حذف المنتج
    db = await db_manager.connect()
    await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
    await db.commit()
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="DELETE_PRODUCT",
        target_type="PRODUCT",
        target_id=product_id,
        details=f"حذف المنتج: {product_name}"
    )
    
    await callback.answer(f"✅ تم حذف المنتج: {product_name}", show_alert=True)
    
    # العودة لقائمة المنتجات
    products = await db_manager.get_products(category_id=category_id, only_active=False)
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    
    await callback.message.edit_text(
        f"📦 *منتجات القسم:*", 
        reply_markup=get_products_keyboard(products, category_id, rate, is_admin=True), 
        parse_mode="Markdown"
    )

# ===== تعديل المزود والمعرف (للمنتجات التلقائية) =====
@router.callback_query(F.data.startswith("admin_prod_edit_prov_"))
async def admin_prod_edit_prov_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء تعديل مزود المنتج"""
    if not is_operator: return
    
    product_id = int(callback.data.split("_")[4])
    await state.update_data(product_id=product_id)
    
    providers = await db_manager.get_providers()
    builder = InlineKeyboardBuilder()
    for p in providers:
        builder.row(types.InlineKeyboardButton(text=p['name'], callback_data=f"admin_prod_setprov_{p['id']}"))
    builder.row(types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_prod_edit_{product_id}"))
    
    await callback.message.edit_text("🔌 اختر المزود الجديد:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("admin_prod_setprov_"))
async def admin_prod_set_provider(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """تعيين المزود الجديد للمنتج"""
    if not is_operator: return
    
    provider_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    product_id = data['product_id']
    
    db = await db_manager.connect()
    await db.execute("UPDATE products SET provider_id = ? WHERE id = ?", (provider_id, product_id))
    await db.commit()
    
    await callback.answer("✅ تم تحديث المزود")
    await state.clear()
    await admin_prod_view(callback, is_operator)

@router.callback_query(F.data.startswith("admin_prod_edit_var_"))
async def admin_prod_edit_var_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    """بدء تعديل معرف المنتج لدى المزود"""
    if not is_operator: return
    
    product_id = int(callback.data.split("_")[4])
    await state.update_data(product_id=product_id)
    await state.set_state(ProductWizard.edit_waiting_for_variation)
    
    await callback.message.edit_text(
        "🆔 أدخل معرف المنتج الجديد لدى المزود (Variation ID):",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_prod_edit_{product_id}")]
        ])
    )

@router.message(ProductWizard.edit_waiting_for_variation)
async def admin_prod_edit_var_finish(message: types.Message, state: FSMContext, is_operator: bool):
    """إنهاء تعديل معرف المنتج لدى المزود"""
    if not is_operator: return
    
    data = await state.get_data()
    product_id = data['product_id']
    new_var = message.text.strip()
    
    db = await db_manager.connect()
    await db.execute("UPDATE products SET variation_id = ? WHERE id = ?", (new_var, product_id))
    await db.commit()
    
    await state.clear()
    await message.answer(f"✅ تم تحديث معرف المزود إلى: {new_var}")
    
    # العودة لعرض المنتج
    product = await db_manager.get_product(product_id)
    await admin_prod_view(types.CallbackQuery(
        id="dummy", from_user=message.from_user, data=f"admin_prod_view_{product_id}",
        chat_instance="dummy", message=message
    ), is_operator)
