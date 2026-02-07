import asyncio
import os
import sys

# إضافة المسار الحالي
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.manager import db_manager
from utils.translations import get_user_language, get_text

async def test_language_logic():
    print("🧪 Testing Language Logic...")
    
    # 1. تهيئة قاعدة البيانات
    if os.path.exists("test_lang.db"):
        os.remove("test_lang.db")
    
    db_manager.db_path = "test_lang.db"
    await db_manager.init_db()
    
    test_user_id = 123456789
    
    # 2. اختبار إنشاء مستخدم بدون لغة
    print("⏳ Creating user without language...")
    await db_manager.create_user(test_user_id, "testuser", language=None)
    user = await db_manager.get_user(test_user_id)
    
    lang = get_user_language(user)
    print(f"Resulting language: {lang}")
    if lang is None:
        print("✅ Correct: New user has no language.")
    else:
        print(f"❌ Error: New user should have None language, got {lang}")
        return

    # 3. اختبار الحصول على نص بدون لغة (يجب أن يعود للعربية)
    welcome_text = get_text("welcome", lang)
    print(f"Welcome text (no lang): {welcome_text[:20]}...")
    if "مرحباً" in welcome_text:
        print("✅ Correct: Defaulted to Arabic text.")
    else:
        print("❌ Error: Should default to Arabic.")

    # 4. اختبار تحديث اللغة للعربية
    print("⏳ Updating language to 'ar'...")
    await db_manager.update_user_language(test_user_id, "ar")
    user = await db_manager.get_user(test_user_id)
    lang = get_user_language(user)
    print(f"Resulting language: {lang}")
    if lang == "ar":
        print("✅ Correct: Language updated to 'ar'.")
    else:
        print(f"❌ Error: Language should be 'ar'.")

    # 5. اختبار تحديث اللغة للإنجليزية
    print("⏳ Updating language to 'en'...")
    await db_manager.update_user_language(test_user_id, "en")
    user = await db_manager.get_user(test_user_id)
    lang = get_user_language(user)
    print(f"Resulting language: {lang}")
    if lang == "en":
        print("✅ Correct: Language updated to 'en'.")
    else:
        print(f"❌ Error: Language should be 'en'.")
        
    welcome_en = get_text("welcome", lang)
    print(f"Welcome text (en): {welcome_en[:20]}...")
    if "Welcome" in welcome_en:
        print("✅ Correct: Got English text.")
    else:
        print("❌ Error: Should get English text.")

    print("\n✨ ALL LANGUAGE TESTS PASSED! ✨")

if __name__ == "__main__":
    asyncio.run(test_language_logic())
