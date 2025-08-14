import asyncio

_user_stop_cache = {}

_user_stop_lock = asyncio.Lock() 