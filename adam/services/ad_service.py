from typing import Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
import ldap
from ldap import modlist
import logging

from config import config
from services.encryption import PasswordEncryptor
from services.utils import generate_password
from services.db_service import DBService
from models.ldap_accounts import LDAPAccount
from schemas.ldap import LDAPUserAttributes

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class ADService:
    def __init__(self):
        self.connection = None
        self.encryptor = PasswordEncryptor()

    def connect(self, timeout: int = 2) -> None:
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

    def create_ou(self, ou_name: str, base_dn: str) -> None:
        """Создает Organizational Unit в AD"""
        ou_dn = f"OU={ou_name},{base_dn}"
        try:
            ldif = modlist.addModlist(
                {
                    "objectClass": [b"top", b"organizationalUnit"],
                    "ou": ou_name.encode("utf-8"),
                }
            )
            self.connection.add_s(ou_dn, ldif)
            logger.info(f"Создан OU: {ou_dn}")
        except ldap.ALREADY_EXISTS:
            logger.debug(f"OU уже существует: {ou_dn}")
            pass
        except ldap.LDAPError as e:
            raise HTTPException(
                status_code=500, detail=f"Ошибка при создании OU {ou_dn}: {str(e)}"
            )

    def add_to_groups(self, user_dn: str, group_dns: list[str], username: str) -> None:
        """Добавляет пользователя в группы по их DN"""
        for group_dn in group_dns:
            try:
                mod_attrs = [(ldap.MOD_ADD, "member", user_dn.encode("utf-8"))]
                self.connection.modify_s(group_dn, mod_attrs)
            except ldap.NO_SUCH_OBJECT:
                logger.warning(
                    f"Группа {group_dn} не найдена для {username}, пропускаем"
                )
            except ldap.LDAPError as e:
                logger.error(
                    f"Ошибка добавления {username} в группу {group_dn}: {str(e)}"
                )
                continue

    def create_account(
        self, user_id: UUID, db: Session, username: str, attributes: LDAPUserAttributes
    ) -> Tuple[LDAPAccount, bool]:
        try:
            self.connect()
            db_service = DBService(db)
            if any(
                account.Kadmin_principal == username
                for account in db_service.get_ldap_accounts_by_user_id(user_id)
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Учетная запись {username} уже существует в БД",
                )

            user_dn = f"CN={username},{config.ldap.default_users_dn}"
            logger.info(f"Создание пользователя: user_dn={user_dn}")

            # Создаём все OU
            dn_parts = config.ldap.default_users_dn.split(",")
            ou_parts = [
                part.split("=")[1] for part in dn_parts if part.startswith("OU=")
            ]
            dc_parts = ",".join([part for part in dn_parts if part.startswith("DC=")])
            current_dn = dc_parts
            for ou in reversed(ou_parts):
                self.create_ou(ou, current_dn)
                current_dn = f"OU={ou},{current_dn}"

            password = attributes.password
            encrypted_password = self.encryptor.encrypt_password(password)
            was_existing = False

            try:
                ldap_attrs = {
                    "objectClass": [
                        oc.encode("utf-8") for oc in attributes.objectClass
                    ],
                    "cn": attributes.cn.encode("utf-8"),
                    "sAMAccountName": attributes.sAMAccountName.encode("utf-8"),
                    "userPrincipalName": attributes.userPrincipalName.encode("utf-8"),
                    "mail": attributes.mail.encode("utf-8"),
                    "unicodePwd": f'"{attributes.password}"'.encode("utf-16-le"),
                    "userAccountControl": attributes.userAccountControl.encode("utf-8"),
                }
                ldif = modlist.addModlist(ldap_attrs)
                self.connection.add_s(user_dn, ldif)
                logger.info(f"Пользователь успешно создан: {user_dn}")
            except ldap.ALREADY_EXISTS:
                was_existing = True
                logger.info(
                    f"Пользователь уже существует, сбрасываем пароль: {user_dn}"
                )
                new_password = self.reset_password(username, user_dn)
                encrypted_password = self.encryptor.encrypt_password(new_password)

            self.create_ou(f"{username}_ou", config.ldap.default_users_dn)
            ad_account = db_service.create_ldap_account_record(
                user_id, username, encrypted_password
            )
            if config.ldap.member_of_groups:
                self.add_to_groups(user_dn, config.ldap.member_of_groups, username)

            return ad_account, was_existing

        except ldap.LDAPError as e:
            logger.error(f"Ошибка LDAP: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Ошибка при создании учетной записи: {str(e)}"
            )
        finally:
            self.disconnect()

    def reset_password(self, username: str, user_dn: str) -> str:
        """Сбрасывает пароль пользователя в AD"""
        try:
            new_password = generate_password()
            unicode_pwd = f'"{new_password}"'.encode("utf-16-le")
            mod_attrs = [(ldap.MOD_REPLACE, "unicodePwd", unicode_pwd)]
            self.connection.modify_s(user_dn, mod_attrs)
            logger.info(f"Пароль сброшен для {username}")
            return new_password
        except ldap.NO_SUCH_OBJECT:
            raise HTTPException(
                status_code=404, detail=f"Пользователь с DN {user_dn} не найден в AD"
            )
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
