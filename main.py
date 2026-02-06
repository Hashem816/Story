import asyncio
import logging
import sys
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def start_dummy():
    port = int(os.environ.get("PORT", 8000))  # Koyeb يمرر PORT كـ env var
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"Dummy health server started on port {port}")
    server.serve_forever()

# شغله في خلفية
threading.Thread(target=start_dummy, daemon=True).start()

# بعد كده كود البوت العادي...

# إضافة المسار الحالي لضمان العثور على المجلدات في Render
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config.settings import BOT_TOKEN
from database.manager import db_manager
from middlewares.auth import AdminMiddleware, AuthMiddleware
from middlewares.throttling import ThrottlingMiddleware
from handlers import user, admin, products, admin_modes, admin_orders, admin_stats, admin_broadcast, admin_coupons, admin_audit, language, payments

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("bot.log")
        ]
    )
    logger = logging.getLogger(__name__)

    # تهيئة قاعدة البيانات بالجداول الجديدة
    await db_manager.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    # تسجيل الميدلوير بالترتيب الصحيح
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(AdminMiddleware())
    dp.message.middleware(AuthMiddleware())
    
    dp.callback_query.middleware(AdminMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # تسجيل الموجهات (Routers) بالترتيب الصحيح (الأدمن أولاً لضمان عدم تداخل الأوامر)
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

    logger.info("Starting Professional Telegram Store v2.2 Ultimate...")
    try:
        # حذف الـ Webhook القديم لضمان عمل الـ Polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped!")
