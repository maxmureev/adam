from fastapi import APIRouter
from .user import user_router
from .ldap import ldap_router
from config import config

v1_router = APIRouter(prefix=config.api.v1.prefix)

v1_router.include_router(user_router)
v1_router.include_router(ldap_router)
