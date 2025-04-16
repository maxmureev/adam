import re
from cryptography.fernet import Fernet
from config import config  # Импорт конфигурации

class PasswordEncryptor:
    def __init__(self):
        self.cipher = Fernet(config.encryption.secret_key.get_secret_value().encode())

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
