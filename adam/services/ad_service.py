# services/ad_service.py
import ldap
from ldap import modlist
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from config import config
from services.encryption import encrypt_password
from services.utils import generate_password
from services.db_service import create_ldap_account_record


def connect_to_ad(timeout=3):
    try:
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_ALLOW)
        ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, timeout)
        ldap.set_option(ldap.OPT_TIMEOUT, timeout)

        connection = ldap.initialize(config.ldap.url)
        connection.simple_bind_s(
            config.ldap.admin_dn, config.ldap.admin_pass.get_secret_value()
        )
        return connection
    except ldap.LDAPError as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка подключения к AD: {str(e)}"
        )


def ou_exists(connection, ou_dn):
    try:
        connection.search_s(ou_dn, ldap.SCOPE_BASE, "(objectClass=organizationalUnit)")
        return True
    except ldap.NO_SUCH_OBJECT:
        return False
    except ldap.LDAPError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка проверки OU: {str(e)}")


def user_exists_in_ad(connection, username):
    """Проверяет, существует ли пользователь в AD в пределах всего домена."""
    search_filter = f"(sAMAccountName={username})"
    search_scope = ldap.SCOPE_SUBTREE
    base_dn = (
        f"DC={config.ldap.domain.split('.')[0]},DC={config.ldap.domain.split('.')[1]}"
    )
    try:
        result = connection.search_s(base_dn, search_scope, search_filter)
        exists = bool(result)
        return exists
    except ldap.LDAPError as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка проверки пользователя {username}: {str(e)}"
        )


def create_ou(connection, ou_name, base_dn):
    ou_dn = f"OU={ou_name},{base_dn}"
    if ou_exists(connection, ou_dn):
        return
    try:
        ldif = modlist.addModlist(
            {
                "objectClass": [
                    "top".encode("utf-8"),
                    "organizationalUnit".encode("utf-8"),
                ],
                "ou": ou_name.encode("utf-8"),
            }
        )
        connection.add_s(ou_dn, ldif)
    except ldap.LDAPError as e:
        raise HTTPException(
            status_code=500, detail=f"Ошибка при создании OU {ou_dn}: {str(e)}"
        )


def create_user(connection, user_data, base_dn):
    user_dn = f"CN={user_data['username']},{base_dn}"
    try:
        if not ou_exists(connection, base_dn):
            raise HTTPException(
                status_code=500, detail=f"Контейнер {base_dn} не существует"
            )
        user_account_control = b"66048"  # Normal account, enabled
        attrs = {
            "objectClass": [
                "top".encode("utf-8"),
                "person".encode("utf-8"),
                "organizationalPerson".encode("utf-8"),
                "user".encode("utf-8"),
            ],
            "cn": user_data["full_name"].encode("utf-8"),
            "sn": user_data["full_name"].split()[-1].encode("utf-8"),
            "givenName": user_data["full_name"].split()[0].encode("utf-8"),
            "displayName": user_data["full_name"].encode("utf-8"),
            "userPrincipalName": f"{user_data['username']}@{config.ldap.domain}".encode(
                "utf-8"
            ),
            "sAMAccountName": user_data["username"].encode("utf-8"),
            "mail": user_data["email"].encode("utf-8"),
            "unicodePwd": f'"{user_data["password"]}"'.encode("utf-16-le"),
            "userAccountControl": user_account_control,
        }
        ldif = modlist.addModlist(attrs)
        connection.add_s(user_dn, ldif)
    except ldap.LDAPError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании пользователя {user_dn}: {str(e)}",
        )


def create_user_in_ad(user_data):
    connection = None
    try:
        connection = connect_to_ad()
        if not connection:
            return {"error": "Не удалось подключиться к AD"}

        # Разбивает default_users_dn на части
        dn_parts = config.ldap.default_users_dn.split(",")
        ou_parts = [part.split("=")[1] for part in dn_parts if part.startswith("OU=")]
        dc_parts = ",".join([part for part in dn_parts if part.startswith("DC=")])

        # Создает OU сверху вниз
        current_dn = dc_parts
        for ou in reversed(ou_parts):
            create_ou(connection, ou, current_dn)
            current_dn = f"OU={ou},{current_dn}"

        # Создает пользователя прямо в LDAP__DEFAULT_USERS_DN
        create_user(connection, user_data, config.ldap.default_users_dn)
        return {
            "username": user_data["username"],
            "full_name": user_data["full_name"],
            "user_dn": f"CN={user_data['username']},{config.ldap.default_users_dn}",
        }
    except HTTPException as e:
        return {"error": e.detail}
    except Exception as e:
        return {"error": f"Неизвестная ошибка: {str(e)}"}
    finally:
        if connection:
            connection.unbind_s()


def create_ldap_account(user_id: UUID, db: Session, username: str):
    connection = connect_to_ad()
    password = generate_password()
    try:
        encrypted_password = encrypt_password(password)
    except ValueError as e:
        connection.unbind_s()
        raise Exception(f"Ошибка шифрования пароля: {str(e)}")

    user_data = {
        "full_name": username,
        "username": username,
        "email": f"{username}@{config.ldap.domain}",
        "first_name": username,
        "last_name": "ee",
        "password": password,
    }

    result = create_user_in_ad(user_data)
    create_ou(connection, f"{username}_ou", config.ldap.default_users_dn)

    connection.unbind_s()
    if "error" in result:
        raise Exception(result["error"])

    ad_account = create_ldap_account_record(db, user_id, username, encrypted_password)
    return ad_account


def delete_ldap_account(
    user_id: UUID, db: Session, username: str, delete_from_db: bool = True
) -> dict:
    """
    Удаляет учетную запись из Active Directory и, опционально, из базы данных.

    :param user_id: UUID пользователя SSO.
    :param db: Сессия SQLAlchemy.
    :param username: Имя пользователя AD (Kadmin_principal).
    :param delete_from_db: Если True, удаляет запись из БД после удаления из AD.
    :return: Словарь с результатом операции.
    :raises HTTPException: Если удаление не удалось.
    """
    try:
        # Подключение к AD
        connection = connect_to_ad()

        # Проверяет, существует ли учетная запись в AD
        if not user_exists_in_ad(connection, username):
            connection.unbind_s()
            raise HTTPException(
                status_code=404, detail=f"Учетная запись {username} не найдена в AD"
            )

        # Формирует DN для удаления
        admin_dn = f"CN={username},{config.ldap.default_users_dn}"

        # Удаляет учетную запись из AD
        connection.delete_s(admin_dn)
        print(f"Учетная запись {username} удалена из AD")

        # Закрывает соединение
        connection.unbind_s()

        # Удаляет запись из базы данных, если указано
        if delete_from_db:
            ldap_accounts = get_ldap_accounts_by_user_id(db, user_id)
            for account in ldap_accounts:
                if account.Kadmin_principal == username:
                    db.delete(account)
                    db.commit()
                    print(f"Запись {username} удалена из БД")
                    break
            else:
                print(f"Запись {username} не найдена в БД")

        return {
            "message": f"Учетная запись {username} успешно удалена из AD"
            + (" и БД" if delete_from_db else "")
        }

    except ldap.LDAPError as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления из AD: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка: {str(e)}")
    finally:
        if "connection" in locals():
            connection.unbind_s()
