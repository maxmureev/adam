# Active Directory Account Manager

Проект задумывался как способ автоматизировать создание учетных записей в Active Directory.
Чтобы любой сотрудник мог самостоятельно создать AD аккаунт или сменить для него пароль не беспокоя администратора.

## Задача и требования от заказчика

- Создать страничку, которая будет из себя представлять сервис по созданию учетки в AD
- Желательно, чтобы создание учетки в AD работало без участия человека
- Показывать пользователю определенным образом значения аккаунта, в их числе логин, пароль и некоторые параметры
  подключения к контроллеру домена
- Обычно каждому пользователю достаточно одного AD аккаунта
- Авторизация должна производиться через корпоративный SSO
- В AD должен быть
    - Создан пользователь
    - Создан organisation unit для этого пользователя
    - Добавить пользователя в уже существующую группу

## Реализация

Договор о наименованиях: \
**Пользователь** (user) - пользоватесь сервиса, который логинится через SSO и хранится в таблице users. \
**Аккаунт** (учетная запись) - LDAP пользователь, который и требуется создать, хранится в таблице ldap_accounts.

В требованиях подразумевается, что у пользователя может быть только один LDAP аккаунт и только в AD реализации.
В частности, сброс пароля реализован исходя из предпосылки одного аккаунта на пользователя.
Задел для создания нескольких аккаунтов частично был предусмотрен.
Для подключения других реализаций LDAP необходимо расширять функционал сервиса.

### Поведение

- Пользователь логинится через SSO
- Username для AD аккаунта формируется из email, указанного в профиле SSO
- Сервис проверяет в базе наличие записи о существовании AD учетки для этого пользователя
    - Если запись существует, пользователю показываются параметры подключения
    - Если записи не существует, предлагается создать новый аккаунт
- При создании AD аккаунта
    - Если аккаунт с таким username не существует в AD
        - Генерируется пароль
        - Создаётся учётная запись
        - Создаётся пользовательский OU
        - Назначаются права на этот UO путем добавления в группу
    - Если аккаунт с таким username уже существует в AD
        - Генерируется новый пароль
        - Пароль аккаунта принудительно сбрасывается на новый
    - Данные аккаунта (username, пароль в зашифрованном виде) сохраняются в базе данных и связываются с профилем
      пользователя. Это предотвращает необходимость сброса пароля для его отображения, так как пароль в AD нельзя
      посмотреть, а только сбросить
- После появления записи об AD аккаунте в БД, результат отображается на страничке в виде списка параметров для настройки
  ADCM

### Заметки

#### Reverse proxy

Nginx прикручивать в проекте не стал, поскольку разворачиваться будет на имеющейся инфраструктуре
и девопсы сами сделают как считают нужным.

#### Alembic

Внедрение Алембика ~~сломало~~ изменило тип объекта id.
При любой повторной миграции он падал с ошибкой, т.к. хотел изменить тип колонки на UUID:

```log
[SQL: ALTER TABLE ldap_accounts ALTER COLUMN sso_user_id TYPE UUID]
```

Но поскольку Sqlite не умеет UUID, пришлось изменить тип с

```python
id = Column(
    UUID(as_uuid=True),
    default=uuid4,
    ...
)
```

на

```python
id = Column(
    String(36),
    default=lambda: str(uuid4()),
    ...
)
```

Что повлекло изменение типов во всем проекте:

```txt
# Вторая модель
sso_user_id = Column(UUID(as_uuid=True), ...) -> sso_user_id = Column(String(36), ...)
# Извлечение токена из куки в web/home.py
user_id = UUID(serializer.loads(auth_token)) -> user_id = str(serializer.loads(auth_token))
# В параметрах функциях
user_id: UUID, ... -> user_id: str, ...
```

Как сделать красиво и просто в голову не пришло. Зато теперь можно применять миграции.

## Run

### Build

```shell
docker build . -t adam:v0.1
```

### Prepare

```shell
mkdir /opt/adam/data --parents
cp adam/.env_example /opt/adam/.env
chmod 400 /opt/adam/.env
```

### Run

Чтобы не потерять данные, в продакшн **обязательно используй внешнее хранилище для каталога с БД**

```shell
docker run --rm \
       --detach \
       --name adam \
       --env-file /opt/adam/.env \
       --publish 8000:8000 \
       --volume /opt/adam/data:/adam/data \
       adam:v0.1
```

## Development

### Installing packages for building dependencies

For macOS:

```shell
pip install python-ldap \
    --global-option=build_ext \
    --global-option="-I$(xcrun --show-sdk-path)/usr/include/sasl"
```

For Debian/Ubuntu:

```shell
apt-get install build-essential python3-dev python2.7-dev \
    libldap2-dev libsasl2-dev slapd ldap-utils tox \
    lcov valgrind
```

For other OS, see the installation in
the [documentation](https://www.python-ldap.org/en/python-ldap-3.3.0/installing.html)

### Installing dependencies

```shell
python3 -m venv .venv
source ./.venv/bin/activate
```

```shell
./.venv/bin/pip install -U pip setuptools
./.venv/bin/pip install poetry
poetry install
```

### Run

```shell
cd adam
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Migrations

Create first migration (already exists in the project):

```shell
alembic revision --autogenerate -m "Initial migration"
```

Applying the latest migration

```shell
alembic upgrade head
```