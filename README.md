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

### Схема работы (упрощенная)

```mermaid
sequenceDiagram
    autonumber
    participant SSO
    actor User
    participant Frontend as Frontend
    participant Backend as Backend
    participant DB as SQLLite
    participant AD as Active Directory

    Note over SSO,AD: Login
    User->>Frontend: Login
    Frontend->>Backend: GET /login
    Backend->>SSO: Redirect to SSO provider
    SSO-->>Backend: Redirect to /callback
    Backend->>DB: Create/Read user
    note left of DB: User table
    DB-->>Backend: User data
    Backend-->>Frontend: Template for logged in user
    Frontend-->>User: Show "Create account" button

    Note over User,AD: Create account
    User->>Frontend: Press "Create account" button
    Frontend->>Backend: POST /api/v1/users/{id}/ldap_account
    Backend->>DB: Read LDAP account
    note left of DB: LDAP table
    DB-->>Backend: LDAP account data

    alt if LDAP account record not exist
    Backend->>AD: Create and configure account
    AD-->>Backend: Response
    Backend->>DB: Create LDAP account record
        DB-->>Backend: LDAP account data
    end

    Backend-->>Frontend: Render table with AD config
    Frontend-->>User: Show AD config
```

### Заметки

#### SSO

SSO для разработки реализован через Яндекс ID и его приложения.
Тестовое приложение для SSO можно создать тут <https://oauth.yandex.ru/>.

При создании SSO требуются

На стороне SSO от сервиса:

- Suggest Hostname: Хост на котором будет работать сервис, например <https://myservice.domain.local> или <http://localhost:8000> для разработки
- Redirect URI: `{{ Suggest Hostname }}/api/auth/callback`. Путь после домена должен быть таким: `/api/auth/callback`

На стороне приложения от SSO:

- ClientID
- Client secret

**Важно**: При подключении Яндекс SSO (приложение создано из под моей корпоративной учетки) **любой** (не только корпоративный) залогиненый в Яндекс пользователь может получить доступ к сервису.
Вероятно какие-то настройки ограничений могут быть у организации, но мне об этом неизвестно.

---

Возможна интеграция FastAPI с [Keycloak](https://fastapi-keycloak-middleware.readthedocs.io/en/latest/usage.html) через Middleware, выглядит не сложно. Для реализации нужен доступ к тестовому приложению в Keycloak сервисе.

---

#### Ограничения .env файла и переменных

При пробелах в значании переменных, их нельзя экранировать и все ломается.
При заключении переменных в кавычки, эти кавычки интерпретируются как часть значения переменной.

Поэтому, переменные на текущий момент:

- Не должны содержать пробелов
- Не должны быть заключены в кавычки

Требуется доработка.

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

## Launch

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

### Run in Docker

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

## Performance

Для теста сервис запускался с 4 воркерами.
В запросе кука авторизации, благодаря которой сервис делает два запроса к БД для извлечения данных пользователя.
Всего 3000 запросов, 20 из которых одновременно. При таких условиях на локальном железе, с ограничением контейнера в 1 CPU и 512 Mem, сервис держит чуть больше 300 запросов в секунду. Если увеличивать количество одновременных коннектов или их общее количество, то процесс gunicorn в контейнере падает и перезапускается. Считаю, что для моих целей этого более, чем достаточно, поскольку ориентировочная нарузка будет менее 1000 запросов в сутки.

```shell
$ docker run --rm \
    --detach \
    --name adam \
    --env-file ~/work/adam/adam/.env \
    --memory="512M" \
    --memory-swap="1G" \
    --cpus="1" \
    --publish 8000:8000 \
    adam:v0.1

$ ab -n 3000 -c 20 \
    -C "auth_token=IjBhZTdjOThkLThmNzctNDcyNy05YWVlLTRhOGEzYTFhY2RmMCI.kOaI6kDyzBaN_kSBugTddZSIX4g" \
    http://localhost:8000/

This is ApacheBench, Version 2.3 <$Revision: 1913912 $>
Copyright 1996 Adam Twiss, Zeus Technology Ltd, http://www.zeustech.net/
Licensed to The Apache Software Foundation, http://www.apache.org/

Benchmarking localhost (be patient)
Completed 300 requests
Completed 600 requests
Completed 900 requests
Completed 1200 requests
Completed 1500 requests
Completed 1800 requests
Completed 2100 requests
Completed 2400 requests
Completed 2700 requests
Completed 3000 requests
Finished 3000 requests


Server Software:        uvicorn
Server Hostname:        localhost
Server Port:            8000

Document Path:          /
Document Length:        8246 bytes

Concurrency Level:      20
Time taken for tests:   8.755 seconds
Complete requests:      3000
Failed requests:        0
Total transferred:      25200000 bytes
HTML transferred:       24738000 bytes
Requests per second:    342.67 [#/sec] (mean)
Time per request:       58.365 [ms] (mean)
Time per request:       2.918 [ms] (mean, across all concurrent requests)
Transfer rate:          2811.00 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    1   0.8      0       8
Processing:     3   57  49.0     74     415
Waiting:        3   52  46.7     29     415
Total:          3   58  49.1     75     416
WARNING: The median and mean for the initial connection time are not within a normal deviation
        These results are probably not that reliable.

Percentage of the requests served within a certain time (ms)
  50%     75
  66%     84
  75%     89
  80%     92
  90%     99
  95%    113
  98%    175
  99%    189
 100%    416 (longest request)
```

## Known issues

- [ ] Отладочные логи (от алембика, гуникорна и вероятно другие) не попадают в лог файл и видны только в логах контейнера
- [ ] Если переменная в `.env` файле обернута в кавычки, то они воспринимаются как часть значения этой переменной
- [ ] Нет возможности написания переменных и создания ресурсов AD с пробелами
- [ ] Захардкожен суффикс пользовательской UO `self.create_ou(f"{username}_ou", config.ldap.default_users_dn)`
- [ ] Лог сброса пароля появляется раньше лога запроса эндпоинта для сброcа пароля
