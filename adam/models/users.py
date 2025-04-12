from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
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
    sso_id = Column(String, unique=True)
    username = Column(String, unique=True)
    email = Column(String, unique=True)
    first_name = Column(String)
    last_name = Column(String)
    picture = Column(String)

    ldap_accounts = relationship("LDAPAccount", back_populates="sso_users")
