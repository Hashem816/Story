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
    waiting_for_dollar_rate = State()
    
    # إدارة الكوبونات
    waiting_for_coupon_code = State()
    waiting_for_coupon_value = State()
    waiting_for_coupon_min_amount = State()
    waiting_for_coupon_max_uses = State()
    waiting_for_coupon_expiry = State()

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

# --- إعدادات وضع التشغيل والطوارئ ---
@router.callback_query(F.data == "admin_store_status")
async def admin_store_status(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض إعدادات وضع التشغيل والطوارئ"""
    if not is_admin: return
    
    lang = get_user_language(user)
    store_mode = await db_manager.get_setting("store_mode", "MANUAL")
    emergency = await db_manager.get_setting("emergency_stop", "0")
    
    mode_text = {"AUTO": "🤖 تلقائي", "MANUAL": "👤 يدوي", "MAINTENANCE": "🛠 صيانة"}.get(store_mode, store_mode)
    emergency_text = "🚨 مفعل (متوقف)" if emergency == "1" else "✅ معطل (يعمل)"
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🤖 تلقائي", callback_data="admin_set_mode_AUTO"),
        InlineKeyboardButton(text="👤 يدوي", callback_data="admin_set_mode_MANUAL")
    )
    builder.row(InlineKeyboardButton(text="🛠 وضع الصيانة", callback_data="admin_set_mode_MAINTENANCE"))
    builder.row(InlineKeyboardButton(text="🚨 تبديل وضع الطوارئ", callback_data="admin_toggle_emergency"))
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="admin_main"))
    
    await callback.message.edit_text(
        f"🔌 *إعدادات تشغيل المتجر*\n\n"
        f"وضع التشغيل الحالي: `{mode_text}`\n"
        f"وضع الطوارئ: `{emergency_text}`\n\n"
        f"ℹ️ وضع الطوارئ يوقف جميع العمليات فوراً لجميع المستخدمين.",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data.startswith("admin_set_mode_"))
async def admin_set_store_mode(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """تغيير وضع تشغيل المتجر"""
    if not is_admin: return
    
    new_mode = callback.data.split("_")[3]
    await db_manager.set_setting("store_mode", new_mode)
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="STORE_MODE_CHANGE",
        details=f"تغيير وضع المتجر إلى: {new_mode}"
    )
    
    await callback.answer(f"✅ تم تغيير الوضع إلى {new_mode}")
    await admin_store_status(callback, is_admin, user)

@router.callback_query(F.data == "admin_toggle_emergency")
async def admin_toggle_emergency(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """تبديل وضع الطوارئ"""
    if not is_admin: return
    
    current = await db_manager.get_setting("emergency_stop", "0")
    new_val = "1" if current == "0" else "0"
    await db_manager.set_setting("emergency_stop", new_val)
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="EMERGENCY_TOGGLE",
        details=f"تغيير وضع الطوارئ إلى: {new_val}"
    )
    
    status_msg = "🚨 تم تفعيل وضع الطوارئ وإيقاف المتجر!" if new_val == "1" else "✅ تم إلغاء وضع الطوارئ وإعادة تشغيل المتجر."
    await callback.answer(status_msg, show_alert=True)
    await admin_store_status(callback, is_admin, user)

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

# --- إعدادات سعر الدولار ---
@router.callback_query(F.data == "admin_dollar_settings")
async def admin_dollar_settings(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض إعدادات سعر الدولار الحالية"""
    if not is_admin: return
    
    lang = get_user_language(user)
    current_rate = await db_manager.get_setting("dollar_rate", "12500")
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ تحديث السعر", callback_data="admin_dollar_update"))
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="admin_main"))
    
    await callback.message.edit_text(
        f"💵 *إعدادات سعر الصرف*\n\nالسعر الحالي: `1$ = {current_rate} ل.س`\n\nيتم استخدام هذا السعر لتحويل أسعار المنتجات وشحن الرصيد.",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "admin_dollar_update")
async def admin_dollar_update_start(callback: types.CallbackQuery, state: FSMContext, is_admin: bool, user: dict):
    """بدء تحديث سعر الدولار"""
    if not is_admin: return
    
    lang = get_user_language(user)
    await state.set_state(AdminStates.waiting_for_dollar_rate)
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn_cancel", lang), callback_data="admin_dollar_settings"))
    
    await callback.message.edit_text(
        "💵 أرسل سعر الصرف الجديد (مثلاً: 13000):",
        reply_markup=builder.as_markup()
    )

@router.message(AdminStates.waiting_for_dollar_rate)
async def admin_dollar_update_finish(message: types.Message, state: FSMContext, is_admin: bool, user: dict):
    """إتمام تحديث سعر الدولار"""
    if not is_admin: return
    
    lang = get_user_language(user)
    try:
        new_rate = int(message.text.strip())
        if new_rate <= 0: raise ValueError
        
        await db_manager.set_setting("dollar_rate", str(new_rate))
        await state.clear()
        
        # تسجيل العملية
        await db_manager.log_admin_action(
            admin_id=message.from_user.id,
            action="DOLLAR_RATE_UPDATE",
            details=f"تحديث سعر الصرف إلى: {new_rate}"
        )
        
        await message.answer(f"✅ تم تحديث سعر الصرف إلى: `{new_rate} ل.س`", parse_mode="Markdown")
        
        # العودة للقائمة
        await admin_dollar_settings(types.CallbackQuery(
            id="dummy", from_user=message.from_user, data="admin_dollar_settings",
            chat_instance="dummy", message=message
        ), is_admin, user)
        
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح أكبر من صفر.")

# --- إدارة الكوبونات ---
@router.callback_query(F.data == "admin_coupons")
async def admin_coupons_main(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """القائمة الرئيسية لإدارة الكوبونات"""
    if not is_admin: return
    
    lang = get_user_language(user)
    coupons = await db_manager.get_all_coupons()
    
    builder = InlineKeyboardBuilder()
    for c in coupons:
        status = "✅" if c['is_active'] else "❌"
        builder.row(InlineKeyboardButton(text=f"{status} {c['code']} ({c['value']}$)", callback_data=f"admin_coupon_view_{c['id']}"))
    
    builder.row(InlineKeyboardButton(text="➕ إضافة كوبون جديد", callback_data="admin_coupon_add_start"))
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="admin_main"))
    
    await callback.message.edit_text(
        "🎟️ *إدارة الكوبونات*\n\nاختر كوبوناً لعرض تفاصيله أو أضف كوبوناً جديداً:",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

@router.callback_query(F.data == "admin_coupon_add_start")
async def admin_coupon_add_start(callback: types.CallbackQuery, state: FSMContext, is_admin: bool):
    """بدء إضافة كوبون جديد"""
    if not is_admin: return
    
    await state.set_state(AdminStates.waiting_for_coupon_code)
    await callback.message.edit_text(
        "🎟️ أدخل كود الكوبون الجديد (مثلاً: SAVE10):",
        reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_coupons")).as_markup()
    )

@router.message(AdminStates.waiting_for_coupon_code)
async def admin_coupon_code(message: types.Message, state: FSMContext):
    """استقبال كود الكوبون"""
    code = message.text.strip().upper()
    existing = await db_manager.get_coupon(code)
    if existing:
        return await message.answer("⚠️ هذا الكود موجود بالفعل، اختر كوداً آخر:")
    
    await state.update_data(code=code)
    await state.set_state(AdminStates.waiting_for_coupon_value)
    await message.answer("💰 أدخل قيمة الخصم بالدولار (مثلاً: 5):")

@router.message(AdminStates.waiting_for_coupon_value)
async def admin_coupon_value(message: types.Message, state: FSMContext):
    """استقبال قيمة الخصم"""
    try:
        value = float(message.text.strip())
        await state.update_data(value=value)
        await state.set_state(AdminStates.waiting_for_coupon_min_amount)
        await message.answer("📉 أدخل الحد الأدنى للطلب لاستخدام الكوبون (مثلاً: 20):")
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح.")

@router.message(AdminStates.waiting_for_coupon_min_amount)
async def admin_coupon_min(message: types.Message, state: FSMContext):
    """استقبال الحد الأدنى"""
    try:
        min_amount = float(message.text.strip())
        await state.update_data(min_amount=min_amount)
        await state.set_state(AdminStates.waiting_for_coupon_max_uses)
        await message.answer("🔢 أدخل أقصى عدد مرات استخدام للكوبون (مثلاً: 100):")
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح.")

@router.message(AdminStates.waiting_for_coupon_max_uses)
async def admin_coupon_max(message: types.Message, state: FSMContext, is_admin: bool, user: dict):
    """استقبال عدد المرات وإنهاء الإضافة"""
    try:
        max_uses = int(message.text.strip())
        data = await state.get_data()
        
        await db_manager.create_coupon(
            code=data['code'],
            type='FIXED',
            value=data['value'],
            max_uses=max_uses,
            min_amount=data['min_amount'],
            expires_at=None,
            created_by=message.from_user.id
        )
        
        # تسجيل العملية
        await db_manager.log_admin_action(
            admin_id=message.from_user.id,
            action="CREATE_COUPON",
            details=f"إنشاء كوبون: {data['code']} بقيمة {data['value']}$"
        )
        
        await state.clear()
        await message.answer(f"✅ تم إنشاء الكوبون `{data['code']}` بنجاح!")
        await admin_coupons_main(types.CallbackQuery(
            id="dummy", from_user=message.from_user, data="admin_coupons",
            chat_instance="dummy", message=message
        ), is_admin, user)
        
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح.")

@router.callback_query(F.data.startswith("admin_coupon_view_"))
async def admin_coupon_view(callback: types.CallbackQuery, is_admin: bool):
    """عرض تفاصيل كوبون"""
    if not is_admin: return
    
    coupon_id = int(callback.data.split("_")[3])
    db = await db_manager.connect()
    cursor = await db.execute("SELECT * FROM coupons WHERE id = ?", (coupon_id,))
    coupon = await cursor.fetchone()
    
    if not coupon:
        return await callback.answer("❌ الكوبون غير موجود", show_alert=True)
    
    text = (
        f"🎟️ *تفاصيل الكوبون*\n\n"
        f"الكود: `{coupon['code']}`\n"
        f"القيمة: `{coupon['value']}$`\n"
        f"الحد الأدنى: `{coupon['min_amount']}$`\n"
        f"الاستخدام: `{coupon['used_count']}/{coupon['max_uses']}`\n"
        f"الحالة: `{'نشط' if coupon['is_active'] else 'معطل'}`"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🗑 حذف الكوبون", callback_data=f"admin_coupon_del_{coupon_id}"))
    builder.row(InlineKeyboardButton(text="🔙 عودة", callback_data="admin_coupons"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_coupon_del_"))
async def admin_coupon_delete(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """حذف كوبون"""
    if not is_admin: return
    
    coupon_id = int(callback.data.split("_")[3])
    await db_manager.delete_coupon(coupon_id)
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="DELETE_COUPON",
        details=f"حذف كوبون ID: {coupon_id}"
    )
    
    await callback.answer("✅ تم حذف الكوبون")
    await admin_coupons_main(callback, is_admin, user)

# --- الإحصائيات والتقارير ---
@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض إحصائيات المتجر الشاملة"""
    if not is_admin: return
    
    lang = get_user_language(user)
    from services.analytics_service import analytics_service
    stats = await analytics_service.get_dashboard_stats()
    
    if not stats:
        return await callback.answer("⚠️ فشل جلب الإحصائيات حالياً.", show_alert=True)
    
    text = (
        "📊 *إحصائيات المتجر الشاملة*\n\n"
        "👥 *المستخدمين:*\n"
        f"├ الإجمالي: `{stats.get('total_users', 0)}`\n"
        f"├ جدد اليوم: `{stats.get('new_users_today', 0)}`\n"
        f"└ محظورين: `{stats.get('blocked_users', 0)}`\n\n"
        
        "📦 *الطلبات:*\n"
        f"├ الإجمالي: `{stats.get('total_orders', 0)}`\n"
        f"├ مكتملة: `{stats.get('completed_orders', 0)}`\n"
        f"├ قيد التنفيذ: `{stats.get('pending_orders', 0)}`\n"
        f"└ معدل النجاح: `{stats.get('success_rate', 0):.1f}%`\n\n"
        
        "💰 *المالية (USD):*\n"
        f"├ إجمالي الإيرادات: `{stats.get('total_revenue', 0):.2f}$`\n"
        f"├ إيرادات اليوم: `{stats.get('revenue_today', 0):.2f}$`\n"
        f"├ إيرادات الشهر: `{stats.get('revenue_month', 0):.2f}$`\n"
        f"└ رصيد المستخدمين: `{stats.get('total_balance', 0):.2f}$`\n\n"
        
        "💳 *الشحن:*\n"
        f"├ إجمالي عمليات الشحن: `{stats.get('total_deposits', 0)}`\n"
        f"└ إجمالي المبالغ المشحونة: `{stats.get('total_deposit_amount', 0):.2f}$`"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔝 أفضل المنتجات", callback_data="admin_stats_top_prods"))
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="admin_main"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "admin_stats_top_prods")
async def admin_stats_top_products(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض أفضل المنتجات مبيعاً"""
    if not is_admin: return
    
    lang = get_user_language(user)
    from services.analytics_service import analytics_service
    top_prods = await analytics_service.get_top_products(limit=10)
    
    if not top_prods:
        return await callback.answer("📭 لا توجد بيانات مبيعات كافية.", show_alert=True)
    
    text = "🔝 *أفضل 10 منتجات مبيعاً*\n\n"
    for i, p in enumerate(top_prods, 1):
        text += f"{i}. `{p['name']}`\n   └ مبيعات: `{p['order_count']}` | إيرادات: `{p['total_revenue']:.2f}$`\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="admin_stats"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# --- سجل العمليات الإدارية ---
@router.callback_query(F.data == "admin_audit_logs")
async def admin_audit_logs(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض آخر سجلات العمليات الإدارية"""
    if not is_admin: return
    
    lang = get_user_language(user)
    db = await db_manager.connect()
    cursor = await db.execute("""
        SELECT * FROM admin_audit_logs 
        ORDER BY created_at DESC 
        LIMIT 15
    """)
    logs = await cursor.fetchall()
    
    if not logs:
        return await callback.answer("📭 السجل فارغ حالياً.", show_alert=True)
    
    text = "📋 *آخر العمليات الإدارية:*\n\n"
    for log in logs:
        dt = datetime.fromisoformat(log['created_at']).strftime('%m/%d %H:%M')
        text += f"🕒 `{dt}` | `{log['action']}`\n└ {log['details']}\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text=get_text("btn_back", lang), callback_data="admin_main"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
