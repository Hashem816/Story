from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_categories_keyboard, get_products_keyboard
from config.settings import UserRole

router = Router()

class ProductWizard(StatesGroup):
    waiting_for_cat_name = State()
    waiting_for_prod_name = State()
    waiting_for_prod_desc = State()
    waiting_for_prod_price = State()

@router.callback_query(F.data == "admin_products")
async def admin_products_main(callback: types.CallbackQuery, is_operator: bool):
    if not is_operator: return
    categories = await db_manager.get_categories(only_active=False)
    await callback.message.edit_text("🛒 *إدارة الأقسام والمنتجات*\nاختر قسماً لعرض منتجاته أو إدارتها:", 
                                     reply_markup=get_categories_keyboard(categories, is_admin=True), 
                                     parse_mode="Markdown")

@router.callback_query(F.data == "admin_cat_add")
async def admin_cat_add_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    if not is_operator: return
    await state.set_state(ProductWizard.waiting_for_cat_name)
    await callback.message.edit_text("📂 أدخل اسم القسم الجديد:", 
                                     reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_products")]]))

@router.message(ProductWizard.waiting_for_cat_name)
async def admin_cat_add_finish(message: types.Message, state: FSMContext, is_operator: bool):
    if not is_operator: return
    await db_manager.add_category(message.text)
    await state.clear()
    await message.answer(f"✅ تم إضافة القسم: {message.text}")
    categories = await db_manager.get_categories(only_active=False)
    await message.answer("🛒 إدارة الأقسام", reply_markup=get_categories_keyboard(categories, is_admin=True))

@router.callback_query(F.data.startswith("admin_cat_view_"))
async def admin_cat_view(callback: types.CallbackQuery, is_operator: bool):
    if not is_operator: return
    cat_id = int(callback.data.split("_")[3])
    products = await db_manager.get_products(category_id=cat_id, only_active=False)
    rate = int(await db_manager.get_setting("dollar_rate", "12500"))
    await callback.message.edit_text(f"📦 *منتجات القسم:*", 
                                     reply_markup=get_products_keyboard(products, cat_id, rate, is_admin=True), 
                                     parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_prod_add_"))
async def admin_prod_add_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    if not is_operator: return
    cat_id = int(callback.data.split("_")[3])
    await state.update_data(cat_id=cat_id)
    await state.set_state(ProductWizard.waiting_for_prod_name)
    await callback.message.edit_text("📦 أدخل اسم المنتج الجديد:", 
                                     reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data=f"admin_cat_view_{cat_id}")]]))

@router.message(ProductWizard.waiting_for_prod_name)
async def admin_prod_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(ProductWizard.waiting_for_prod_desc)
    await message.answer("📝 أدخل وصف المنتج:")

@router.message(ProductWizard.waiting_for_prod_desc)
async def admin_prod_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text)
    await state.set_state(ProductWizard.waiting_for_prod_price)
    await message.answer("💰 أدخل سعر المنتج بالدولار (مثلاً: 5.5):")

@router.message(ProductWizard.waiting_for_prod_price)
async def admin_prod_price(message: types.Message, state: FSMContext, is_operator: bool):
    if not is_operator: return
    try:
        price = float(message.text)
        data = await state.get_data()
        await db_manager.add_product(data['cat_id'], data['name'], data['desc'], price)
        await state.clear()
        await message.answer(f"✅ تم إضافة المنتج: {data['name']}")
        products = await db_manager.get_products(category_id=data['cat_id'], only_active=False)
        rate = int(await db_manager.get_setting("dollar_rate", "12500"))
        await message.answer("📦 قائمة المنتجات", reply_markup=get_products_keyboard(products, data['cat_id'], rate, is_admin=True))
    except ValueError:
        await message.answer("⚠️ يرجى إدخال سعر صحيح.")
