# app/services/encryption.py
import re
import os
from cryptography.fernet import Fernet


def validate_password(password: str) -> bool:
    # Проверка сложности пароля
    if len(password) < 8:
        return False
    if not re.search("[a-z]", password):
        return False
    if not re.search("[A-Z]", password):
        return False
    if not re.search("[0-9]", password):
        return False
    return True


# Генерация и сохранение ключа
if not os.path.exists("secret.key"):
    with open("secret.key", "wb") as key_file:
        key_file.write(Fernet.generate_key())


def load_key():
    return open("secret.key", "rb").read()


cipher = Fernet(load_key())


def encrypt_password(password: str) -> bytes:
    if not validate_password(password):
        raise ValueError("Пароль не соответствует требованиям безопасности")
    encrypted = cipher.encrypt(password.encode())
    return encrypted


def decrypt_password(encrypted_password: str) -> str:
    return cipher.decrypt(encrypted_password.encode()).decode()
