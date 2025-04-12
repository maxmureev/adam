# Active Directory Account Manager

Проект задумывался как способ автоматизировать создание учетных записей в Active Directory.

## Задача и требования от заказчика

- Создать страничку, которая будет из себя представлять сервис по созданию учетки в AD
- Сделать так, чтобы создание аккаунта работало без участия человека
- Показывать пользователю определенным образом значения аккаунта, в их числе логин, пароль и некоторые параметры подключения к контроллеру домена
- Обычно, каждому пользователю достаточно одного AD аккаунта
- По-возможности сделать авторизацию через корпоративный SSO, только ради удобства, чтобы однозначно идентифицировать сотрудника без его регистрации на целевой страничке для разделения показа AD аккаунтов
- В AD должны быть
  - Создан пользователь
  - Создан organisation unit для этого пользователя
  - Добавить пользователя в уже существующую группу

## Реализация

1. Пользователь авторизуется на страничке через SSO
1. Логин, под которым входит SSO пользователь, передается сервису в качестве аргумента
1. Создается пользователь в БД
1. Скрипт идет в AD и для этого SSO пользователя
    - Генерирует пароль
    - Создает аккаунт, который равен логину пользователя
    - Создает OU
    - Добавляет пользователя в группу (указанную в переменных)
1. Записывает данные в БД, где этот аккаунт привязан к ранее созданному пользователю, чтобы не менять пароль каждый раз при входе на страничку сервиса, т.к. в AD нельзя просто так посмотреть пароль, можно только сбросить.
1. Показыват пользователю таблицу со значениями параметров подключения

## Installing packages for building dependencies

```shell
python3 -m venv .venv
source ./.venv/bin/activate
```

### macOS

```shell
pip install python-ldap \
    --global-option=build_ext \
    --global-option="-I$(xcrun --show-sdk-path)/usr/include/sasl"
```

### Alpine

```shell
apk add build-base openldap-dev python2-dev python3-dev
```

### CentOS

```shell
yum groupinstall "Development tools"
yum install openldap-devel python-devel
```

### Debian

```shell
apt-get install build-essential python3-dev python2.7-dev \
    libldap2-dev libsasl2-dev slapd ldap-utils tox \
    lcov valgrind
```

## Installing dependencies

```shell
./.venv/bin/pip install -U pip setuptools
./.venv/bin/pip install poetry
poetry install
```

## Run

```shell
cd adam
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
