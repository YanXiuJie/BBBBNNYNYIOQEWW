# Adaptive Math AI Learning System

This repository contains a Final Year Project prototype for an adaptive Year 5
mathematics learning system. The student interface uses Malay learning content
and the teacher interface provides class, question-bank and analytics tools.

The project has two parts:

- `backend`: Python FastAPI API and MySQL database access.
- `frontend`: React and Vite web interface.

The application can run without an OpenAI API key. Without the key, it uses
the built-in template question and local hint logic. With a valid key, the
teacher AI generator can request Malay questions and multilevel hints.

## What the system can do

- Student login and profile management.
- Diagnostic testing and adaptive practice.
- Comprehensive practice with progressive hints and answer feedback.
- Progress, mastery, knowledge-map and mistake-review views.
- Teacher class and student management.
- Syllabus and question-bank management.
- Optional AI-assisted question generation.

## Before you start

Install these tools on Windows. The links below are official download pages.

| Tool | Why it is needed | Recommended version | Download |
| --- | --- | --- | --- |
| Git | Download and update the project | Current version | [git-scm.com/download/win](https://git-scm.com/download/win) |
| Python | Run the backend and tests | 3.12 or 3.13 | [python.org/downloads/windows](https://www.python.org/downloads/windows/) |
| Node.js | Run the frontend and npm | LTS version, 20 or newer | [nodejs.org/en/download](https://nodejs.org/en/download) |
| MySQL Community Server | Store users, questions and progress | MySQL 8.0 | [dev.mysql.com/downloads/mysql](https://dev.mysql.com/downloads/mysql/) |
| VS Code | Optional editor for beginners | Current version | [code.visualstudio.com/download](https://code.visualstudio.com/download) |

During the Python installation, enable **Add Python to PATH**. Node.js
includes `npm`, so npm does not need a separate download. MySQL Workbench is
optional, but it is useful for viewing the database:
[dev.mysql.com/downloads/workbench](https://dev.mysql.com/downloads/workbench/).

After installation, open a new PowerShell window and check the tools:

```powershell
git --version
python --version
node --version
npm --version
```

Make sure the MySQL service is running before starting the backend. On
Windows, this can be checked in **Services** by looking for a service such as
`MySQL80`.

## Download the project

### Option A: Git clone

```powershell
git clone https://github.com/YanXiuJie/BBBBNNYNYIOQEWW.git
cd BBBBNNYNYIOQEWW
```

### Option B: Download ZIP

Download the latest main branch as a ZIP file:

[Download project ZIP](https://github.com/YanXiuJie/BBBBNNYNYIOQEWW/archive/refs/heads/main.zip)

Extract the ZIP, open the extracted folder in PowerShell, and use that folder
as the project root. The project root is the folder containing `README.md`,
`.env.example`, `backend` and `frontend`.

## Create the local environment file

The real `.env` file is intentionally **not stored on GitHub**. It can contain
database passwords and an OpenAI API key. The `.gitignore` file protects it
from being committed. A new user therefore has to create a local copy after
cloning the project.

From the project root, run:

```powershell
Copy-Item .env.example .env
notepad .env
```

At minimum, replace `YOUR_MYSQL_PASSWORD` with the password of the local
MySQL `root` user:

```dotenv
DATABASE_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@127.0.0.1:3306/adaptive_math_ai?charset=utf8mb4
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
SEED_DEMO_DATA=auto
```

`OPENAI_API_KEY` is optional. Leave it empty if you do not need AI-generated
questions. The main learning features still work without it.

Do not upload `.env`, paste its contents into GitHub, or share screenshots
that show the key. If a real key is ever committed by accident, revoke it at
[platform.openai.com/api-keys](https://platform.openai.com/api-keys) and create
a new one.

If the MySQL password contains URL characters such as `@`, `#`, `:` or `/`,
URL-encode those characters in `DATABASE_URL`. For example, `@` becomes `%40`
and `#` becomes `%23`.

The backend creates the `adaptive_math_ai` database and its tables on startup
when the configured MySQL account has permission to create databases. A fresh
installation does not need a manual SQL migration.

## Install backend dependencies

Run these commands from the project root. The virtual environment keeps this
project's Python libraries separate from other projects.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

If PowerShell blocks activation, run this once in the same PowerShell window
and then activate the environment again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the beginning of the PowerShell prompt after
activation.

## Start the backend

Use **Terminal 1**. Keep this terminal open while using the website.

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python -m uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8000
```

On the first startup, the backend creates the database tables and demo data.
Check that the API is running by opening:

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

The health check should return:

```json
{"status":"ok"}
```

## Install and start the frontend

Open **Terminal 2** in the project root. Do not close Terminal 1.

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally:

[http://localhost:5173](http://localhost:5173)

The frontend is configured to call the backend at
`http://127.0.0.1:8000`. For the easiest setup, keep the backend on port
`8000` and the frontend on port `5173`.

To stop either server, press `Ctrl+C` in its terminal.

## Build the frontend

To create the production build from the project root, run:

```powershell
cd frontend
npm install
npm run build
```

This creates `frontend/dist`. The folder is generated output and is ignored by
Git. It can be recreated at any time by running the same commands again.

## Demo accounts

The first backend startup creates these accounts:

| Role | Username | Password |
| --- | --- | --- |
| Student | `amin` | `password123` |
| Student | `sara` | `password123` |
| Teacher/Admin | `cikgu` | `password123` |

These are local demonstration accounts only. Do not use these passwords for a
real deployment.

## Run the checks

The frontend build and unit test commands do not need the development server:

```powershell
cd frontend
npm test
npm run build
```

Return to the project root before running backend tests. Backend tests require
a running MySQL server and a test database account that
can create and delete databases. The current test fixture uses the local
development password `admin123` by default. If your MySQL root password is
different, the application can still use your `DATABASE_URL`, but the tests
may need developer-specific test configuration before they can run:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pytest backend\tests -v
```

## Project structure

```text
.
|-- .env.example          Safe template for local configuration
|-- .gitignore            Files that must not be uploaded
|-- README.md             This guide
|-- README.txt            Plain-text copy of this guide
|-- backend
|   |-- app
|   |   |-- main.py        FastAPI routes and application startup
|   |   |-- models.py      SQLAlchemy database models
|   |   |-- schemas.py     Request and response validation
|   |   `-- services       Adaptive-learning and AI services
|   |-- migrations         SQL notes for existing databases
|   |-- requirements.txt   Python dependencies
|   `-- tests              Backend tests
`-- frontend
    |-- src               React pages, components and API client
    |-- package.json      Frontend scripts and dependencies
    `-- vite.config.js    Vite configuration
```

Generated folders such as `.venv`, `frontend/node_modules`, `frontend/dist`,
`.npm-cache`, `.pytest_cache`, logs and local database files are not project
source files. They can be recreated locally and should not be added to new
commits. The `.gitignore` rules protect newly generated copies.

## Libraries and tools used

You do not need to download each library separately. The `pip install` and
`npm install` commands download the versions listed by this repository.

Backend:

- [FastAPI](https://fastapi.tiangolo.com/) - web API framework.
- [Uvicorn](https://www.uvicorn.org/) - development API server.
- [SQLAlchemy](https://www.sqlalchemy.org/) - database ORM.
- [PyMySQL](https://pypi.org/project/PyMySQL/) - MySQL driver.
- [Pydantic](https://docs.pydantic.dev/) - request and response validation.
- [python-dotenv](https://pypi.org/project/python-dotenv/) - loads `.env` values.
- [OpenAI Python library](https://pypi.org/project/openai/) - optional AI generation.
- [pytest](https://docs.pytest.org/) and [HTTPX](https://www.python-httpx.org/) - tests.

Frontend:

- [React](https://react.dev/) - user interface library.
- [Vite](https://vite.dev/) - frontend development server and build tool.
- [Chart.js](https://www.chartjs.org/) - charts.
- [react-chartjs-2](https://react-chartjs-2.js.org/) - React bindings for Chart.js.
- [Lucide React](https://lucide.dev/guide/packages/lucide-react) - interface icons.

## Common problems

### `python` or `pip` is not recognized

Install Python again with **Add Python to PATH** enabled, close PowerShell,
open a new PowerShell window, and try `python --version` again.

### `npm` is not recognized

Install the Node.js LTS version, close PowerShell, open a new PowerShell
window, and try `node --version` again.

### MySQL access denied or connection refused

Check that the MySQL service is running and that the password in `.env` is
correct. The `DATABASE_URL` must use the same MySQL username, password, host
and port as your local installation.

### The database does not exist

The backend normally creates `adaptive_math_ai` automatically. The MySQL user
must have permission to create databases. If it does not, create the database
once in MySQL Workbench or grant the required permission, then start the
backend again.

### The website shows a network error

Keep the backend running in Terminal 1 and confirm that
[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) works before starting
the frontend.

### OpenAI generation is unavailable

This is expected when `OPENAI_API_KEY` is empty or invalid. The application
falls back to template-based questions and local hints. To enable AI features,
create a key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys),
put it only in your local `.env`, and restart the backend.

### A port is already in use

Stop the old backend or frontend process with `Ctrl+C`. Use port `8000` for the
backend and `5173` for the frontend because these are the ports configured by
the current application.

## Security and GitHub notes

- `.env` is local-only and is ignored by `.gitignore`.
- `.env.example` contains placeholders only and is safe to commit.
- Never commit API keys, database passwords, local database files or logs.
- `OPENAI_API_KEY` is optional for local development.
- The demo accounts and passwords are for testing only.
