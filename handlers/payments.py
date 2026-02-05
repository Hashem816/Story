from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager
from utils.keyboards import get_payment_methods_keyboard

router = Router()

class PaymentMethodStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_desc = State()

@router.callback_query(F.data == "admin_payment_methods")
async def admin_payment_methods_main(callback: types.CallbackQuery, is_operator: bool):
    if not is_operator: return
    methods = await db_manager.get_payment_methods(only_active=False)
    await callback.message.edit_text("💳 *إدارة طرق الدفع*\n\nاختر طريقة لتعديلها أو أضف واحدة جديدة:", 
                                     reply_markup=get_payment_methods_keyboard(methods, is_admin=True), 
                                     parse_mode="Markdown")

@router.callback_query(F.data == "admin_add_pay_start")
async def admin_add_pay_start(callback: types.CallbackQuery, state: FSMContext, is_operator: bool):
    if not is_operator: return
    await state.set_state(PaymentMethodStates.waiting_for_name)
    await callback.message.edit_text("💳 أدخل اسم طريقة الدفع الجديدة (مثلاً: سيريتيل كاش):", 
                                     reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_payment_methods")]]))

@router.message(PaymentMethodStates.waiting_for_name)
async def admin_add_pay_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(PaymentMethodStates.waiting_for_desc)
    await message.answer("📝 أدخل تعليمات الدفع (رقم الحساب، الاسم، إلخ):")

@router.message(PaymentMethodStates.waiting_for_desc)
async def admin_add_pay_finish(message: types.Message, state: FSMContext, is_operator: bool):
    if not is_operator: return
    data = await state.get_data()
    db = await db_manager.connect()
    await db.execute("INSERT INTO payment_methods (name, description, is_active) VALUES (?, ?, 1)", (data['name'], message.text))
    await db.commit()
    await state.clear()
    await message.answer(f"✅ تم إضافة طريقة الدفع: {data['name']}")
    methods = await db_manager.get_payment_methods(only_active=False)
    await message.answer("💳 إدارة طرق الدفع", reply_markup=get_payment_methods_keyboard(methods, is_admin=True))

@router.callback_query(F.data.startswith("admin_view_pay_"))
async def admin_view_pay(callback: types.CallbackQuery, is_operator: bool):
    if not is_operator: return
    method_id = int(callback.data.split("_")[3])
    method = await db_manager.get_payment_method(method_id)
    
    status = "✅ نشطة" if method['is_active'] else "❌ معطلة"
    text = f"💳 *تفاصيل طريقة الدفع*\n\nالاسم: `{method['name']}`\nالحالة: {status}\n\nالتعليمات:\n`{method['description']}`"
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔄 تغيير الحالة (تفعيل/تعطيل)", callback_data=f"admin_toggle_pay_{method_id}")],
        [types.InlineKeyboardButton(text="🗑 حذف", callback_data=f"admin_del_pay_{method_id}")],
        [types.InlineKeyboardButton(text="🔙 عودة", callback_data="admin_payment_methods")]
    ])
    await callback.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("admin_toggle_pay_"))
async def admin_toggle_pay(callback: types.CallbackQuery, is_operator: bool):
    if not is_operator: return
    method_id = int(callback.data.split("_")[3])
    method = await db_manager.get_payment_method(method_id)
    new_status = 0 if method['is_active'] else 1
    db = await db_manager.connect()
    await db.execute("UPDATE payment_methods SET is_active = ? WHERE id = ?", (new_status, method_id))
    await db.commit()
    await callback.answer("✅ تم تحديث الحالة")
    await admin_view_pay(callback, is_operator)

# --- معالجة عمليات الشحن (Deposit Approval) ---
@router.callback_query(F.data.startswith("admin_pay_approve_"))
async def admin_approve_payment(callback: types.CallbackQuery, bot: Bot, is_operator: bool):
    if not is_operator: return
    parts = callback.data.split("_")
    user_id, amount = int(parts[3]), float(parts[4])
    
    success, new_bal = await db_manager.update_user_balance(user_id, amount, "DEPOSIT", admin_id=callback.from_user.id, reason="شحن يدوي")
    if success:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ *تم القبول بنجاح*", parse_mode="Markdown")
        try: await bot.send_message(user_id, f"✅ تم شحن رصيدك بمبلغ {amount}$. رصيدك الحالي: {new_bal:.2f}$")
        except: pass
    else:
        await callback.answer(f"❌ فشل: {new_bal}", show_alert=True)

@router.callback_query(F.data.startswith("admin_pay_reject_"))
async def admin_reject_payment(callback: types.CallbackQuery, bot: Bot, is_operator: bool):
    if not is_operator: return
    user_id = int(callback.data.split("_")[3])
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ *تم الرفض*", parse_mode="Markdown")
    try: await bot.send_message(user_id, "❌ تم رفض طلب شحن الرصيد.")
    except: pass
