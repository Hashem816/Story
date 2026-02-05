import aiohttp
from config.settings import ITEM4GAMER_API_KEY, ITEM4GAMER_BASE_URL
from database.manager import db_manager

class Item4GamerClient:
    def __init__(self):
        self.base_url = ITEM4GAMER_BASE_URL

    async def is_enabled(self) -> bool:
        enabled = await db_manager.get_setting("item4gamer_enabled", "0")
        return enabled == "1"

    async def create_order(self, variation_id: str, player_id: str):
        if not await self.is_enabled():
            return {"success": False, "message": "API is currently disabled"}

        api_key = await db_manager.get_setting("item4gamer_api_key", ITEM4GAMER_API_KEY)
        if not api_key:
            return {"success": False, "message": "API Key not configured"}

        url = f"{self.base_url}/order/add-order"
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "variation_id": str(variation_id),
            "quantity": 1,
            "customer": {
                "first_name": "Store",
                "last_name": "User",
                "email": "customer@store.com"
            },
            "data": {
                "save_id": str(player_id)
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=30) as response:
                    data = await response.json()
                    if response.status == 200 and data.get("status") == 200:
                        return {"success": True, "order_id": data.get("order_id")}
                    return {"success": False, "message": data.get("message", "Unknown API Error")}
        except Exception as e:
            return {"success": False, "message": str(e)}

    async def get_balance(self):
        api_key = await db_manager.get_setting("item4gamer_api_key", ITEM4GAMER_API_KEY)
        if not api_key: return 0
        
        url = f"{self.base_url}/order/get-balance"
        headers = {"api-key": api_key}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=20) as response:
                    data = await response.json()
                    if data.get("status") == 200:
                        return float(data.get("balance", 0))
                return 0
        except:
            return 0

api_client = Item4GamerClient()
