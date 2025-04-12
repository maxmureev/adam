from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from config import config
from models.users import SSOUser
from models.ldap_accounts import LDAPAccount
from services.encryption import decrypt_password


def get_sso_user_by_id(db: Session, user_id: UUID) -> SSOUser | None:
    """Получает пользователя SSO по его UUID."""
    return db.query(SSOUser).filter(SSOUser.id == user_id).first()


# def get_ldap_accounts_by_user_id(db: Session, user_id: UUID) -> List[LDAPAccount]:
#     """Получает все учетные записи LDAP для пользователя по его UUID."""
#     return db.query(LDAPAccount).filter(LDAPAccount.sso_user_id == user_id).all()


def get_ldap_accounts_by_user_id(db: Session, user_id: UUID) -> List[LDAPAccount]:
    accounts = db.query(LDAPAccount).filter(LDAPAccount.sso_user_id == user_id).all()
    for account in accounts:
        try:
            account.Kadmin_password = decrypt_password(account.Kadmin_password.decode())
        except Exception as e:
            print(f"Ошибка расшифровки пароля: {e}")
            account.Kadmin_password = "Ошибка расшифровки"
    return accounts


def create_ldap_account_record(
    db: Session,
    user_id: UUID,
    username: str,
    encrypted_password: bytes,
) -> LDAPAccount:
    """Создает запись учетной записи LDAP в базе данных."""
    ad_account = LDAPAccount(
        sso_user_id=user_id,
        KDC_hosts=config.ldap.host,
        Realm=config.ldap.realm,
        Kadmin_server=config.ldap.host,
        Kadmin_principal=username,
        Kadmin_password=encrypted_password,
        Admin_DN=f"CN={username},{config.ldap.default_users_dn}",
        LDAP_URL=config.ldap.url,
        Container_DN=f"OU={username}_ou,{config.ldap.default_users_dn}",
    )
    db.add(ad_account)
    db.commit()
    db.refresh(ad_account)
    return ad_account
