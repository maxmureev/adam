import re
import os
from cryptography.fernet import Fernet


class PasswordEncryptor:
    def __init__(self, key_path: str = "secret.key"):
        self.key_path = key_path
        self.cipher = self._load_or_generate_key()

    def _load_or_generate_key(self) -> Fernet:
        """Загружает или генерирует ключ шифрования."""
        if not os.path.exists(self.key_path):
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as key_file:
                key_file.write(key)
        with open(self.key_path, "rb") as key_file:
            key = key_file.read()
        return Fernet(key)

    def validate_password(self, password: str) -> bool:
        """Проверяет сложность пароля."""
        if len(password) < 8:
            return False
        if not re.search("[a-z]", password):
            return False
        if not re.search("[A-Z]", password):
            return False
        if not re.search("[0-9]", password):
            return False
        return True

    def encrypt_password(self, password: str) -> bytes:
        """Шифрует пароль."""
        if not self.validate_password(password):
            raise ValueError("Пароль не соответствует требованиям безопасности")
        return self.cipher.encrypt(password.encode())

    def decrypt_password(self, encrypted_password: bytes) -> str:
        """Расшифровывает пароль."""
        try:
            return self.cipher.decrypt(encrypted_password).decode()
        except Exception as e:
            raise ValueError(f"Ошибка расшифровки пароля: {str(e)}")
