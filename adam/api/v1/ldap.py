# api/v1/ldap.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from config import config
from models.database import get_db
from services.ad_service import ADService
from services.db_service import DBService
from services.utils import generate_username

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ldap_router = APIRouter(prefix=f"{config.api.v1.users}/{{user_id}}", tags=["LDAP"])


@ldap_router.get("/ldap_account")
async def get_ldap_accounts(user_id: UUID, db: Session = Depends(get_db)):
    logger.info(f"GET /api/v1/user/{user_id}/ldap_account called")
    db_service = DBService(db)
    sso_user = db_service.get_sso_user_by_id(user_id)
    if not sso_user:
        raise HTTPException(status_code=404, detail="User not found")
    ldap_accounts = db_service.get_ldap_accounts_by_user_id(user_id)
    return ldap_accounts


@ldap_router.post("/ldap_account")
async def create_ldap_account_route(
    user_id: UUID, request: Request, db: Session = Depends(get_db)
):
    logger.info(f"POST /api/v1/user/{user_id}/ldap_account called")
    db_service = DBService(db)
    sso_user = db_service.get_sso_user_by_id(user_id)
    if not sso_user:
        error_message = "Пользователь не найден"
        logger.info(f"User not found: {user_id}")
        if "application/json" in request.headers.get("Accept", ""):
            return JSONResponse(status_code=404, content={"detail": error_message})
        return RedirectResponse(url=f"/?message={error_message}", status_code=303)

    username = generate_username(sso_user.email)
    ad_service = ADService()

    try:
        ad_account = ad_service.create_account(user_id, db, username)
        logger.info(f"Account created for {username}: {ad_account.__dict__}")
    except HTTPException as e:
        error_message = e.detail
        logger.error(f"Creation error: {error_message}")
        if "application/json" in request.headers.get("Accept", ""):
            return JSONResponse(
                status_code=e.status_code, content={"detail": error_message}
            )
        return RedirectResponse(url=f"/?message={error_message}", status_code=303)

    success_message = "Учётная запись AD успешно создана"
    logger.info(f"Success: {success_message}")
    if "application/json" in request.headers.get("Accept", ""):
        account_dict = {
            "id": str(ad_account.id),
            "sso_user_id": str(ad_account.sso_user_id),
            "Kadmin_principal": ad_account.Kadmin_principal,
            "Admin_DN": ad_account.Admin_DN,
        }
        return JSONResponse(
            status_code=200,
            content={"message": success_message, "account": account_dict},
        )
    return RedirectResponse(url=f"/?message={success_message}", status_code=303)


@ldap_router.post("/ldap_account/reset_password")
async def reset_ldap_account_password(user_id: UUID, db: Session = Depends(get_db)):
    logger.info(f"POST /api/v1/user/{user_id}/ldap_account/reset_password called")
    db_service = DBService(db)
    ad_service = ADService()

    try:
        ad_service.connect()
        sso_user = db_service.get_sso_user_by_id(user_id)
        if not sso_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")

        ldap_username = generate_username(sso_user.email)
        accounts = db_service.get_ldap_accounts_by_user_id(user_id)
        account_found = None
        for account in accounts:
            if account.Kadmin_principal == ldap_username:
                account_found = account
                break
        if not account_found:
            raise HTTPException(
                status_code=404, detail=f"Запись для {ldap_username} не найдена в БД"
            )

        user_dn = f"CN={ldap_username},{config.ldap.default_users_dn}"
        new_password = ad_service.reset_password(ldap_username, user_dn)
        encrypted_password = ad_service.encryptor.encrypt_password(new_password)

        account_found.Kadmin_password = encrypted_password
        db.commit()
        db.refresh(account_found)

        success_message = f"Пароль для {ldap_username} успешно сброшен"
        logger.info(success_message)
        return RedirectResponse(url=f"/?message={success_message}", status_code=303)

    except HTTPException as e:
        logger.error(f"Reset password error: {e.detail}")
        return RedirectResponse(url=f"/?message={e.detail}", status_code=303)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return RedirectResponse(
            url=f"/?message=Ошибка при сбросе пароля: {str(e)}", status_code=303
        )
    finally:
        ad_service.disconnect()
