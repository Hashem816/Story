
import logging
import traceback
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, ErrorEvent

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseMiddleware):
    """
    Middleware لمعالجة الأخطاء بشكل مركزي
    يمنع توقف البوت عند حدوث خطأ غير متوقع ويقوم بتسجيله
    """
    async def __call__(
        self,
        handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception as e:
            user_id = "Unknown"
            if hasattr(event, 'from_user') and event.from_user:
                user_id = event.from_user.id
            
            error_msg = f"❌ Error for user {user_id}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            
            # إخطار المستخدم بطريقة ودية
            friendly_msg = "⚠️ عذراً، حدث خطأ غير متوقع أثناء معالجة طلبك. تم إبلاغ المطورين."
            
            try:
                if isinstance(event, Message):
                    await event.answer(friendly_msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(friendly_msg, show_alert=True)
            except Exception as send_error:
                logger.error(f"Failed to send error message to user: {send_error}")
            
            return None
