from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from config import config
from models.database import get_db
from services.ad_service import ADService
from services.db_service import DBService
from services.utils import generate_password
from schemas.ldap import LDAPUserAttributes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ldap_router = APIRouter(prefix=f"{config.api.v1.users}/{{user_id}}", tags=["LDAP"])


@ldap_router.get("/ldap_account")
async def get_ldap_accounts(user_id: str, db: Session = Depends(get_db)):
    logger.info(f"GET /api/v1/user/{user_id}/ldap_account called")
    db_service = DBService(db)
    sso_user = db_service.get_sso_user_by_id(user_id)
    if not sso_user:
        raise HTTPException(status_code=404, detail="User not found")
    ldap_accounts = db_service.get_ldap_accounts_by_user_id(user_id)
    return ldap_accounts


@ldap_router.post("/ldap_account")
async def create_ldap_account(
    user_id: str, request: Request, db: Session = Depends(get_db)
):
    logger.info(f"POST /api/v1/user/{user_id}/ldap_account called")
    db_service = DBService(db)
    sso_user = db_service.get_sso_user_by_id(user_id)
    if not sso_user:
        error_message = "Пользователь не найден"
        logger.info(f"User not found: {user_id}")
        if "application/json" in request.headers.get("Accept", ""):
            return JSONResponse(status_code=404, content={"detail": error_message})
        request.session["flash_message"] = error_message
        return RedirectResponse(url="/", status_code=303)

    try:
        username = sso_user.email.split("@")[0].replace(".", "_")
    except IndexError:
        error_message = "Некорректный email пользователя"
        logger.error(f"Invalid email format: {sso_user.email}")
        if "application/json" in request.headers.get("Accept", ""):
            return JSONResponse(status_code=400, content={"detail": error_message})
        request.session["flash_message"] = error_message
        return RedirectResponse(url="/", status_code=303)

    logger.info(f"Сгенерирован username: {username}")
    password = generate_password()

    try:
        attributes = LDAPUserAttributes(
            cn=username,
            sAMAccountName=username,
            userPrincipalName=f"{username}@{config.ldap.domain}",
            mail=sso_user.email,
            password=password,
        )
        logger.info(f"Созданы атрибуты для {username}: {attributes.dict()}")
    except ValueError as e:
        error_message = f"Ошибка валидации атрибутов: {str(e)}"
        logger.error(error_message)
        if "application/json" in request.headers.get("Accept", ""):
            return JSONResponse(status_code=400, content={"detail": error_message})
        request.session["flash_message"] = error_message
        return RedirectResponse(url="/", status_code=303)

    ad_service = ADService()
    try:
        ad_account, was_existing = ad_service.create_account(
            user_id, db, username, attributes
        )
        logger.info(f"Account processed for {username}: {vars(ad_account)}")
        success_message = (
            "Учётная запись AD уже существовала, пароль сброшен"
            if was_existing
            else "Учётная запись AD успешно создана"
        )
    except HTTPException as e:
        error_message = e.detail
        logger.error(f"Creation error: {error_message}")
        if "application/json" in request.headers.get("Accept", ""):
            return JSONResponse(
                status_code=e.status_code, content={"detail": error_message}
            )
        request.session["flash_message"] = error_message
        return RedirectResponse(url="/", status_code=303)

    logger.info(f"Success: {success_message}")
    if "application/json" in request.headers.get("Accept", ""):
        account_dict = {
            "sso_user_id": str(ad_account.sso_user_id),
            "kadmin_principal": ad_account.kadmin_principal,
            "admin_DN": ad_account.admin_dn,
            "kadmin_password": db_service.encryptor.decrypt_password(
                ad_account.kadmin_password
            ),
        }
        return JSONResponse(
            status_code=200,
            content={"message": success_message, "account": account_dict},
        )
    request.session["flash_message"] = success_message
    return RedirectResponse(url="/", status_code=303)


@ldap_router.post("/ldap_account/reset_password")
async def reset_ldap_account_password(
    user_id: str, request: Request, db: Session = Depends(get_db)
):
    logger.info(f"POST /api/v1/user/{user_id}/ldap_account/reset_password called")
    db_service = DBService(db)
    ad_service = ADService()

    try:
        ad_service.connect()
        sso_user = db_service.get_sso_user_by_id(user_id)
        if not sso_user:
            error_message = "Пользователь не найден"
            request.session["flash_message"] = error_message
            raise HTTPException(status_code=404, detail=error_message)

        ldap_username = sso_user.email.split("@")[0].replace(".", "_")
        accounts = db_service.get_ldap_accounts_by_user_id(user_id)
        account_found = None
        for account in accounts:
            if account.kadmin_principal == ldap_username:
                account_found = account
                break
        if not account_found:
            error_message = f"Запись для {ldap_username} не найдена в БД"
            request.session["flash_message"] = error_message
            raise HTTPException(status_code=404, detail=error_message)

        user_dn = f"CN={ldap_username},{config.ldap.default_users_dn}"
        new_password = ad_service.reset_password(ldap_username, user_dn)
        encrypted_password = ad_service.encryptor.encrypt_password(new_password)

        account_found.kadmin_password = encrypted_password
        db.commit()
        db.refresh(account_found)

        success_message = f"Пароль для {ldap_username} успешно сброшен"
        logger.info(success_message)
        request.session["flash_message"] = success_message
        return RedirectResponse(url="/", status_code=303)

    except HTTPException as e:
        logger.error(f"Reset password error: {e.detail}")
        request.session["flash_message"] = e.detail
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        error_message = f"Ошибка при сбросе пароля: {str(e)}"
        logger.error(f"Unexpected error: {error_message}")
        request.session["flash_message"] = error_message
        return RedirectResponse(url="/", status_code=303)
    finally:
        ad_service.disconnect()
