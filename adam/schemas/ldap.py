from pydantic import BaseModel, EmailStr


class LDAPUserAttributes(BaseModel):
    cn: str
    sAMAccountName: str
    userPrincipalName: str
    mail: EmailStr
    password: str
    objectClass: list[str] = ["top", "person", "organizationalPerson", "user"]
    userAccountControl: str = "66048"

    class Config:
        str_strip_whitespace = True
