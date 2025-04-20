from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from itsdangerous import URLSafeSerializer
from uuid import UUID

from config import config
from models.database import get_db
from services.db_service import DBService

home_router = APIRouter()
templates = Jinja2Templates(directory="templates")
serializer = URLSafeSerializer(config.encryption.user_session_key.get_secret_value())


@home_router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "login.html", {"request": request, "title": "Login"}
    )


@home_router.get("/logout", include_in_schema=False)
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="auth_token")
    return response


@home_router.get("/features", response_class=HTMLResponse, include_in_schema=False)
async def features(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "features.html", {"request": request, "title": "AD.AM | Features"}
    )


@home_router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    auth_token = request.cookies.get("auth_token")
    if not auth_token:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "AD.AM",
            },
        )

    try:
        user_id = str(serializer.loads(auth_token))
    except Exception as e:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "AD.AM",
            },
        )

    # Получить пользователя через DBService
    db_service = DBService(db)
    sso_user = db_service.get_sso_user_by_id(user_id)
    if not sso_user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "AD.AM",
            },
        )

    # Получить учетные записи AD через DBService
    ad_accounts = db_service.get_ldap_accounts_by_user_id(user_id)
    # Получить список колонок из модели LDAPAccount
    from models.ldap_accounts import LDAPAccount

    columns = [col.name for col in LDAPAccount.__table__.columns]
    display_columns = {col: LDAPAccount.display_names.get(col, col) for col in columns}
    message = request.query_params.get("message")

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": sso_user,
            "ad_accounts": ad_accounts,
            "columns": columns,
            "display_columns": display_columns,
            "message": message,
            "title": "AD.AM",
        },
    )
