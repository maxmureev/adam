# api/v1/ldap.py
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from config import config
from models.database import get_db
from services.ad_service import create_ldap_account, connect_to_ad
from services.db_service import get_sso_user_by_id, get_ldap_accounts_by_user_id
from services.utils import generate_username

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ldap_router = APIRouter(prefix=f"{config.api.v1.users}/{{user_id}}", tags=["LDAP"])


@ldap_router.get("/ldap_account")
async def get_ldap_accounts(user_id: UUID, db: Session = Depends(get_db)):
    logger.info(f"GET /api/v1/user/{user_id}/ldap_account called")
    sso_user = get_sso_user_by_id(db, user_id)
    if not sso_user:
        raise HTTPException(status_code=404, detail="User not found")
    ldap_accounts = get_ldap_accounts_by_user_id(db, user_id)
    return ldap_accounts


@ldap_router.post("/ldap_account")
async def create_ldap_account_route(
    user_id: UUID, request: Request, db: Session = Depends(get_db)
):
    logger.info(f"POST /api/v1/user/{user_id}/ldap_account called")
    sso_user = get_sso_user_by_id(db, user_id)
    if not sso_user:
        error_message = "Пользователь не найден"
        logger.info(f"User not found: {user_id}")
        if "application/json" in request.headers.get("Accept", ""):
            return JSONResponse(status_code=404, content={"detail": error_message})
        return RedirectResponse(url=f"/?message={error_message}", status_code=303)

    username = generate_username(sso_user.email)

    try:
        ad_account = create_ldap_account(user_id, db, username)
        logger.info(f"Account created for {username}: {ad_account.__dict__}")
    except Exception as e:
        error_message = str(e)
        if "Учетная запись с таким именем уже существует" in error_message:
            logger.warning(f"Account already exists: {username}")
            if "application/json" in request.headers.get("Accept", ""):
                return JSONResponse(status_code=409, content={"detail": error_message})
            return RedirectResponse(url=f"/?message={error_message}", status_code=303)
        error_message = f"Ошибка при создании учетной записи: {error_message}"
        logger.error(f"Creation error: {error_message}")
        if "application/json" in request.headers.get("Accept", ""):
            return JSONResponse(status_code=500, content={"detail": error_message})
        return RedirectResponse(url=f"/?message={error_message}", status_code=303)

    success_message = "Учётная запись AD успешно создана"
    logger.info(f"Success: {success_message}")
    if "application/json" in request.headers.get("Accept", ""):
        account_dict = {
            "id": str(ad_account.id),
            "sso_user_id": str(ad_account.sso_user_id),
            "Kadmin_principal": ad_account.Kadmin_principal,
            "Admin_DN": ad_account.Admin_DN,
            "Admin_PW": ad_account.Admin_PW,
        }
        return JSONResponse(
            status_code=200,
            content={"message": success_message, "account": account_dict},
        )
    return RedirectResponse(url=f"/?message={success_message}", status_code=303)
