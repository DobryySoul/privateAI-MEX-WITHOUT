import secrets
import string


async def generate_name(length):
    # Define the characters to use in the secret
    characters = string.ascii_letters + string.digits

    # Generate a secure random secret
    secret = ''.join(secrets.choice(characters) for _ in range(length))

    return secret

import secrets
import string


async def generate_name(length):
    # Define the characters to use in the secret
    characters = string.ascii_letters + string.digits

    # Generate a secure random secret
    secret = ''.join(secrets.choice(characters) for _ in range(length))

    return secret
