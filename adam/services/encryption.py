from cryptography.fernet import Fernet
from config import config


class PasswordEncryptor:
    def __init__(self):
        self.cipher = Fernet(config.encryption.secret_key.get_secret_value().encode())

    def encrypt_password(self, password: str) -> bytes:
        """Encrypt the password"""
        return self.cipher.encrypt(password.encode())

    def decrypt_password(self, encrypted_password: bytes) -> str:
        """Decrypt the password"""
        try:
            return self.cipher.decrypt(encrypted_password).decode()
        except Exception as e:
            raise ValueError(f"Password decryption error: {str(e)}")
