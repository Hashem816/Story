"""
نظام اختيار اللغة
يسمح للمستخدمين باختيار لغتهم المفضلة
"""

from aiogram import Router, F, types
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.manager import db_manager
from utils.translations import get_text
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.callback_query(F.data == "select_language")
async def show_language_selection(callback: types.CallbackQuery):
    """عرض قائمة اختيار اللغة"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")
    )
    
    await callback.message.edit_text(
        "🌐 *اختر لغتك المفضلة / Choose your language*",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery, user: dict):
    """تعيين لغة المستخدم"""
    lang = callback.data.split("_")[1]
    
    # تحديث اللغة في قاعدة البيانات
    await db_manager.update_user_language(callback.from_user.id, lang)
    
    # تسجيل العملية
    await db_manager.log_admin_action(
        admin_id=callback.from_user.id,
        action="LANGUAGE_CHANGE",
        details=f"تغيير اللغة إلى {lang}"
    )
    
    await callback.answer(get_text("language_selected", lang), show_alert=True)
    
    # العودة للقائمة الرئيسية
    from utils.keyboards import get_main_menu
    user_role = user.get('role', 'USER')
    
    await callback.message.delete()
    await callback.message.answer(
        get_text("main_menu", lang),
        reply_markup=get_main_menu(user_role, lang)
    )
