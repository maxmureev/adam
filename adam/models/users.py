from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4

from models.database import Base


class SSOUser(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        unique=True,
        index=True,
    )

    username = Column(String(255), unique=True)
    email = Column(String(255), unique=True)
    sso_id = Column(String(255), unique=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    picture = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    ldap_accounts = relationship("LDAPAccount", back_populates="sso_users")
