import string
import secrets


def generate_password(length=20):
    """
    Generates a random password of a given length.
    The password contains letters (upper and lower case) and numbers.
    """
    characters = string.ascii_letters + string.digits
    password = "".join(secrets.choice(characters) for _ in range(length))
    return password
