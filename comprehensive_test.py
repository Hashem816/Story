#!/usr/bin/env python3.11
"""
Comprehensive Lifecycle Test for Story Bot
Tests: Deposit -> Purchase -> Success -> Refund (on failure)
"""

import asyncio
import os
import sys
import logging
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.manager import db_manager
from services.order_service import order_service
from config.settings import OrderStatus

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test")

async def run_test():
    print("\n🚀 Starting Comprehensive Lifecycle Test...")
    
    try:
        # 1. Initialize Database
        print("⏳ Initializing Database...")
        await db_manager.init_db()
        print("✅ Database initialized.")
        
        # 2. Create Test User
        test_user_id = 999999999
        print(f"⏳ Creating Test User {test_user_id}...")
        await db_manager.create_user(
            telegram_id=test_user_id,
            username="test_user",
            first_name="Test",
            last_name="User",
            role="USER"
        )
        print(f"✅ Test user created.")
        
        # 3. Create Test Category and Product
        print("⏳ Creating Test Category, Product and Payment Method...")
        db = await db_manager.connect()
        async with db.execute("INSERT OR IGNORE INTO categories (id, name) VALUES (1, 'Test Category')"): pass
        async with db.execute("""
            INSERT OR IGNORE INTO products (id, category_id, name, description, price_usd, type, is_active)
            VALUES (1, 1, 'Test Product', 'Description', 10.0, 'MANUAL', 1)
        """): pass
        async with db.execute("INSERT OR IGNORE INTO payment_methods (id, name, is_active) VALUES (1, 'Test Method', 1)"): pass
        await db.commit()
        print("✅ Test assets created.")
        
        # 4. Test Deposit (Recharge)
        print("⏳ Testing Deposit...")
        deposit_amount = 50.0
        success, new_balance = await db_manager.update_user_balance(
            user_id=test_user_id,
            amount=deposit_amount,
            log_type="DEPOSIT",
            reason="Test Deposit"
        )
        if success and new_balance == 50.0:
            print(f"✅ Deposit successful. New balance: {new_balance}$")
        else:
            print(f"❌ Deposit failed. Result: {new_balance}")
            return

        # 5. Test Purchase (Create Order)
        print("⏳ Testing Purchase...")
        success, msg, order_id = await order_service.create_order(
            user_id=test_user_id,
            product_id=1,
            player_id="PLAYER123",
            payment_method_id=None # Use balance
        )
        
        if success:
            user = await db_manager.get_user(test_user_id)
            print(f"✅ Purchase successful. Order ID: #{order_id}. New balance: {user['balance']}$")
            if user['balance'] != 40.0:
                print(f"❌ Balance mismatch! Expected 40.0, got {user['balance']}")
                return
        else:
            print(f"❌ Purchase failed: {msg}")
            return

        # 6. Test Order Finalization (Success)
        print("⏳ Testing Order Finalization (Success)...")
        await db_manager.create_user(telegram_id=12345, username="admin", role="SUPER_ADMIN")
        
        success, msg = await order_service.finalize_order(
            order_id=order_id,
            status=OrderStatus.COMPLETED,
            admin_id=12345,
            admin_notes="Test completion"
        )
        if success:
            order = await db_manager.get_order(order_id)
            print(f"✅ Order #{order_id} completed successfully. Status: {order['status']}")
        else:
            print(f"❌ Order completion failed: {msg}")
            return

        # 7. Test Refund Lifecycle (Purchase -> Failure -> Refund)
        print("\n🔄 Testing Refund Lifecycle...")
        success, msg, order_id2 = await order_service.create_order(
            user_id=test_user_id,
            product_id=1,
            player_id="PLAYER456",
            payment_method_id=None
        )
        
        user_before = await db_manager.get_user(test_user_id)
        print(f"✅ Second order created: #{order_id2}. Balance: {user_before['balance']}$")
        
        success, msg = await order_service.finalize_order(
            order_id=order_id2,
            status=OrderStatus.FAILED,
            admin_id=12345,
            admin_notes="Test failure for refund"
        )
        
        if success:
            user_after = await db_manager.get_user(test_user_id)
            print(f"✅ Order #{order_id2} failed. Balance after refund: {user_after['balance']}$")
            if user_after['balance'] == user_before['balance'] + 10.0:
                print("✅ Refund verified successfully!")
            else:
                print(f"❌ Refund failed! Expected {user_before['balance'] + 10.0}, got {user_after['balance']}")
                return
        else:
            print(f"❌ Order failure/refund process failed: {msg}")
            return

        # 8. Test Coupon System
        print("\n🎟️ Testing Coupon System...")
        coupon_code = "TEST50"
        db = await db_manager.connect()
        async with db.execute("""
            INSERT OR IGNORE INTO coupons (code, type, value, max_uses, min_amount, is_active)
            VALUES (?, 'PERCENTAGE', 50, 10, 5, 1)
        """, (coupon_code,)): pass
        await db.commit()
        
        is_valid, msg, discount = await db_manager.validate_coupon(coupon_code, test_user_id, 10.0)
        if is_valid and discount == 5.0:
            print(f"✅ Coupon validation successful. Discount: {discount}$")
        else:
            print(f"❌ Coupon validation failed: {msg}, Discount: {discount}")
            return

        success, msg, order_id3 = await order_service.create_order(
            user_id=test_user_id,
            product_id=1,
            player_id="PLAYER_COUPON",
            payment_method_id=None,
            coupon_code=coupon_code
        )
        
        if success:
            order = await db_manager.get_order(order_id3)
            user = await db_manager.get_user(test_user_id)
            print(f"✅ Order with coupon created: #{order_id3}. Price USD: {order['price_usd']}$. New balance: {user['balance']}$")
            if order['price_usd'] == 5.0:
                print("✅ Coupon discount applied correctly to order price!")
            else:
                print(f"❌ Coupon discount mismatch! Expected 5.0, got {order['price_usd']}")
        else:
            print(f"❌ Order with coupon failed: {msg}")
            return

        print("\n✨ ALL TESTS PASSED 100%! ✨")
    
    except Exception as e:
        print(f"\n❌ Test crashed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if db_manager._db:
            await db_manager._db.close()
            print("🔌 Database connection closed.")

if __name__ == "__main__":
    if os.path.exists("test_story.db"):
        os.remove("test_story.db")
    os.environ["DB_PATH"] = "test_story.db"
    asyncio.run(run_test())
