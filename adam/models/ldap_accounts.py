from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship

from models.database import Base


class LDAPAccount(Base):
    __tablename__ = "ldap_accounts"

    KDC_hosts = Column(String)
    Realm = Column(String)
    Kadmin_server = Column(String)
    Kadmin_principal = Column(String, primary_key=True, unique=True, index=True)
    Kadmin_password = Column(LargeBinary)
    Admin_DN = Column(String)
    LDAP_URL = Column(String)
    Container_DN = Column(String)

    sso_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    sso_users = relationship("SSOUser", back_populates="ldap_accounts")
