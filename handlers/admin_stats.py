from aiogram import Router, F, types
from database.manager import db_manager

router = Router()

@router.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery, is_admin: bool):
    if not is_admin: return
    
    db = await db_manager.connect()
    # إحصائيات حقيقية من الجداول
    cursor = await db.execute("SELECT COUNT(*) as total FROM users")
    total_users = (await cursor.fetchone())['total']
    
    cursor = await db.execute("SELECT COUNT(*) as total FROM orders")
    total_orders = (await cursor.fetchone())['total']
    
    cursor = await db.execute("SELECT SUM(amount) as total FROM balance_logs WHERE type='DEPOSIT'")
    total_deposits = (await cursor.fetchone())['total'] or 0
    
    text = (
        f"📊 *إحصائيات المتجر الشاملة*\n\n"
        f"👥 إجمالي المستخدمين: `{total_users}`\n"
        f"📦 إجمالي الطلبات: `{total_orders}`\n"
        f"💰 إجمالي الشحنات: `{total_deposits:.2f}$`\n\n"
        f"📅 تم التحديث الآن."
    )
    
    builder = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="🔙 عودة للرئيسية", callback_data="admin_main")]
    ])
    await callback.message.edit_text(text, reply_markup=builder, parse_mode="Markdown")
