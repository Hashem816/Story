"""
Telegram Bot - Professional Store v2.2 Ultimate
نقطة الدخول الرئيسية للبوت

التحسينات:
- Error Handler مركزي
- Graceful Shutdown
- Health Server محسّن
- Logging احترافي
"""

import asyncio
import logging
import sys
import os
import signal
from contextlib import asynccontextmanager

# إضافة المسار الحالي لضمان العثور على المجلدات في Koyeb/Render
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from config.settings import BOT_TOKEN
from database.manager import db_manager
from middlewares.auth import AdminMiddleware, AuthMiddleware
from middlewares.throttling import ThrottlingMiddleware
from handlers import (
    user, admin, products, admin_modes, admin_orders, 
    admin_stats, admin_broadcast, admin_coupons, 
    admin_audit, language, payments
)

# إعداد Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# متغيرات عامة
bot: Bot = None
dp: Dispatcher = None
health_server_task = None


# ===== Health Server (Async) =====
async def health_server():
    """
    Health Server بسيط لـ Koyeb/Render
    يعمل بشكل async بدون threading
    """
    from aiohttp import web
    
    async def health_check(request):
        return web.Response(text="OK", status=200)
    
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    
    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    
    logger.info(f"Health server started on port {port}")
    await site.start()
    
    # الانتظار إلى الأبد (سيتم إيقافه عند shutdown)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


# ===== Error Handler =====
async def error_handler(event: ErrorEvent):
    """
    Error Handler مركزي لجميع الأخطاء
    يمنع توقف البوت عند حدوث خطأ
    """
    logger.error(
        f"Error handling update {event.update.update_id}: {event.exception}",
        exc_info=True
    )
    
    # تسجيل الخطأ في قاعدة البيانات
    try:
        await db_manager.log_admin_action(
            admin_id=0,  # System
            action="ERROR",
            details=f"Update {event.update.update_id}: {str(event.exception)[:500]}"
        )
    except Exception as e:
        logger.error(f"Failed to log error to database: {e}")
    
    # محاولة إرسال رسالة للمستخدم إذا أمكن
    try:
        if event.update.message:
            await event.update.message.answer(
                "⚠️ حدث خطأ أثناء معالجة طلبك. يرجى المحاولة مرة أخرى.\n"
                "إذا استمرت المشكلة، تواصل مع الدعم."
            )
        elif event.update.callback_query:
            await event.update.callback_query.answer(
                "⚠️ حدث خطأ. يرجى المحاولة مرة أخرى.",
                show_alert=True
            )
    except:
        pass  # إذا فشل إرسال الرسالة، لا مشكلة


# ===== Graceful Shutdown =====
async def shutdown(signal_type=None):
    """
    إيقاف البوت بشكل آمن
    """
    if signal_type:
        logger.info(f"Received exit signal {signal_type.name}...")
    else:
        logger.info("Shutting down...")
    
    # إيقاف Health Server
    if health_server_task:
        health_server_task.cancel()
        try:
            await health_server_task
        except asyncio.CancelledError:
            pass
    
    # إغلاق اتصال البوت
    if bot:
        await bot.session.close()
    
    logger.info("Bot stopped successfully!")


# ===== Main Function =====
async def main():
    """
    الدالة الرئيسية لتشغيل البوت
    """
    global bot, dp, health_server_task
    
    logger.info("Starting Professional Telegram Store v2.2 Ultimate...")
    
    # تهيئة قاعدة البيانات
    try:
        await db_manager.init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return
    
    # إنشاء Bot و Dispatcher
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    
    # تسجيل Error Handler
    dp.errors.register(error_handler)
    
    # تسجيل الميدلوير بالترتيب الصحيح
    # الترتيب مهم: Throttling -> Admin -> Auth
    throttling_middleware = ThrottlingMiddleware()
    dp.message.middleware(throttling_middleware)
    dp.message.middleware(AdminMiddleware())
    dp.message.middleware(AuthMiddleware())
    
    dp.callback_query.middleware(AdminMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    
    # تسجيل الموجهات (Routers) بالترتيب الصحيح
    # الأدمن أولاً لضمان عدم تداخل الأوامر
    dp.include_router(admin.router)
    dp.include_router(products.router)
    dp.include_router(admin_modes.router)
    dp.include_router(admin_orders.router)
    dp.include_router(admin_stats.router)
    dp.include_router(admin_broadcast.router)
    dp.include_router(admin_coupons.router)
    dp.include_router(admin_audit.router)
    dp.include_router(language.router)
    dp.include_router(payments.router)
    dp.include_router(user.router)
    
    # تشغيل Health Server في الخلفية
    health_server_task = asyncio.create_task(health_server())
    
    # تسجيل Signal Handlers للـ Graceful Shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s))
        )
    
    try:
        # حذف الـ Webhook القديم لضمان عمل الـ Polling
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted, starting polling...")
        
        # بدء الـ Polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        logger.error(f"Error during polling: {e}", exc_info=True)
    finally:
        await shutdown()


# ===== Entry Point =====
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
