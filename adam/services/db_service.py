from sqlalchemy.orm import Session
from uuid import UUID
from typing import List, Optional

from config import config
from models.users import SSOUser
from models.ldap_accounts import LDAPAccount
from services.encryption import PasswordEncryptor


class DBService:
    def __init__(self, db: Session):
        self.db = db
        self.encryptor = PasswordEncryptor()

    def get_sso_user_by_id(self, user_id: UUID) -> Optional[SSOUser]:
        """Получает пользователя SSO по его UUID."""
        return self.db.query(SSOUser).filter(SSOUser.id == user_id).first()

    def get_ldap_accounts_by_user_id(self, user_id: UUID) -> List[LDAPAccount]:
        """Получает все учетные записи LDAP для пользователя по его UUID."""
        accounts = (
            self.db.query(LDAPAccount).filter(LDAPAccount.sso_user_id == user_id).all()
        )
        for account in accounts:
            try:
                account.kadmin_password = self.encryptor.decrypt_password(
                    account.kadmin_password
                )
            except Exception as e:
                print(f"Ошибка расшифровки пароля: {e}")
                account.kadmin_password = "Ошибка расшифровки"
        return accounts

    def create_ldap_account_record(
        self, user_id: UUID, username: str, encrypted_password: bytes
    ) -> LDAPAccount:
        """Создает запись учетной записи LDAP в базе данных."""
        ad_account = LDAPAccount(
            sso_user_id=user_id,
            kdc_hosts=config.ldap.host,
            realm=config.ldap.realm,
            kadmin_server=config.ldap.host,
            kadmin_principal=username,
            kadmin_password=encrypted_password,
            admin_dn=f"CN={username},{config.ldap.default_users_dn}",
            ldap_url=config.ldap.url,
            container_dn=f"OU={username}_ou,{config.ldap.default_users_dn}",
        )
        self.db.add(ad_account)
        self.db.commit()
        self.db.refresh(ad_account)
        return ad_account

    def delete_ldap_account(self, user_id: UUID, username: str) -> None:
        """Удаляет учетную запись LDAP из базы данных."""
        accounts = self.get_ldap_accounts_by_user_id(user_id)
        for account in accounts:
            if account.kadmin_principal == username:
                self.db.delete(account)
                self.db.commit()
                break
