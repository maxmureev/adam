# services/ad_service.py
from typing import Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
import ldap
from ldap import modlist
from pydantic import BaseModel
import logging

from config import config
from services.encryption import PasswordEncryptor
from services.utils import generate_password
from services.db_service import DBService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ADUserResponse(BaseModel):
    username: str
    full_name: str
    user_dn: str
    email: str


class ADService:
    def __init__(self):
        self.connection: Optional[ldap.LDAPObject] = None
        self.encryptor = PasswordEncryptor()

    def connect(self, timeout: int = 3) -> None:
        """Устанавливает соединение с Active Directory"""
        try:
            ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
            ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, timeout)
            ldap.set_option(ldap.OPT_TIMEOUT, timeout)

            self.connection = ldap.initialize(config.ldap.url)
            self.connection.simple_bind_s(
                config.ldap.admin_dn, config.ldap.admin_pass.get_secret_value()
            )
        except ldap.LDAPError as e:
            raise HTTPException(
                status_code=500, detail=f"Ошибка подключения к AD: {str(e)}"
            )

    def disconnect(self) -> None:
        """Закрывает соединение с AD"""
        if self.connection:
            self.connection.unbind_s()
            self.connection = None

    def ou_exists(self, ou_dn: str) -> bool:
        """Проверяет существование OU в AD"""
        try:
            self.connection.search_s(
                ou_dn, ldap.SCOPE_BASE, "(objectClass=organizationalUnit)"
            )
            return True
        except ldap.NO_SUCH_OBJECT:
            return False
        except ldap.LDAPError as e:
            raise HTTPException(status_code=500, detail=f"Ошибка проверки OU: {str(e)}")

    def user_exists(self, username: str) -> bool:
        """Проверяет существование пользователя в AD"""
        search_filter = (
            f"(&(objectClass=user)(!(objectClass=computer))(sAMAccountName={username}))"
        )
        base_dn = config.ldap.base_dn
        try:
            result = self.connection.search_s(
                base_dn, ldap.SCOPE_SUBTREE, search_filter
            )
            # Проверяем, что результат содержит реальные пользовательские записи
            valid_results = [(dn, attrs) for dn, attrs in result if dn is not None]
            if valid_results:
                logger.info(f"Found user objects for {username}: {valid_results}")
            return bool(valid_results)
        except ldap.LDAPError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка проверки пользователя {username}: {str(e)}",
            )

    def create_ou(self, ou_name: str, base_dn: str) -> None:
        """Создает Organizational Unit в AD"""
        ou_dn = f"OU={ou_name},{base_dn}"
        if self.ou_exists(ou_dn):
            return
        try:
            ldif = modlist.addModlist(
                {
                    "objectClass": [b"top", b"organizationalUnit"],
                    "ou": ou_name.encode("utf-8"),
                }
            )
            self.connection.add_s(ou_dn, ldif)
        except ldap.LDAPError as e:
            raise HTTPException(
                status_code=500, detail=f"Ошибка при создании OU {ou_dn}: {str(e)}"
            )

    def create_account(
        self, user_id: UUID, db: Session, username: str
    ) -> "LDAPAccount":
        """Создает учетную запись в AD и сохраняет её в БД"""
        try:
            self.connect()
            logger.info(
                f"Creating account for {username}, domain: {config.ldap.domain}"
            )

            # Проверка существования пользователя
            if self.user_exists(username):
                raise HTTPException(
                    status_code=409, detail=f"Учетная запись {username} уже существует"
                )

            # Генерация и шифрование пароля
            password = generate_password()
            encrypted_password = self.encryptor.encrypt_password(password)

            # Формирование данных пользователя
            user_data = {
                "full_name": username,
                "username": username,
                "email": f"{username}@{config.ldap.domain}",
                "first_name": username,
                "last_name": "ee",
                "password": password,
            }

            # Создание OU в default_users_dn
            dn_parts = config.ldap.default_users_dn.split(",")
            ou_parts = [
                part.split("=")[1] for part in dn_parts if part.startswith("OU=")
            ]
            dc_parts = ",".join([part for part in dn_parts if part.startswith("DC=")])

            current_dn = dc_parts
            for ou in reversed(ou_parts):
                self.create_ou(ou, current_dn)
                current_dn = f"OU={ou},{current_dn}"

            # Создание пользователя в AD
            user_dn = f"CN={username},{config.ldap.default_users_dn}"
            if not self.ou_exists(config.ldap.default_users_dn):
                raise HTTPException(
                    status_code=500,
                    detail=f"Контейнер {config.ldap.default_users_dn} не существует",
                )

            user_account_control = b"66048"  # Normal account, enabled
            attrs = {
                "objectClass": [b"top", b"person", b"organizationalPerson", b"user"],
                "cn": user_data["full_name"].encode("utf-8"),
                "sn": user_data["full_name"].split()[-1].encode("utf-8"),
                "givenName": user_data["full_name"].split()[0].encode("utf-8"),
                "displayName": user_data["full_name"].encode("utf-8"),
                "userPrincipalName": f"{user_data['username']}@{config.ldap.domain}".encode(
                    "utf-8"
                ),
                "sAMAccountName": user_data["username"].encode("utf-8"),
                "mail": user_data["email"].encode("utf-8"),
                "unicodePwd": f'"{password}"'.encode("utf-16-le"),
                "userAccountControl": user_account_control,
            }
            ldif = modlist.addModlist(attrs)
            self.connection.add_s(user_dn, ldif)

            # Создание пользовательского OU
            self.create_ou(f"{username}_ou", config.ldap.default_users_dn)

            # Сохранение в БД
            db_service = DBService(db)
            ad_account = db_service.create_ldap_account_record(
                user_id, username, encrypted_password
            )

            return ad_account

        except ldap.ALREADY_EXISTS:
            raise HTTPException(
                status_code=409, detail=f"Учетная запись {username} уже существует"
            )
        except ldap.LDAPError as e:
            raise HTTPException(
                status_code=500, detail=f"Ошибка при создании учетной записи: {str(e)}"
            )
        finally:
            self.disconnect()

    def delete_account(
        self, user_id: UUID, db: Session, username: str, delete_from_db: bool = True
    ) -> dict:
        """Удаляет учетную запись из AD и, опционально, из БД"""
        try:
            self.connect()
            if not self.user_exists(username):
                raise HTTPException(
                    status_code=404, detail=f"Учетная запись {username} не найдена в AD"
                )

            admin_dn = f"CN={username},{config.ldap.default_users_dn}"
            self.connection.delete_s(admin_dn)

            if delete_from_db:
                db_service = DBService(db)
                db_service.delete_ldap_account(user_id, username)

            return {
                "message": f"Учетная запись {username} успешно удалена из AD"
                + (" и БД" if delete_from_db else "")
            }
        finally:
            self.disconnect()

    def reset_password(self, username: str, user_dn: str) -> str:
        """Сбрасывает пароль пользователя в AD и возвращает новый пароль."""
        try:
            new_password = generate_password()
            unicode_pwd = f'"{new_password}"'.encode("utf-16-le")
            mod_attrs = [(ldap.MOD_REPLACE, "unicodePwd", unicode_pwd)]
            self.connection.modify_s(user_dn, mod_attrs)
            logger.info(f"Password reset for {username} at {user_dn}")
            return new_password
        except ldap.INSUFFICIENT_ACCESS:
            raise HTTPException(
                status_code=403,
                detail=f"Недостаточно прав для сброса пароля {username}",
            )
        except ldap.LDAPError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при сбросе пароля для {username}: {str(e)}",
            )
