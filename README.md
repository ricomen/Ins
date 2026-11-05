# Ins

Сервис скачивания публичного контента Instagram: FastAPI + Redis/arq + PostgreSQL,
адаптер iqsaved, локальное хранилище и дашборд на React + shadcn/ui + FSD.

## Что умеет

- посты, Reels, IGTV и карусели — все файлы публикации;
- профили — 12 последних постов и активные stories;
- stories — отдельной задачей;
- highlights — через Instaloader при настроенной сессии Instagram;
- пакетная загрузка: несколько ссылок одной задачей;
- очередь с одним воркером и паузой 3–5 секунд между запросами к iqsaved;
- статусы, прогресс, история, повтор и удаление задач;
- скачивание отдельных файлов и ZIP-архива;
- авторизация одного администратора по паролю;
- автоудаление файлов через 24 часа.

## Быстрый старт

```bash
cp .env.example .env
# обязательно поменяйте INS_ADMIN_PASSWORD и INS_AUTH_SECRET

docker compose up -d --build
```

- Дашборд: <http://localhost:8080>
- API и Swagger: <http://localhost:8000/docs>
- Логин по умолчанию: пароль из `INS_ADMIN_PASSWORD` (в примере — `admin`)

Остановить:

```bash
docker compose down
```

Удалить вместе с БД и файлами:

```bash
docker compose down -v
```

## Локальная разработка

### Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Нужны PostgreSQL и Redis. Можно поднять только их:

```bash
docker compose up -d postgres redis
```

Переменные окружения читаются с префиксом `INS_`, например:

```bash
export INS_DATABASE_URL=postgresql+asyncpg://ins:ins@localhost:5432/ins
export INS_REDIS_URL=redis://localhost:6379/0
export INS_ADMIN_PASSWORD=admin
```

Воркер:

```bash
cd backend
uv run arq app.worker.WorkerSettings
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite проксирует `/api` на `http://localhost:8000`.

## Highlights

iqsaved не поддерживает highlights. Для них используется Instaloader с
авторизованной сессией. Инструкция: [`secrets/README.md`](secrets/README.md).

Без сессии чекбокс highlights в UI отключён, а API возвращает понятную ошибку.

## Структура

```text
backend/
  app/
    api/routes.py       # REST API
    auth.py             # вход администратора, JWT
    db_models.py        # Job, MediaFile
    worker.py           # arq worker, последовательная обработка
    storage.py          # локальный диск, ZIP, TTL
    downloader/         # iqsaved + Instaloader
  tests/
frontend/
  src/
    app/                # провайдеры, роутер, стили
    pages/              # login, dashboard, jobs, job
    widgets/            # layout, job-form, job-table, stats
    features/           # действия с задачами
    entities/           # job: типы, API, UI
    shared/             # api-клиент, UI-компоненты, утилиты
```

## API

Все защищённые эндпоинты принимают `Authorization: Bearer <token>`.

```text
POST   /api/auth/login
GET    /api/health
GET    /api/config
POST   /api/jobs
POST   /api/jobs/batch
GET    /api/jobs?status=&kind=&limit=&offset=
GET    /api/jobs/{id}
DELETE /api/jobs/{id}
POST   /api/jobs/{id}/retry
GET    /api/jobs/{id}/archive
GET    /api/jobs/{id}/files/{file_id}
GET    /api/stats
```

## Проверка

```bash
cd backend
uv run ruff check .
uv run mypy app tests
uv run pytest -q

cd ../frontend
npm run build
```

## Ограничения

- только публичный контент;
- iqsaved — неофициальный сторонний сервис, его API может измениться;
- лимит запросов привязан к IP, поэтому воркер обрабатывает задачи последовательно;
- для highlights нужна сессия Instagram;
- файлы хранятся локально и удаляются через `INS_JOB_TTL_HOURS` часов (по умолчанию 24).
