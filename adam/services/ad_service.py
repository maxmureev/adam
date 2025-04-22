from typing import Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
import ldap
from ldap import modlist

from config import config
from services.encryption import PasswordEncryptor
from services.utils import generate_password
from services.db_service import DBService
from models.ldap_accounts import LDAPAccount
from schemas.ldap import LDAPUserAttributes
from services.logging_config import get_logger

logger = get_logger(__name__)


class ADService:
    def __init__(self):
        self.connection = None
        self.encryptor = PasswordEncryptor()

    def connect(self, timeout: int = 2) -> None:
        """Connect to Active Directory"""
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
                status_code=500, detail=f"AD connection error: {str(e)}"
            )

    def disconnect(self) -> None:
        """Disconnect from Active Directory"""
        if self.connection:
            self.connection.unbind_s()
            self.connection = None

    def create_ou(self, ou_name: str, base_dn: str) -> None:
        """Create Organizational Unit in Active Directory"""
        ou_dn = f"OU={ou_name},{base_dn}"
        try:
            ldif = modlist.addModlist(
                {
                    "objectClass": [b"top", b"organizationalUnit"],
                    "ou": ou_name.encode("utf-8"),
                }
            )
            self.connection.add_s(ou_dn, ldif)
            logger.debug(f"OU has been successfully created: {ou_dn}")
        except ldap.ALREADY_EXISTS:
            logger.debug(f"OU already exists: {ou_dn}")
            pass
        except ldap.LDAPError as e:
            raise HTTPException(
                status_code=500, detail=f"Error while creating OU '{ou_dn}': {str(e)}"
            )

    def add_to_groups(self, user_dn: str, group_dns: list[str], username: str) -> None:
        """Add user to groups"""
        for group_dn in group_dns:
            try:
                mod_attrs = [(ldap.MOD_ADD, "member", user_dn.encode("utf-8"))]
                self.connection.modify_s(group_dn, mod_attrs)
            except ldap.NO_SUCH_OBJECT:
                logger.warning(
                    f"Group '{group_dn}' was not found for '{username}', skip it"
                )
            except ldap.LDAPError as e:
                logger.error(
                    f"Error adding '{username}' to '{group_dn}' group: {str(e)}"
                )
                continue

    def create_account(
        self, user_id: str, db: Session, username: str, attributes: LDAPUserAttributes
    ) -> Tuple[LDAPAccount, bool]:
        try:
            self.connect()
            db_service = DBService(db)
            if any(
                account.kadmin_principal == username
                for account in db_service.get_ldap_accounts_by_user_id(user_id)
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"An account already exists in the database",
                )

            user_dn = f"CN={username},{config.ldap.default_users_dn}"

            # Create all nesting OU
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
                logger.info(f"Account successfully created: {user_dn}")

            except ldap.ALREADY_EXISTS:
                was_existing = True
                logger.info(f"Account already exists, reset password: {user_dn}")
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
            logger.error(f"Error when creating AD account: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error when creating AD account: {str(e)}"
            )
        finally:
            self.disconnect()

    def reset_password(self, username: str, user_dn: str) -> str:
        """Reset user password in AD"""
        try:
            new_password = generate_password()
            unicode_pwd = f'"{new_password}"'.encode("utf-16-le")
            mod_attrs = [(ldap.MOD_REPLACE, "unicodePwd", unicode_pwd)]
            self.connection.modify_s(user_dn, mod_attrs)
            return new_password
        except ldap.NO_SUCH_OBJECT:
            raise HTTPException(
                status_code=404, detail=f"User not found with such DN: '{user_dn}'"
            )
        except ldap.LDAPError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error resetting password for: '{username}': {str(e)}",
            )
