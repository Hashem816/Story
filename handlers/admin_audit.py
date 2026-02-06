"""
نظام عرض سجل العمليات (Audit Log)
يسمح للأدمن بمراجعة جميع العمليات الإدارية
"""

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.manager import db_manager
from utils.translations import get_text, get_user_language
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "admin_audit_logs")
async def admin_audit_logs_main(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض سجل العمليات الإدارية"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    logs = await db_manager.get_audit_logs(limit=20)
    
    if not logs:
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(
            text=get_text("btn_back", lang),
            callback_data="admin_main"
        ))
        return await callback.message.edit_text(
            "📭 لا توجد سجلات حالياً",
            reply_markup=builder.as_markup()
        )
    
    text = "📝 *سجل العمليات الإدارية*\n\n"
    text += "آخر 20 عملية:\n\n"
    
    for log in logs:
        admin_id = log['admin_id']
        action = log['action']
        details = log['details'] or ''
        created_at = log['created_at']
        
        text += f"🔹 `{action}`\n"
        text += f"   👤 Admin: `{admin_id}`\n"
        if details:
            text += f"   📄 {details[:50]}\n"
        text += f"   ⏰ {created_at}\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📊 إحصائيات السجل",
        callback_data="admin_audit_stats"
    ))
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_main"
    ))
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "admin_audit_stats")
async def admin_audit_stats(callback: types.CallbackQuery, is_admin: bool, user: dict):
    """عرض إحصائيات سجل العمليات"""
    if not is_admin:
        return
    
    lang = get_user_language(user)
    db = await db_manager.connect()
    
    # إحصائيات العمليات
    cursor = await db.execute("""
        SELECT action, COUNT(*) as count
        FROM audit_logs
        GROUP BY action
        ORDER BY count DESC
        LIMIT 10
    """)
    action_stats = await cursor.fetchall()
    
    # إحصائيات الأدمن
    cursor = await db.execute("""
        SELECT admin_id, COUNT(*) as count
        FROM audit_logs
        GROUP BY admin_id
        ORDER BY count DESC
        LIMIT 5
    """)
    admin_stats = await cursor.fetchall()
    
    text = "📊 *إحصائيات سجل العمليات*\n\n"
    
    text += "🔝 أكثر العمليات:\n"
    for stat in action_stats:
        text += f"   • {stat['action']}: {stat['count']}\n"
    
    text += "\n👥 أكثر الأدمن نشاطاً:\n"
    for stat in admin_stats:
        text += f"   • Admin `{stat['admin_id']}`: {stat['count']} عملية\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text=get_text("btn_back", lang),
        callback_data="admin_audit_logs"
    ))
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
