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
    # Search for a user by username
    db_user = db.query(SSOUser).filter(SSOUser.username == username).first()

    # If the user is not found, returns 404
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    # Return the user's data
    db_user.id = db_user.id
    return db_user


@user_router.post("/", response_model=SSOUserCreate)
def create_user(user: SSOUserCreate, db: Session = Depends(get_db)):
    # Check if a user with this sso_id or username exists
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

    # Create a new user
    db_user = SSOUser(
        id=uuid4(),  # Generate UUID
        sso_id=user.sso_id,
        username=user.username,
        email=user.email,
        full_name=f"{user.first_name} {user.last_name}",
        first_name=user.first_name,
        last_name=user.last_name,
        picture=user.picture,
    )

    # Add a user to the database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return db_user


@user_router.put("/{user_id}", response_model=SSOUserResponse)
async def update_user(
    user_id: str,
    user_data: SSOUserCreate,
    db: Session = Depends(get_db),
):

    # Search user by ID
    db_user = db.query(SSOUser).filter(SSOUser.id == user_id).first()

    # If user is not found, returns 404
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Updates user's fields
    for key, value in user_data.model_dump(exclude_unset=True).items():
        setattr(db_user, key, value)

    # Save changes to database
    db.commit()
    db.refresh(db_user)
    db_user.id = str(db_user.id)

    # Return updated user data
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
