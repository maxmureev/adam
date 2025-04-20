from sqlalchemy import Column, String, LargeBinary, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from models.database import Base


class LDAPAccount(Base):
    __tablename__ = "ldap_accounts"

    kdc_hosts = Column(String(255), nullable=True)
    realm = Column(String(255), nullable=True)
    kadmin_server = Column(String(255), nullable=True)
    kadmin_principal = Column(String(255), primary_key=True, unique=True, nullable=True)
    kadmin_password = Column(LargeBinary, nullable=True)
    admin_dn = Column(String(255), nullable=True)
    ldap_url = Column(String(255), nullable=True)
    container_dn = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    sso_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    sso_user = relationship("SSOUser", back_populates="ldap_accounts")

    # Dictionary of display names for the user
    display_names = {
        "kdc_hosts": "KDC hosts",
        "realm": "Realm",
        "kadmin_server": "Kadmin server",
        "kadmin_principal": "Kadmin principal",
        "kadmin_password": "Kadmin password",
        "admin_dn": "Admin DN",
        "ldap_url": "LDAP URL",
        "container_dn": "Container DN",
        "created_at": "Created at",
    }
