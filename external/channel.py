from settings.logger import logger

bot_id = None

async def get_bot_id(client=None):
    """
    Retrieves and caches the bot's Telegram ID.

    :param client: The Telegram client instance.
    :return: The bot's Telegram ID.
    """
    global bot_id
    
    if client is None:
        return bot_id
        
    if bot_id is None:
        logger.debug("Bot ID not cached, retrieving from client.")
        me = await client.get_me()
        bot_id = me.id
        logger.info(f"Bot ID retrieved and cached: {bot_id}")
    else:
        logger.debug("Bot ID retrieved from cache.")
    return bot_id
from settings.logger import logger

bot_id = None

async def get_bot_id(client=None):
    """
    Retrieves and caches the bot's Telegram ID.

    :param client: The Telegram client instance.
    :return: The bot's Telegram ID.
    """
    global bot_id
    
    if client is None:
        return bot_id
        
    if bot_id is None:
        logger.debug("Bot ID not cached, retrieving from client.")
        me = await client.get_me()
        bot_id = me.id
        logger.info(f"Bot ID retrieved and cached: {bot_id}")
    else:
        logger.debug("Bot ID retrieved from cache.")
    return bot_id