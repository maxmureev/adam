from adam.services.ad_service import create_user_in_ad
from adam.services.db_service import save_user_to_db
from adam.services.utils import generate_password
import config


user = "t.user"
user_name = user.replace(".", "_")
ou_name = f"{user_name.replace(".", "_")}_ou"
password = generate_password()

# Данные для создания пользователя
user_data = {
    "full_name": user_name,
    "username": user_name,
    "email": f"{user_name}@{config.ldap_domain}",
    "first_name": user_name,
    "last_name": "ee",
    "password": password,
    "ou_name": ou_name,
    "user_dn": f"CN={user_name},{config.ldap_default_users_dn}",
}


# Создание пользователя в AD
create_user_in_ad(user_data)
# result = create_user_in_ad(user_data)
# print(result)
