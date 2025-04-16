from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from itsdangerous import URLSafeSerializer
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

from models.database import get_db
from models.users import SSOUser
from services.sso_service import sso
from config import config

auth_router = APIRouter(prefix=config.api.auth, tags=["Auth"])

serializer = URLSafeSerializer(config.encryption.user_session_key.get_secret_value())


@auth_router.get("/login")
async def auth_init():
    async with sso:
        return await sso.get_login_redirect()


@auth_router.get("/callback")
async def auth_callback(request: Request, db: Session = Depends(get_db)):
    try:
        async with sso:
            # Получает данные пользователя от SSO
            user = await sso.verify_and_process(request)
            # Проверяет, есть ли пользователь в БД
            existing_user = db.query(SSOUser).filter(SSOUser.sso_id == user.id).first()
            if not existing_user:
                # Если пользователя нет — добавить
                sso_user = SSOUser(
                    sso_id=user.id,
                    username=user.email.split("@")[0],
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    picture=user.picture,
                )
                db.add(sso_user)
                db.commit()
                db.refresh(sso_user)
                existing_user = sso_user

            token = serializer.dumps(str(existing_user.id))
            # Устанавливает куку и перенаправляет на главную страницу
            response = RedirectResponse(url="/", status_code=303)
            response.set_cookie(key="auth_token", value=token)
            return response

    except InvalidGrantError as e:
        print(f"Ошибка авторизации: {e}")
        raise HTTPException(
            status_code=400,
            detail="SSO authorization code has expired. Please log in again.",
        )

    except Exception as e:
        print(f"Ошибка при обработке callback: {e}")
        raise HTTPException(
            status_code=500,
            detail="Authorization error occurred. Please try again.",
        )
