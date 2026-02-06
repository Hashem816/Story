from aiogram import Router, F, types, Bot
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_admin_main_menu
from utils.translations import get_text, get_user_language
from utils.notifications import notification_manager
from config.settings import UserRole
import logging

router = Router()
logger = logging.getLogger(__name__)

class AdminStates(StatesGroup):
    waiting_for_search_query = State()
    waiting_for_support_msg = State()
    waiting_for_balance_amount = State()
    waiting_for_admin_password = State()

@router.message(F.text.in_(["⚙️ لوحة التحكم", "⚙️ Admin Panel"]))
async def admin_panel(message: types.Message, is_support: bool, user_role: str, user: dict):
    """عرض لوحة التحكم الرئيسية"""
    if not is_support: 
        return
    
    lang = get_user_language(user)
    
    # التحقق من كلمة السر إذا كانت مفعلة
    require_password = await db_manager.get_setting("require_admin_password", "0")
    if require_password == "1":
        # التحقق من الجلسة
        # TODO: تطبيق نظام الجلسات
        pass
    
    await message.answer(
        get_text("admin_panel_title", lang),
        reply_markup=get_admin_main_menu(user_role, lang),
        parse_mode="Markdown"
    )
    
    # تسجيل الدخول للوحة الأدمن
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="ADMIN_PANEL_ACCESS",
        details="دخول إلى لوحة التحكم"
    )

@router.callback_query(F.data == "admin_main")
async def back_to_admin_main(callback: types.CallbackQuery, is_support: bool, user_role: str, user: dict):
    """العودة للوحة التحكم الرئيسية"""
    if not is_support: 
        return
    
    lang = get_user_language(user)
    await callback.message.edit_text(
        get_text("admin_panel_title", lang),
        reply_markup=get_admin_main_menu(user_role),
        parse_mode="Markdown"
    )

# --- إدارة المستخدمين المتقدمة ---
@router.callback_query(F.data == "admin_users_manage")
async def admin_users_main(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """قائمة إدارة المستخدمين الرئيسية"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("search_user", lang),
        callback_data="admin_user_search_start"
    ))
    builder.row(InlineKeyboardButton(
        text=get_text("recent_users", lang),
        callback_data="admin_user_recent"
    ))
    builder.row(InlineKeyboardButton(
        text=get_text("all_users", lang),
        callback_data="admin_user_list_1"
    ))
    builder.row(InlineKeyboardButton(
        text=get_text("blocked_users", lang),
        callback_data="admin_user_blocked_list"
    ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_main"
    ))
    
    await callback.message.edit_text(
        get_text("users_management", lang),
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_user_search_start")
async def admin_user_search_prompt(callback: types.CallbackQuery, state: FSMContext, is_admin: bool, user: dict):
    """بدء البحث عن مستخدم"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    await state.set_state(AdminStates.waiting_for_search_query)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn_cancel", lang),
        callback_data="admin_users_manage"
    ))
    
    await callback.message.edit_text(
        get_text("search_prompt", lang),
        reply_markup=builder.as_markup()
    )

@router.message(AdminStates.waiting_for_search_query)
async def admin_user_search_execute(message: types.Message, state: FSMContext, is_admin: bool, user: dict):
    """تنفيذ البحث عن المستخدمين"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    query = message.text.strip()
    
    # البحث المتقدم
    users = await db_manager.search_users(query, limit=20)
    await state.clear()
    
    if not users:
        return await message.answer(get_text("no_results", lang))
    
    if len(users) == 1:
        # عرض تفاصيل المستخدم مباشرة
        await show_user_details(message, users[0], lang)
    else:
        # عرض قائمة النتائج
        builder = InlineKeyboardBuilder()
        for u in users[:15]:
            display_name = f"@{u['username']}" if u['username'] else f"{u['first_name'] or 'User'}"
            builder.row(InlineKeyboardButton(
                text=f"{display_name} ({u['telegram_id']})",
                callback_data=f"admin_user_view_{u['telegram_id']}"
            ))
        builder.row(InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="admin_users_manage"
        ))
        
        await message.answer(
            get_text("search_results", lang, count=len(users)),
            reply_markup=builder.as_markup()
        )
    
    # تسجيل عملية البحث
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="USER_SEARCH",
        details=f"بحث عن: {query}"
    )

@router.callback_query(F.data == "admin_user_recent")
async def admin_user_recent_list(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض آخر 10 مستخدمين"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    result = await db_manager.get_users_paginated(page=1, per_page=10)
    users = result['users']
    
    if not users:
        return await callback.answer(get_text("no_results", lang), show_alert=True)
    
    builder = InlineKeyboardBuilder()
    for u in users:
        display_name = f"@{u['username']}" if u['username'] else f"{u['first_name'] or 'User'}"
        builder.row(InlineKeyboardButton(
            text=f"{display_name} ({u['telegram_id']})",
            callback_data=f"admin_user_view_{u['telegram_id']}"
        ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_users_manage"
    ))
    
    await callback.message.edit_text(
        f"{get_text('recent_users', lang)}:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("admin_user_list_"))
async def admin_user_list_paginated(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض قائمة المستخدمين مع Pagination"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    page = int(callback.data.split("_")[-1])
    
    result = await db_manager.get_users_paginated(page=page, per_page=10)
    users = result['users']
    
    if not users:
        return await callback.answer(get_text("no_results", lang), show_alert=True)
    
    builder = InlineKeyboardBuilder()
    for u in users:
        display_name = f"@{u['username']}" if u['username'] else f"{u['first_name'] or 'User'}"
        status_icon = "🚫" if u['is_blocked'] else "✅"
        builder.row(InlineKeyboardButton(
            text=f"{status_icon} {display_name} ({u['telegram_id']})",
            callback_data=f"admin_user_view_{u['telegram_id']}"
        ))
    
    # أزرار التنقل
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(
            text=get_text("btn_previous", lang),
            callback_data=f"admin_user_list_{page-1}"
        ))
    if page < result['total_pages']:
        nav_buttons.append(InlineKeyboardButton(
            text=get_text("btn_next", lang),
            callback_data=f"admin_user_list_{page+1}"
        ))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_users_manage"
    ))
    
    await callback.message.edit_text(
        f"{get_text('all_users', lang)} - صفحة {page}/{result['total_pages']}\n"
        f"إجمالي: {result['total']} مستخدم",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "admin_user_blocked_list")
async def admin_user_blocked_list(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض قائمة المستخدمين المحظورين"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    result = await db_manager.get_users_paginated(page=1, per_page=20, filter_blocked=True)
    users = result['users']
    
    if not users:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="admin_users_manage"
        ))
        return await callback.message.edit_text(
            "✅ لا يوجد مستخدمين محظورين",
            reply_markup=builder.as_markup()
        )
    
    builder = InlineKeyboardBuilder()
    for u in users:
        display_name = f"@{u['username']}" if u['username'] else f"{u['first_name'] or 'User'}"
        builder.row(InlineKeyboardButton(
            text=f"🚫 {display_name} ({u['telegram_id']})",
            callback_data=f"admin_user_view_{u['telegram_id']}"
        ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_users_manage"
    ))
    
    await callback.message.edit_text(
        f"{get_text('blocked_users', lang)}: {result['total']}",
        reply_markup=builder.as_markup()
    )

async def show_user_details(message_or_callback, user_data, lang: str = "ar"):
    """عرض تفاصيل المستخدم"""
    user_id = user_data['telegram_id']
    status = get_text("status_blocked", lang) if user_data['is_blocked'] else get_text("status_active", lang)
    
    # جلب عدد الطلبات
    orders_count = await db_manager.get_user_orders_count(user_id)
    
    text = (
        f"{get_text('user_details', lang)}\n\n"
        f"{get_text('user_id', lang)}: `{user_id}`\n"
        f"{get_text('username', lang)}: @{user_data['username'] or 'N/A'}\n"
        f"{get_text('role', lang)}: `{user_data['role']}`\n"
        f"{get_text('balance', lang)}: `{user_data['balance']:.2f}$`\n"
        f"{get_text('status', lang)}: {status}\n"
        f"{get_text('orders_count', lang)}: `{orders_count}`\n"
        f"{get_text('joined_at', lang)}: {user_data['created_at']}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=get_text("change_role", lang),
            callback_data=f"admin_user_role_{user_id}"
        ),
        InlineKeyboardButton(
            text=get_text("edit_balance", lang),
            callback_data=f"admin_user_bal_{user_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=get_text("toggle_block", lang),
            callback_data=f"admin_user_toggle_{user_id}"
        ),
        InlineKeyboardButton(
            text=get_text("view_orders", lang),
            callback_data=f"admin_user_orders_{user_id}"
        )
    )
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_users_manage"
    ))
    
    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_user_view_"))
async def admin_user_view_callback(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض تفاصيل مستخدم من callback"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    user_id = int(callback.data.split("_")[3])
    target_user = await db_manager.get_user(user_id)
    
    if not target_user:
        return await callback.answer("❌ المستخدم غير موجود", show_alert=True)
    
    await show_user_details(callback, target_user, lang)

@router.callback_query(F.data.startswith("admin_user_orders_"))
async def admin_user_orders_view(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض طلبات مستخدم معين"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    user_id = int(callback.data.split("_")[3])
    orders = await db_manager.get_user_orders(user_id, limit=10)
    
    if not orders:
        return await callback.answer("لا توجد طلبات لهذا المستخدم", show_alert=True)
    
    text = f"📦 *طلبات المستخدم {user_id}*\n\n"
    for order in orders:
        text += f"#{order['id']} - {order['product_name']} - {order['status']}\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data=f"admin_user_view_{user_id}"
    ))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_user_toggle_"))
async def admin_user_toggle_block(callback: types.CallbackQuery, is_admin: bool, user: dict, bot: Bot):
    """حظر/إلغاء حظر مستخدم"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    user_id = int(callback.data.split("_")[3])
    target_user = await db_manager.get_user(user_id)
    
    if not target_user:
        return await callback.answer("❌ المستخدم غير موجود", show_alert=True)
    
    new_status = 0 if target_user['is_blocked'] else 1
    db = await db_manager.connect()
    await db.execute("UPDATE users SET is_blocked = ? WHERE telegram_id = ?", (new_status, user_id))
    await db.commit()
    
    action_text = "حظر" if new_status else "إلغاء حظر"
    await callback.answer(f"✅ تم {action_text} المستخدم.")
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="USER_BLOCK_TOGGLE",
        target_type="USER",
        target_id=user_id,
        details=f"{action_text} المستخدم"
    )
    
    # إشعار المستخدم
    if new_status:
        await notification_manager.notify_user(
            bot, user_id,
            "🚫 تم حظر حسابك من قبل الإدارة."
        )
    
    updated_user = await db_manager.get_user(user_id)
    await show_user_details(callback, updated_user, lang)

@router.callback_query(F.data.startswith("admin_user_bal_"))
async def admin_user_bal_start(callback: types.CallbackQuery, state: FSMContext, is_admin: bool, user: dict):
    """بدء تعديل رصيد المستخدم"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    user_id = callback.data.split("_")[3]
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_balance_amount)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn_cancel", lang),
        callback_data=f"admin_user_view_{user_id}"
    ))
    
    await callback.message.edit_text(
        "💰 أرسل المبلغ المراد إضافته (أو خصمه باستخدام -) بالدولار:",
        reply_markup=builder.as_markup()
    )

@router.message(AdminStates.waiting_for_balance_amount)
async def admin_user_bal_finish(message: types.Message, state: FSMContext, is_admin: bool, user: dict, bot: Bot):
    """إتمام تعديل رصيد المستخدم"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    
    try:
        amount = float(message.text)
        data = await state.get_data()
        user_id = int(data['target_user_id'])
        
        success, res = await db_manager.update_user_balance(
            user_id, amount, "ADMIN_ADJUST",
            admin_id=message.from_user.id,
            reason="تعديل يدوي من الإدارة"
        )
        
        if success:
            await message.answer(f"✅ تم تحديث الرصيد. الرصيد الجديد: `{res:.2f}$`", parse_mode="Markdown")
            
            # تسجيل العملية
            await db_manager.log_admin_action(
                admin_id=message.from_user.id,
                action="BALANCE_ADJUST",
                target_type="USER",
                target_id=user_id,
                details=f"تعديل الرصيد: {amount:+.2f}$"
            )
            
            # إشعار المستخدم
            await notification_manager.notify_balance_change(
                bot, user_id, amount, res,
                "تعديل من الإدارة"
            )
            
            target_user = await db_manager.get_user(user_id)
            await show_user_details(message, target_user, lang)
        else:
            await message.answer(f"❌ فشل: {res}")
        
        await state.clear()
    except ValueError:
        await message.answer(get_text("error_invalid_input", lang))

@router.callback_query(F.data.startswith("admin_user_role_"))
async def admin_user_role_list(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض قائمة الرتب لتغيير رتبة المستخدم"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    user_id = callback.data.split("_")[3]
    
    builder = InlineKeyboardBuilder()
    for role in [UserRole.SUPER_ADMIN, UserRole.OPERATOR, UserRole.SUPPORT, UserRole.USER]:
        builder.row(InlineKeyboardButton(
            text=role,
            callback_data=f"admin_user_setrole_{user_id}_{role}"
        ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn_cancel", lang),
        callback_data=f"admin_user_view_{user_id}"
    ))
    
    await callback.message.edit_text(
        "🎖 اختر الرتبة الجديدة:",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("admin_user_setrole_"))
async def admin_user_role_finish(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """إتمام تغيير رتبة المستخدم"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    parts = callback.data.split("_")
    user_id, new_role = int(parts[3]), parts[4]
    
    await db_manager.update_user_role(user_id, new_role)
    await callback.answer(f"✅ تم تغيير الرتبة إلى {new_role}")
    
    # إشعار المستخدم
    from utils.notifications import notification_manager
    await notification_manager.notify_user(callback.bot, user_id, f"🎖 تم تغيير رتبتك إلى: {new_role}\nيرجى الضغط على /start لتحديث القوائم.")
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="ROLE_CHANGE",
        target_type="USER",
        target_id=user_id,
        details=f"تغيير الرتبة إلى {new_role}"
    )
    
    target_user = await db_manager.get_user(user_id)
    await show_user_details(callback, target_user, lang)

# --- إعداد رسالة الدعم ---
@router.callback_query(F.data == "admin_support_msg")
async def admin_support_msg_start(callback: types.CallbackQuery, state: FSMContext, is_admin: bool, user: dict):
    """بدء تعديل رسالة الدعم"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    current_msg = await db_manager.get_setting("support_message", "تواصل مع الدعم الفني.")
    await state.set_state(AdminStates.waiting_for_support_msg)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn_cancel", lang),
        callback_data="admin_main"
    ))
    
    await callback.message.edit_text(
        f"❓ *إعداد رسالة الدعم*\n\nالرسالة الحالية:\n`{current_msg}`\n\nأرسل الرسالة الجديدة الآن:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

@router.message(AdminStates.waiting_for_support_msg)
async def admin_support_msg_save(message: types.Message, state: FSMContext, is_admin: bool, user_role: str, user: dict):
    """حفظ رسالة الدعم الجديدة"""
    if not is_admin: 
        return
    
    lang = get_user_language(user)
    await db_manager.set_setting("support_message", message.text)
    await state.clear()
    
    await message.answer(get_text("success_updated", lang))
    await message.answer(
        get_text("admin_panel_title", lang),
        reply_markup=get_admin_main_menu(user_role, lang),
        parse_mode="Markdown"
    )
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=message.from_user.id,
        action="SUPPORT_MESSAGE_UPDATE",
        details="تحديث رسالة الدعم"
    )
