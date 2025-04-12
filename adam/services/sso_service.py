from fastapi_sso.sso.yandex import YandexSSO

from config import config

sso = YandexSSO(
    client_id=config.sso.client_id.get_secret_value(),
    client_secret=config.sso.client_secret.get_secret_value(),
    redirect_uri=config.sso.redirect_uri,
    allow_insecure_http=True,
)
