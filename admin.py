from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_admin_main_menu
from config.settings import UserRole

router = Router()

class AdminStates(StatesGroup):
    waiting_for_search_query = State()
    waiting_for_support_msg = State()
    waiting_for_balance_amount = State()

@router.message(F.text == "⚙️ لوحة التحكم")
async def admin_panel(message: types.Message, is_support: bool, user_role: str):
    if not is_support: return
    await message.answer("🛠 *لوحة تحكم الإدارة*\nاختر القسم المطلوب إدارته:", reply_markup=get_admin_main_menu(user_role), parse_mode="Markdown")

@router.callback_query(F.data == "admin_main")
async def back_to_admin_main(callback: types.CallbackQuery, is_support: bool, user_role: str):
    if not is_support: return
    await callback.message.edit_text("🛠 *لوحة تحكم الإدارة*\nاختر القسم المطلوب إدارته:", reply_markup=get_admin_main_menu(user_role), parse_mode="Markdown")

# --- إدارة المستخدمين المتقدمة ---
@router.callback_query(F.data == "admin_users_manage")
async def admin_users_main(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔍 بحث عن مستخدم (ID/Username)", callback_data="admin_user_search_start"))
    builder.row(InlineKeyboardButton(text="🔝 آخر 10 مستخدمين", callback_data="admin_user_recent"))
    builder.row(InlineKeyboardButton(text="🚫 قائمة المحظورين", callback_data="admin_user_blocked_list"))
    builder.row(InlineKeyboardButton(text="🔙 عودة للرئيسية", callback_data="admin_main"))
    
    await callback.message.edit_text("👤 *نظام إدارة المستخدمين المطور*\n\nاختر وسيلة البحث أو العرض:", reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_user_search_start")
async def admin_user_search_prompt(callback: types.CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin: return
    await state.set_state(AdminStates.waiting_for_search_query)
    await callback.message.edit_text("🔍 أرسل معرف التيليجرام (ID) أو اسم المستخدم (بدون @) للبحث عنه:")

@router.message(AdminStates.waiting_for_search_query)
async def admin_user_search_execute(message: types.Message, state: FSMContext, is_admin: bool):
    if not is_admin: return
    query = message.text.strip()
    
    db = await db_manager.connect()
    # البحث بـ ID أو Username
    if query.isdigit():
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (int(query),))
    else:
        cursor = await db.execute("SELECT * FROM users WHERE username LIKE ?", (f"%{query}%",))
    
    users = await cursor.fetchall()
    await state.clear()
    
    if not users:
        return await message.answer("❌ لم يتم العثور على أي مستخدم يطابق بحثك.")
    
    if len(users) == 1:
        await show_user_details(message, users[0])
    else:
        builder = InlineKeyboardBuilder()
        for u in users[:10]:
            builder.row(InlineKeyboardButton(text=f"@{u['username']} ({u['telegram_id']})", callback_data=f"admin_user_view_{u['telegram_id']}"))
        builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="admin_users_manage"))
        await message.answer(f"🔍 نتائج البحث ({len(users)}):", reply_markup=builder.as_markup())

async def show_user_details(message_or_callback, user_data):
    user_id = user_data['telegram_id']
    status = "🚫 محظور" if user_data['is_blocked'] else "✅ نشط"
    text = (
        f"👤 *تفاصيل المستخدم*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Username: @{user_data['username']}\n"
        f"🎖 الرتبة: `{user_data['role']}`\n"
        f"💰 الرصيد: `{user_data['balance']:.2f}$`\n"
        f"📍 الحالة: {status}\n"
        f"📅 انضم في: {user_data['created_at']}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎖 تغيير الرتبة", callback_data=f"admin_user_role_{user_id}"),
        InlineKeyboardButton(text="💰 تعديل الرصيد", callback_data=f"admin_user_bal_{user_id}")
    )
    builder.row(
        InlineKeyboardButton(text="🚫 حظر/إلغاء حظر", callback_data=f"admin_user_toggle_{user_id}"),
        InlineKeyboardButton(text="📦 طلبات المستخدم", callback_data=f"admin_user_orders_{user_id}")
    )
    builder.row(InlineKeyboardButton(text="🔙 عودة للقائمة", callback_data="admin_users_manage"))
    
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_user_view_"))
async def admin_user_view_callback(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    user_id = int(callback.data.split("_")[3])
    user = await db_manager.get_user(user_id)
    await show_user_details(callback, user)

@router.callback_query(F.data.startswith("admin_user_toggle_"))
async def admin_user_toggle_block(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    user_id = int(callback.data.split("_")[3])
    user = await db_manager.get_user(user_id)
    new_status = 0 if user['is_blocked'] else 1
    db = await db_manager.connect()
    await db.execute("UPDATE users SET is_blocked = ? WHERE telegram_id = ?", (new_status, user_id))
    await db.commit()
    await callback.answer(f"✅ تم {'حظر' if new_status else 'إلغاء حظر'} المستخدم.")
    updated_user = await db_manager.get_user(user_id)
    await show_user_details(callback, updated_user)

@router.callback_query(F.data.startswith("admin_user_bal_"))
async def admin_user_bal_start(callback: types.CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin: return
    user_id = callback.data.split("_")[3]
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_balance_amount)
    await callback.message.edit_text("💰 أرسل المبلغ المراد إضافته (أو خصمه باستخدام -) بالدولار:")

@router.message(AdminStates.waiting_for_balance_amount)
async def admin_user_bal_finish(message: types.Message, state: FSMContext, is_admin: bool):
    if not is_admin: return
    try:
        amount = float(message.text)
        data = await state.get_data()
        user_id = int(data['target_user_id'])
        
        success, res = await db_manager.update_user_balance(user_id, amount, "ADMIN_ADJUST", admin_id=message.from_user.id, reason="تعديل يدوي من الإدارة")
        if success:
            await message.answer(f"✅ تم تحديث الرصيد. الرصيد الجديد: `{res:.2f}$`", parse_mode="Markdown")
            user = await db_manager.get_user(user_id)
            await show_user_details(message, user)
        else:
            await message.answer(f"❌ فشل: {res}")
        await state.clear()
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح.")

@router.callback_query(F.data.startswith("admin_user_role_"))
async def admin_user_role_list(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    user_id = callback.data.split("_")[3]
    builder = InlineKeyboardBuilder()
    for role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT, UserRole.USER]:
        builder.row(InlineKeyboardButton(text=role, callback_data=f"admin_user_setrole_{user_id}_{role}"))
    builder.row(InlineKeyboardButton(text="🔙 إلغاء", callback_data=f"admin_user_view_{user_id}"))
    await callback.message.edit_text("🎖 اختر الرتبة الجديدة:", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("admin_user_setrole_"))
async def admin_user_role_finish(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    parts = callback.data.split("_")
    user_id, new_role = int(parts[3]), parts[4]
    await db_manager.update_user_role(user_id, new_role)
    await callback.answer(f"✅ تم تغيير الرتبة إلى {new_role}")
    user = await db_manager.get_user(user_id)
    await show_user_details(callback, user)

# --- إعداد رسالة الدعم ---
@router.callback_query(F.data == "admin_support_msg")
async def admin_support_msg_start(callback: types.CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin: return
    current_msg = await db_manager.get_setting("support_message", "تواصل مع الدعم الفني.")
    await state.set_state(AdminStates.waiting_for_support_msg)
    await callback.message.edit_text(
        f"❓ *إعداد رسالة الدعم*\n\nالرسالة الحالية:\n`{current_msg}`\n\nأرسل الرسالة الجديدة الآن:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_main")).as_markup()
    )

@router.message(AdminStates.waiting_for_support_msg)
async def admin_support_msg_save(message: types.Message, state: FSMContext, is_admin: bool, user_role: str):
    if not is_admin: return
    await db_manager.set_setting("support_message", message.text)
    await state.clear()
    await message.answer("✅ تم تحديث رسالة الدعم!")
    await message.answer("🛠 *لوحة تحكم الإدارة*", reply_markup=get_admin_main_menu(user_role), parse_mode="Markdown")
