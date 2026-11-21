# Academix FastAPI backend

This service is the HTTP boundary between the Flutter application, PostgreSQL,
and the separate AI engine. It provides JWT authentication, role-protected
class management, and class stream announcements.

## Requirements

- Python 3.11 or newer
- PostgreSQL 15 or newer for database-backed development

## Local setup

From this directory, create and activate a virtual environment, then install
the dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a unique `SECRET_KEY` and adjust `DATABASE_URL` in `.env` before exposing
the service beyond local development. Start the API with:

```powershell
uvicorn app.main:app --reload
```

In the development environment, browser requests from `localhost` and
`127.0.0.1` are allowed on any local development-server port. For other
environments, set `CORS_ALLOWED_ORIGINS` to the exact trusted frontend origins.

The health endpoint is `GET http://127.0.0.1:8000/api/v1/health`. Class
announcements are available under `/api/v1/classes/{class_id}/announcements`;
teachers can create, edit, pin, and delete announcements, and enrolled students
can read them. Interactive API documentation is available at `/docs`.

## Database migrations

With PostgreSQL configured and reachable:

```powershell
alembic upgrade head
```

Migrations are managed in `migrations/versions/`. Apply the current schema with
`alembic upgrade head` before starting the API against a new database.

## Checks

```powershell
python -m pytest
```

`DATABASE_URL` is read from the environment. The health endpoint test does not
require a running PostgreSQL instance.
