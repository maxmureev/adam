from sqlalchemy.orm import Session
from typing import List, Optional

from config import config
from models.users import SSOUser
from models.ldap_accounts import LDAPAccount
from services.encryption import PasswordEncryptor
from services.logging_config import get_logger
from services.utils import dn_keys_to_upper

logger = get_logger(__name__)


class DBService:
    def __init__(self, db: Session):
        self.db = db
        self.encryptor = PasswordEncryptor()

    def get_sso_user_by_id(self, user_id: str) -> Optional[SSOUser]:
        """Get the SSO user by its UUID"""
        return self.db.query(SSOUser).filter(SSOUser.id == user_id).first()

    def get_ldap_accounts_by_user_id(self, user_id: str) -> List[LDAPAccount]:
        """Gets all LDAP accounts for a user by its UUID"""
        accounts = (
            self.db.query(LDAPAccount).filter(LDAPAccount.sso_user_id == user_id).all()
        )
        for account in accounts:
            try:
                account.kadmin_password = self.encryptor.decrypt_password(
                    account.kadmin_password
                )
            except Exception as e:
                logger.error(f"Password decryption error: {e}")
                account.kadmin_password = "Decryption error"
        return accounts

    def create_ldap_account_record(
        self, user_id: str, username: str, encrypted_password: bytes
    ) -> LDAPAccount:
        """Creates LDAP account record in the database"""
        admin_dn = dn_keys_to_upper(f"CN={username},{config.ldap.default_users_dn}")
        container_dn = dn_keys_to_upper(
            f"OU={username}_ou,{config.ldap.default_users_dn}"
        )
        ad_account = LDAPAccount(
            sso_user_id=user_id,
            kdc_hosts=config.ldap.host,
            realm=config.ldap.realm,
            kadmin_server=config.ldap.host,
            kadmin_principal=username,
            kadmin_password=encrypted_password,
            admin_dn=admin_dn,
            ldap_url=config.ldap.url,
            container_dn=container_dn,
        )
        self.db.add(ad_account)
        self.db.commit()
        self.db.refresh(ad_account)
        return ad_account

    def delete_ldap_account(self, user_id: str, username: str) -> None:
        """Deletes LDAP account from the database"""
        accounts = self.get_ldap_accounts_by_user_id(user_id)
        for account in accounts:
            if account.kadmin_principal == username:
                self.db.delete(account)
                self.db.commit()
                break
