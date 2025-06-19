import string
import secrets
import re


def generate_password(length=20):
    """
    Generates a random password of a given length.
    The password contains letters (upper and lower case) and numbers.
    """
    characters = string.ascii_letters + string.digits
    password = "".join(secrets.choice(characters) for _ in range(length))
    return password


def dn_keys_to_upper(dn: str) -> str:
    """
    Converts all occurrences of OU=, DC=, CN= in the DN string to uppercase.
    """

    def repl(match):
        return match.group(1).upper() + match.group(2)

    return re.sub(r"((?:ou|dc|cn)=)([^,]+)", repl, dn, flags=re.IGNORECASE)
