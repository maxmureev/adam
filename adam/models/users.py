from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from models.database import Base


class SSOUser(Base):
    __tablename__ = "users"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        unique=True,
        index=True,
    )
    username = Column(String(255), unique=True)
    email = Column(String(255), unique=True)
    sso_id = Column(String(255), unique=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    picture = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    ldap_accounts = relationship(
        "LDAPAccount", back_populates="sso_user", cascade="all, delete-orphan"
    )
