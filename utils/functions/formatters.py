from settings.logger import logger


def format_user_info_message(sender, user_message):
    """
    Форматирует сообщение с информацией о пользователе для первого сообщения.
    
    Args:
        sender: Объект отправителя сообщения с атрибутами first_name, last_name, username
        user_message: Исходное сообщение пользователя
        
    Returns:
        str: Отформатированное сообщение с информацией о пользователе
    """
    user_info = {
        'first_name': sender.first_name,
        'last_name': sender.last_name,
        'username': sender.username
    }
    
    logger.info("First message from user, add user info to message")
    
    formatted_message = (
        f"User info:\n"
        f"First name: {user_info.get('first_name')}\n"
        f"Last name: {user_info.get('last_name')}\n"
        f"Username: @{user_info.get('username')}\n"
        f"---\n"
        f"{user_message}"
    )
    
    return formatted_message