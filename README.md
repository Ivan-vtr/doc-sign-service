# Document Signing Service

Backend-сервис на Django для подписания документов реальными ЭЦП через [sigex.kz](https://sigex.kz) с поддержкой eGov QR.

## Архитектура

Проект построен по принципам **Clean Architecture**:

```
app/
├── domain/           # Сущности, бизнес-правила, порты (интерфейсы)
│   ├── entities.py   # Document, Signature, Package, SignerIdentity
│   ├── ports.py      # Абстрактные интерфейсы (репозитории, сервисы)
│   └── exceptions.py # Доменные исключения
├── application/      # Use Cases — логика приложения
│   └── use_cases.py  # Загрузка, подписание, верификация, пакеты, скачивание
├── infrastructure/   # Внешние зависимости
│   ├── sigex/        # Клиент Sigex API
│   ├── storage/      # Файловое хранилище (local / S3)
│   ├── persistence/  # Django ORM модели и репозитории
│   └── container.py  # Dependency injection
└── interfaces/       # Точки входа
    ├── api/          # REST API (DRF views, serializers, urls)
    └── web/          # Web UI (Django templates)
```

## Быстрый старт (Docker)

```bash
cp .env.example .env   # отредактировать пароли и настройки
docker compose up -d
```

Готово. Сервис доступен на `http://localhost` (порт 80).

Суперпользователь создаётся автоматически (по умолчанию `admin` / `admin123`, настраивается в `.env`).

### Что происходит при запуске

1. Поднимается PostgreSQL
2. Backend ждёт готовности БД
3. Применяются миграции (`migrate`)
4. Собирается статика (`collectstatic`)
5. Создаётся суперпользователь (если не существует)
6. Запускается Gunicorn (3 воркера)
7. Nginx проксирует запросы и раздаёт статику/медиа

### Управление

```bash
docker compose up -d      # запуск
docker compose down        # остановка
docker compose logs -f     # логи
docker compose restart     # перезапуск
docker compose up -d --build  # пересборка после изменений кода
```

## Локальная разработка (без Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Отредактировать: DB_HOST=localhost, DB_PORT=5432, DJANGO_DEBUG=True

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Развёртывание на сервере

### Требования

- Linux (Ubuntu 22.04+ / Debian 12+)
- Docker Engine 24+ и Docker Compose v2
- Открытый порт 80 (или 443 при настройке SSL)
- Минимум 1 GB RAM, 10 GB диск

### Пошаговый план

**1. Установить Docker** (если не установлен):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# перелогиниться
```

**2. Склонировать репозиторий:**

```bash
git clone <your-repo-url> /opt/signing-service
cd /opt/signing-service
```

**3. Настроить окружение:**

```bash
cp .env.example .env
nano .env
```

Обязательно изменить:
- `DJANGO_SECRET_KEY` — случайная строка 50+ символов
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS` — домен/IP сервера
- `DB_PASSWORD` — надёжный пароль для PostgreSQL
- `DJANGO_SUPERUSER_PASSWORD` — пароль администратора

**4. Запустить:**

```bash
docker compose up -d
```

**5. Проверить:**

```bash
docker compose ps        # все сервисы UP
docker compose logs backend  # нет ошибок
curl http://localhost/api/auth/profile/  # должен вернуть 401/403
```

### SSL (HTTPS)

Для production рекомендуется поставить reverse proxy (Caddy / Traefik / certbot + nginx) перед контейнером. Самый простой вариант — Caddy:

```bash
# Установить Caddy на хосте
sudo apt install caddy

# /etc/caddy/Caddyfile
your-domain.kz {
    reverse_proxy localhost:80
}

sudo systemctl restart caddy
```

Caddy автоматически получит и обновит SSL-сертификат от Let's Encrypt.

### Обновление

```bash
cd /opt/signing-service
git pull
docker compose up -d --build
```

### Бэкап БД

```bash
# Создать дамп
docker compose exec db pg_dump -U postgres signing_service > backup_$(date +%Y%m%d).sql

# Восстановить
docker compose exec -T db psql -U postgres signing_service < backup.sql
```

## API Endpoints

### Авторизация

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/auth/register/` | Регистрация пользователя |
| POST | `/api/auth/login/` | Вход |
| POST | `/api/auth/logout/` | Выход |
| GET | `/api/auth/profile/` | Профиль текущего пользователя |

### Документы

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/documents/` | Список документов |
| POST | `/api/documents/upload/` | Загрузка одного файла |
| POST | `/api/documents/upload-multiple/` | Загрузка нескольких файлов |
| GET | `/api/documents/{id}/` | Статус и подписи документа |
| GET | `/api/documents/{id}/download/` | Скачать оригинал |
| GET | `/api/documents/{id}/download/original/` | Скачать оригинал (алиас) |
| GET | `/api/documents/{id}/download/signature/` | Скачать CMS-подпись (.cms) |
| GET | `/api/documents/{id}/download-signed/` | Скачать подписанную копию |
| POST | `/api/documents/{id}/verify/` | Проверить контрольные суммы и подпись |

### Подписание (eGov QR)

| Метод | URL | Описание |
|-------|-----|----------|
| POST | `/api/signing/initiate/` | Начать QR-подписание (получить QR код) |
| POST | `/api/signing/complete/` | Завершить подписание |
| POST | `/api/signing/package/initiate/` | Начать подписание пакета |
| POST | `/api/signing/package/complete/` | Завершить подписание пакета |

### Пакеты

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/api/packages/` | Список пакетов |
| POST | `/api/packages/create/` | Создать пакет |
| POST | `/api/packages/{id}/add-document/` | Добавить документ в пакет |
| GET | `/api/packages/{id}/download-signed/` | Скачать ZIP подписанных документов |

### Формат ZIP пакета

```
package_{uuid}_signed.zip
├── originals/
│   ├── document1.pdf
│   └── document2.pdf
└── signatures/
    ├── document1.pdf.cms
    └── document2.pdf.cms
```

ZIP содержит только успешно подписанные документы. Документы со статусом FAILED пропускаются.

## Флоу подписания документов и пакетов

### Подписание одного документа

**1. Регистрация и вход:**

```bash
curl -X POST http://localhost/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user1",
    "password": "secure123",
    "iin": "123456789012",
    "full_name": "Иванов Иван Иванович",
    "signer_type": "individual"
  }'

curl -X POST http://localhost/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "user1", "password": "secure123"}' \
  -c cookies.txt
```

**2. Загрузка документа:**

```bash
curl -X POST http://localhost/api/documents/upload/ \
  -b cookies.txt \
  -F "file=@document.pdf" \
  -F "title=Договор"
```

**3. Инициация QR-подписания:**

```bash
curl -X POST http://localhost/api/signing/initiate/ \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"document_id": "uuid..."}'
```

QR-код показывается пользователю: `data:image/gif;base64,{qr_code_base64}`.
Пользователь сканирует в eGov mobile (физлицо) или eGov Business (юрлицо).

**4. Завершение подписания:**

```bash
curl -X POST http://localhost/api/signing/complete/ \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "uuid...",
    "session_id": "...",
    "data_url": "https://sigex.kz/api/egovQr/.../data",
    "sign_url": "https://sigex.kz/api/egovQr/.../sign"
  }'
```

**5. Скачивание подписи:**

```bash
# CMS-подпись
curl -b cookies.txt http://localhost/api/documents/{uuid}/download/signature/ -o signature.cms

# Оригинал
curl -b cookies.txt http://localhost/api/documents/{uuid}/download/original/ -o original.pdf
```

### Подписание пакета документов

```bash
# 1. Создать пакет
curl -X POST http://localhost/api/packages/create/ \
  -b cookies.txt -H "Content-Type: application/json" \
  -d '{"title": "Пакет документов", "description": "Договор + приложения"}'

# 2. Добавить документы
curl -X POST http://localhost/api/packages/{pkg_id}/add-document/ \
  -b cookies.txt -H "Content-Type: application/json" \
  -d '{"document_id": "doc_uuid_1"}'

# 3. Подписать пакет
curl -X POST http://localhost/api/signing/package/initiate/ ...
curl -X POST http://localhost/api/signing/package/complete/ ...

# 4. Скачать ZIP с подписями
curl -b cookies.txt http://localhost/api/packages/{pkg_id}/download-signed/ -o signed.zip
```

При подписании пакета каждый документ обрабатывается независимо. Если один документ упал — остальные продолжают подписываться. Статус пакета: `signed` (все ОК), `partially_signed` (часть failed), `failed` (все failed).

## Тестирование

```bash
pytest                        # все тесты
pytest tests/unit/            # unit-тесты
pytest tests/integration/     # интеграционные
pytest --cov=app --cov-report=html  # с покрытием
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `DJANGO_SECRET_KEY` | `change-me...` | Секретный ключ Django |
| `DJANGO_DEBUG` | `False` | Режим отладки |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Разрешённые хосты |
| `DB_NAME` | `signing_service` | Имя БД |
| `DB_USER` | `postgres` | Пользователь БД |
| `DB_PASSWORD` | `postgres` | Пароль БД |
| `DJANGO_SUPERUSER_USERNAME` | `admin` | Логин суперпользователя |
| `DJANGO_SUPERUSER_PASSWORD` | `admin123` | Пароль суперпользователя |
| `SIGEX_BASE_URL` | `https://sigex.kz` | URL Sigex API |
| `SIGEX_TIMEOUT` | `30` | Таймаут запросов к Sigex (секунды) |
| `SIGEX_QR_POLL_RETRIES` | `60` | Количество попыток опроса подписи |
| `SIGEX_QR_POLL_INTERVAL` | `3` | Интервал опроса подписи (секунды) |
| `FILE_STORAGE_BACKEND` | `local` | Хранилище файлов (`local` / `s3`) |
| `APP_PORT` | `80` | Порт nginx на хосте |

Sigex API работает без аутентификации для eGov QR подписания.

## Поддерживаемые форматы

- **PDF** (основной)
- **PNG** (сканы документов)
- **JPEG** (сканы документов)

Максимальный размер файла: 50 МБ.

## Структура Docker

```
docker-compose.yml
├── db        — PostgreSQL 16
├── backend   — Django + Gunicorn (3 воркера, timeout 300s)
└── nginx     — Nginx (статика, медиа, reverse proxy)
```

Данные сохраняются в Docker volumes: `postgres_data`, `media_data`, `static_data`.
