import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message

class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, slow_mode_delay: float = 0.5):
        self.slow_mode_delay = slow_mode_delay
        self.user_last_message_time = {}

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)
            
        user_id = event.from_user.id
        current_time = time.time()
        
        last_time = self.user_last_message_time.get(user_id, 0)
        if current_time - last_time < self.slow_mode_delay:
            return 
        
        self.user_last_message_time[user_id] = current_time
        return await handler(event, data)
