# Adaptive Math AI

Malay Year 5 adaptive mathematics FYP MVP.

## Stack

- Backend: Python, FastAPI, SQLAlchemy
- Frontend: React, Vite
- Database: MySQL by default for development and tests, override with `DATABASE_URL`

## Core Features

- Student diagnostic test
- Adaptive practice
- Malay feedback and mistake review
- Progress and mastery tracking
- Teacher class/student CRUD
- Syllabus support for Year 5 textbook chapters
- Question bank and AI question generation

## Run Backend

```powershell
python -m pip install -r backend/requirements.txt
cd backend
python -m uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8000
```

The backend defaults to a local MySQL instance and auto-creates the `adaptive_math_ai` database if needed.

Optional AI configuration:

- `OPENAI_API_KEY` enables LLM-generated questions and multilevel hints.
- `OPENAI_MODEL` overrides the default model used for question generation.
- Without `OPENAI_API_KEY`, the system falls back to template-based question generation and local hint generation.

## Run Frontend

```powershell
cd frontend
$env:npm_config_cache = (Join-Path (Get-Location) ".npm-cache")
npm install
npm run dev
```

## Demo Accounts

| Role | Username | Password |
| --- | --- | --- |
| Student | `amin` | `password123` |
| Teacher/Admin | `cikgu` | `password123` |

## Verification

```powershell
python -m pytest backend/tests -v
cd frontend
$env:npm_config_cache = (Join-Path (Get-Location) ".npm-cache")
npm run build
```
