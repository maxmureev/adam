import secrets
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List, Optional


class EncryptionConfig(BaseModel):
    secret_key: SecretStr
    user_session_key: SecretStr


class RunConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class ApiV1Prefix(BaseModel):
    prefix: str = "/v1"
    users: str = "/users"


class ApiPrefix(BaseModel):
    prefix: str = "/api"
    auth: str = "/auth"
    v1: ApiV1Prefix = ApiV1Prefix()


class SSOConfig(BaseModel):
    client_id: SecretStr
    client_secret: SecretStr
    redirect_uri: str
    allow_insecure_http: bool


class LDAPConfig(BaseModel):
    domain: str
    base_dn: str
    default_users_ou: Optional[str] = None
    member_of_groups: Optional[List[str]] = None
    url: str
    admin_dn: str
    admin_pass: SecretStr
    default_users_dn: str
    host: Optional[str] = None
    realm: Optional[str] = None
    nested_dn: Optional[str] = None


class DatabaseConfig(BaseModel):
    path: str = "data/database.sqlite"
    url: str = f"sqlite:///{path}"
    # url: str = f"sqlite+aiosqlite:///{path}"


class UsersConfig(BaseModel):
    cookie_ttl: int = 10_368_000  # 120 days or ~1/3 year


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    db: DatabaseConfig = DatabaseConfig()
    run: RunConfig = RunConfig()
    api: ApiPrefix = ApiPrefix()
    users: UsersConfig = UsersConfig()
    sso: SSOConfig
    ldap: LDAPConfig
    encryption: EncryptionConfig

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._setup_ldap_derivatives()

    def _setup_ldap_derivatives(self) -> None:
        """Вычисляет производные LDAP-значения после инициализации."""
        self.ldap.nested_dn = self._compute_nested_dn()
        self.ldap.host = self.ldap.url.split("//")[-1]
        self.ldap.realm = self._compute_realm()

    def _compute_nested_dn(self) -> Dict[str, str]:
        """Вычисляет вложенные DN для OU."""
        ou_list = [
            ou.split("=")[1]
            for ou in self.ldap.default_users_dn.split(",")
            if ou.startswith("OU=")
        ]
        return {
            ou_list[i]: ",".join(self.ldap.default_users_dn.split(",")[i + 1 :])
            for i in range(len(ou_list))
        }

    def _compute_realm(self) -> str:
        """Вычисляет LDAP realm из base_dn."""
        domain_parts = [
            part.split("=")[1]
            for part in self.ldap.default_users_dn.split(",")
            if part.startswith("DC=")
        ]
        return ".".join(domain_parts).upper()


# Создание экземпляра настроек
config = Settings()
