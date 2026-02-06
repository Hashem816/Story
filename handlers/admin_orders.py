from aiogram import Router, F, types, Bot
from database.manager import db_manager
from utils.keyboards import get_admin_order_actions
from utils.translations import get_text, get_user_language
from config.settings import OrderStatus, UserRole

router = Router()

@router.callback_query(F.data == "admin_orders")
async def list_active_orders(callback: types.CallbackQuery, is_support: bool):
    if not is_support: return
    db = await db_manager.connect()
    cursor = await db.execute("""
        SELECT o.id, o.status, p.name, u.username 
        FROM orders o 
        JOIN products p ON o.product_id = p.id 
        JOIN users u ON o.user_id = u.telegram_id
        WHERE o.status IN (?, ?, ?)
        ORDER BY o.created_at DESC LIMIT 20
    """, (OrderStatus.PAID, OrderStatus.IN_PROGRESS, OrderStatus.PENDING_REVIEW))
    orders = await cursor.fetchall()
    
    if not orders:
        return await callback.message.edit_text("📭 لا توجد طلبات نشطة حالياً.", 
                                               reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[types.InlineKeyboardButton(text="🔙 عودة", callback_data="admin_main")]]))

    builder = types.InlineKeyboardMarkup(inline_keyboard=[])
    for ord in orders:
        status_icon = "📸" if ord['status'] == OrderStatus.PAID else "⏳" if ord['status'] == OrderStatus.IN_PROGRESS else "👀"
        builder.inline_keyboard.append([
            types.InlineKeyboardButton(text=f"{status_icon} #{ord['id']} | {ord['name']} | @{ord['username']}", callback_data=f"aord_view_{ord['id']}")
        ])
    builder.inline_keyboard.append([types.InlineKeyboardButton(text="🔙 عودة", callback_data="admin_main")])
    
    await callback.message.edit_text("📦 *إدارة الطلبات النشطة:*", reply_markup=builder, parse_mode="Markdown")

@router.callback_query(F.data.startswith("aord_view_"))
async def view_order_details(callback: types.CallbackQuery, is_support: bool):
    if not is_support: return
    order_id = int(callback.data.split("_")[2])
    order = await db_manager.get_order(order_id)
    
    text = (
        f"📑 *تفاصيل الطلب #{order_id}*\n\n"
        f"👤 المستخدم: @{order['username']} (`{order['telegram_id']}`)\n"
        f"📦 المنتج: {order['product_name']}\n"
        f"🆔 معرف اللاعب: `{order['player_id']}`\n"
        f"💰 السعر: {order['price_local']:,.0f} ل.س ({order['price_usd']}$)\n"
        f"📍 الحالة: `{order['status']}`\n"
        f"📅 التاريخ: {order['created_at']}"
    )
    
    await callback.message.edit_text(text, reply_markup=get_admin_order_actions(order_id, order['status']), parse_mode="Markdown")

@router.callback_query(F.data.startswith("aord_approve_pay_"))
async def approve_payment(callback: types.CallbackQuery, is_operator: bool, bot: Bot):
    if not is_operator: return
    order_id = int(callback.data.split("_")[3])
    order = await db_manager.get_order(order_id)
    
    await db_manager.update_order_status(order_id, OrderStatus.IN_PROGRESS, operator_id=callback.from_user.id)
    await callback.answer("✅ تم تأكيد الإيصال. الطلب الآن قيد التنفيذ.")
    
    user_data = await db_manager.get_user(order['telegram_id'])
    lang = get_user_language(user_data)
    await bot.send_message(order['telegram_id'], f"✅ تم تأكيد إيصال الدفع للطلب `#{order_id}`.\nجاري تنفيذ طلبك الآن..." if lang == "ar" else f"✅ Payment receipt confirmed for order `#{order_id}`.\nYour order is being processed...")
    await list_active_orders(callback, is_operator)

@router.callback_query(F.data.startswith("aord_reject_pay_"))
async def reject_payment(callback: types.CallbackQuery, is_operator: bool, bot: Bot):
    if not is_operator: return
    order_id = int(callback.data.split("_")[3])
    order = await db_manager.get_order(order_id)
    
    await db_manager.update_order_status(order_id, OrderStatus.FAILED, admin_notes="تم رفض الإيصال")
    await callback.answer("❌ تم رفض الإيصال.")
    
    user_data = await db_manager.get_user(order['telegram_id'])
    lang = get_user_language(user_data)
    await bot.send_message(order['telegram_id'], f"❌ عذراً، تم رفض إيصال الدفع للطلب `#{order_id}`. يرجى التواصل مع الدعم." if lang == "ar" else f"❌ Sorry, the payment receipt for order `#{order_id}` was rejected. Please contact support.")
    await list_active_orders(callback, is_operator)

@router.callback_query(F.data.startswith("aord_complete_"))
async def complete_order(callback: types.CallbackQuery, is_operator: bool, bot: Bot):
    if not is_operator: return
    order_id = int(callback.data.split("_")[2])
    order = await db_manager.get_order(order_id)
    
    await db_manager.update_order_status(order_id, OrderStatus.COMPLETED, execution_type="MANUAL", operator_id=callback.from_user.id)
    await callback.answer("✅ تم إكمال الطلب بنجاح.")
    
    user_data = await db_manager.get_user(order['telegram_id'])
    lang = get_user_language(user_data)
    await bot.send_message(order['telegram_id'], f"✅ مبروك! تم تنفيذ طلبك `#{order_id}` بنجاح.\nشكراً لتعاملك معنا." if lang == "ar" else f"✅ Congratulations! Your order `#{order_id}` has been successfully executed.\nThank you for choosing us.")
    await list_active_orders(callback, is_operator)

@router.callback_query(F.data.startswith("aord_cancel_"))
async def cancel_order(callback: types.CallbackQuery, is_operator: bool, bot: Bot):
    if not is_operator: return
    order_id = int(callback.data.split("_")[2])
    order = await db_manager.get_order(order_id)
    
    await db_manager.update_order_status(order_id, OrderStatus.CANCELED, operator_id=callback.from_user.id)
    await callback.answer("❌ تم إلغاء الطلب.")
    
    user_data = await db_manager.get_user(order['telegram_id'])
    lang = get_user_language(user_data)
    await bot.send_message(order['telegram_id'], f"❌ نعتذر، تم إلغاء طلبك `#{order_id}`." if lang == "ar" else f"❌ Sorry, your order `#{order_id}` has been canceled.")
    await list_active_orders(callback, is_operator)
