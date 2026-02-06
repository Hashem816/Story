from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from config.settings import StoreMode, UserRole
from utils.keyboards import get_admin_main_menu

router = Router()

class DollarSettings(StatesGroup):
    waiting_for_rate = State()

def get_modes_keyboard(current_mode: str, emergency_stop: bool):
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text=f"{'✅ ' if current_mode == StoreMode.AUTO else ''}🟢 AUTO", callback_data=f"admin_set_mode_{StoreMode.AUTO}")],
        [types.InlineKeyboardButton(text=f"{'✅ ' if current_mode == StoreMode.MANUAL else ''}🟡 MANUAL", callback_data=f"admin_set_mode_{StoreMode.MANUAL}")],
        [types.InlineKeyboardButton(text=f"{'✅ ' if current_mode == StoreMode.MAINTENANCE else ''}🛠 MAINTENANCE", callback_data=f"admin_set_mode_{StoreMode.MAINTENANCE}")],
        [types.InlineKeyboardButton(
            text="🚨 إيقاف الطوارئ (ON)" if not emergency_stop else "🟢 إلغاء الطوارئ (OFF)", 
            callback_data="admin_toggle_emergency"
        )],
        [types.InlineKeyboardButton(text="🔙 عودة للرئيسية", callback_data="admin_main")]
    ])
    return builder

@router.callback_query(F.data == "admin_store_status")
async def show_store_modes(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    current_mode = await db_manager.get_setting("store_mode", StoreMode.MANUAL)
    emergency_stop = (await db_manager.get_setting("emergency_stop", "0")) == "1"
    
    status_text = (
        f"🔌 *نظام تشغيل المتجر*\n\n"
        f"📍 الوضع الحالي: `{current_mode}`\n"
        f"🚨 حالة الطوارئ: `{'مفعلة' if emergency_stop else 'معطلة'}`\n\n"
        f"ℹ️ *الفرق بين الأوضاع:*\n"
        f"• *🛠 الصيانة*: إيقاف المتجر للتحديثات مع إشعار المستخدمين بالعودة قريباً.\n"
        f"• *🚨 الطوارئ*: إيقاف فوري وشامل لجميع العمليات (شحن، طلبات) لحماية النظام.\n"
        f"• *🤖 AUTO*: تنفيذ تلقائي عبر API.\n"
        f"• *👤 MANUAL*: تنفيذ يدوي من قبل الأدمن."
    )
    
    await callback.message.edit_text(status_text, reply_markup=get_modes_keyboard(current_mode, emergency_stop), parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_set_mode_"))
async def set_mode(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    new_mode = callback.data.replace("admin_set_mode_", "")
    await db_manager.set_setting("store_mode", new_mode)
    await callback.answer(f"✅ تم الانتقال لوضع {new_mode}")
    await show_store_modes(callback, is_admin)

@router.callback_query(F.data == "admin_toggle_emergency")
async def toggle_emergency(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    current = await db_manager.get_setting("emergency_stop", "0")
    new_val = "1" if current == "0" else "0"
    await db_manager.set_setting("emergency_stop", new_val)
    
    msg = "🚨 تم تفعيل إيقاف الطوارئ!" if new_val == "1" else "🟢 تم إلغاء إيقاف الطوارئ."
    await callback.answer(msg, show_alert=True)
    await show_store_modes(callback, is_admin)

# --- إعدادات سعر الدولار ---
@router.callback_query(F.data == "admin_dollar_settings")
async def dollar_settings_main(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    rate = await db_manager.get_setting("dollar_rate", "12500")
    
    text = (
        f"💵 *إعدادات سعر الصرف*\n\n"
        f"سعر الدولار الحالي: `{rate} ل.س`\n\n"
        f"هذا السعر يستخدم لحساب تكلفة المنتجات للمستخدمين."
    )
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✏️ تعديل السعر يدويًا", callback_data="admin_set_rate")],
        [types.InlineKeyboardButton(text="🔙 عودة", callback_data="admin_main")]
    ])
    
    await callback.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data == "admin_set_rate")
async def set_rate_start(callback: types.CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin: return
    await state.set_state(DollarSettings.waiting_for_rate)
    await callback.message.edit_text("💵 أدخل سعر الدولار الجديد (مثلاً: 13000):")

@router.message(DollarSettings.waiting_for_rate)
async def set_rate_finish(message: types.Message, state: FSMContext, is_admin: bool, user_role: str):
    if not is_admin: return
    try:
        new_rate = int(message.text)
        await db_manager.set_setting("dollar_rate", str(new_rate))
        await state.clear()
        await message.answer(f"✅ تم تحديث سعر الدولار إلى: `{new_rate} ل.س`", parse_mode="Markdown")
        await message.answer("🛠 لوحة التحكم", reply_markup=get_admin_main_menu(user_role))
    except ValueError:
        await message.answer("⚠️ يرجى إدخال رقم صحيح.")
