import asyncio
import logging
from aiogram import Router, F, types, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.manager import db_manager

logger = logging.getLogger(__name__)
router = Router()

class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirming = State()

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext, is_admin: bool):
    if not is_admin: return
    await state.set_state(BroadcastStates.waiting_for_message)
    await callback.message.edit_text(
        "📢 *نظام البث الجماعي*\n\nيرجى إرسال الرسالة التي ترغب في بثها لجميع المستخدمين.\nيمكنك إرسال (نص، صورة، فيديو، أو منشور كامل):",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_main")]]),
        parse_mode="Markdown"
    )

@router.message(BroadcastStates.waiting_for_message)
async def confirm_broadcast(message: types.Message, state: FSMContext):
    await state.update_data(broadcast_msg_id=message.message_id, from_chat_id=message.chat.id)
    await state.set_state(BroadcastStates.confirming)
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="✅ تأكيد الإرسال", callback_data="broadcast_confirm")],
        [types.InlineKeyboardButton(text="❌ إلغاء", callback_data="admin_main")]
    ])
    
    await message.answer("⚠️ *هل أنت متأكد؟*\nسيتم بث هذا المنشور لجميع المشتركين في البوت.", reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data == "broadcast_confirm", BroadcastStates.confirming)
async def execute_broadcast(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    msg_id = data.get('broadcast_msg_id')
    from_chat = data.get('from_chat_id')
    
    if not msg_id or not from_chat:
        await callback.answer("❌ حدث خطأ في استعادة الرسالة.")
        return

    db = await db_manager.connect()
    cursor = await db.execute("SELECT telegram_id FROM users")
    users = [row['telegram_id'] for row in await cursor.fetchall()]
    
    await callback.message.edit_text(f"⏳ بدأ البث لـ {len(users)} مستخدم...")
    
    success_count = 0
    fail_count = 0
    
    for user_id in users:
        try:
            await bot.copy_message(chat_id=user_id, from_chat_id=from_chat, message_id=msg_id)
            success_count += 1
            await asyncio.sleep(0.05) # تفادي قيود تيليجرام
        except Exception as e:
            logger.error(f"Failed to broadcast to {user_id}: {e}")
            fail_count += 1
            
    await callback.message.answer(
        f"✅ *اكتمل البث الجماعي*\n\n"
        f"📊 التقرير:\n"
        f"🔹 تم الإرسال بنجاح: `{success_count}`\n"
        f"🔸 فشل الإرسال: `{fail_count}`",
        parse_mode="Markdown"
    )
    await state.clear()
