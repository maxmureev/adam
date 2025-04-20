from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import uuid4

from models.database import get_db
from models.users import SSOUser
from schemas import SSOUserCreate
from schemas import SSOUserResponse
from config import config


user_router = APIRouter(prefix=config.api.v1.users, tags=["User"])


@user_router.get("/{username}", response_model=SSOUserResponse)
def get_id_by_username(username: str, db: Session = Depends(get_db)):
    # Ищет пользователя по username
    db_user = db.query(SSOUser).filter(SSOUser.username == username).first()

    # Если пользователь не найден, возвращает 404
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Возвращает данные пользователя
    db_user.id = db_user.id
    return db_user


@user_router.post("/", response_model=SSOUserCreate)
def create_user(user: SSOUserCreate, db: Session = Depends(get_db)):
    # Проверяет, существует ли пользователь с таким sso_id или username
    db_user_sso = db.query(SSOUser).filter(SSOUser.sso_id == user.sso_id).first()
    db_user_username = (
        db.query(SSOUser).filter(SSOUser.username == user.username).first()
    )

    if db_user_sso:
        raise HTTPException(
            status_code=400, detail="User with this SSO ID already exists"
        )
    if db_user_username:
        raise HTTPException(
            status_code=400, detail="User with this username already exists"
        )

    # Создает нового пользователя
    db_user = SSOUser(
        id=uuid4(),  # Генерирует UUID
        sso_id=user.sso_id,
        username=user.username,
        email=user.email,
        full_name=f"{user.first_name} {user.last_name}",
        first_name=user.first_name,
        last_name=user.last_name,
        picture=user.picture,
    )

    # Добавляет пользователя в БД
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@user_router.put("/{user_id}", response_model=SSOUserResponse)
async def update_user(
    user_id: str,  # UUID пользователя
    user_data: SSOUserCreate,  # Данные для обновления
    db: Session = Depends(get_db),  # Сессия БД
):

    # Ищет пользователя по ID
    db_user = db.query(SSOUser).filter(SSOUser.id == user_id).first()

    # Если пользователь не найден, возвращает 404
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Обновляет поля пользователя
    for key, value in user_data.model_dump(exclude_unset=True).items():
        setattr(db_user, key, value)

    # Сохраняет изменения в БД
    db.commit()
    db.refresh(db_user)

    # Преобразует UUID в строку для ответа
    db_user.id = str(db_user.id)

    # Возвращает обновленные данные пользователя
    return db_user


@user_router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
):
    db_user = db.query(SSOUser).filter(SSOUser.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(db_user)
    db.commit()
    return {"message": "User deleted successfully"}
