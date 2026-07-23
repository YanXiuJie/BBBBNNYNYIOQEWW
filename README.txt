ADAPTIVE MATH AI LEARNING SYSTEM
================================

This repository contains a Final Year Project prototype for an adaptive Year
5 mathematics learning system. The student interface uses Malay learning
content. The teacher interface provides class, question-bank and analytics
tools.

The project has two parts:

  backend  Python FastAPI API and MySQL database access
  frontend React and Vite web interface

The application can run without an OpenAI API key. Without the key, it uses
the built-in template question and local hint logic. With a valid key, the
teacher AI generator can request Malay questions and multilevel hints.


1. REQUIRED TOOLS
-----------------

Install these tools on Windows:

  Git       https://git-scm.com/download/win
  Python    https://www.python.org/downloads/windows/
            Recommended: Python 3.12 or 3.13
  Node.js   https://nodejs.org/en/download
            Install the LTS version, 20 or newer
  MySQL     https://dev.mysql.com/downloads/mysql/
            Recommended: MySQL 8.0 Community Server
  VS Code   https://code.visualstudio.com/download
            Optional editor

MySQL Workbench is optional:
  https://dev.mysql.com/downloads/workbench/

During Python installation, enable "Add Python to PATH". Node.js includes
npm, so npm does not need a separate download.

After installation, open a new PowerShell window and check:

  git --version
  python --version
  node --version
  npm --version

Make sure the MySQL service is running. In Windows Services, look for a
service such as MySQL80.


2. DOWNLOAD THE PROJECT
-----------------------

Option A - Git clone:

  git clone https://github.com/YanXiuJie/BBBBNNYNYIOQEWW.git
  cd BBBBNNYNYIOQEWW

Option B - Download ZIP:

  https://github.com/YanXiuJie/BBBBNNYNYIOQEWW/archive/refs/heads/main.zip

If you download the ZIP, extract it and open PowerShell in the extracted folder.
The project root is the folder containing README.md, .env.example, backend and
frontend.


3. CREATE THE LOCAL .ENV FILE
-----------------------------

The real .env file is intentionally not stored on GitHub. It may contain a
database password and an OpenAI API key. The .gitignore file prevents it from
being committed. New users must create a local copy after cloning.

From the project root, run:

  Copy-Item .env.example .env
  notepad .env

Replace YOUR_MYSQL_PASSWORD with the password of the local MySQL root user:

  DATABASE_URL=mysql+pymysql://root:YOUR_MYSQL_PASSWORD@127.0.0.1:3306/adaptive_math_ai?charset=utf8mb4
  OPENAI_API_KEY=
  OPENAI_MODEL=gpt-4.1-mini
  SEED_DEMO_DATA=auto

OPENAI_API_KEY is optional. Leave it empty if AI-generated questions are not
needed. The main learning features still work without it.

Never upload .env or share screenshots containing its contents. If a real key
is committed by accident, revoke it here and create a new one:
  https://platform.openai.com/api-keys

If the MySQL password contains @, #, : or /, URL-encode that character in
DATABASE_URL. For example, @ becomes %40 and # becomes %23.

The backend creates the adaptive_math_ai database and tables on startup when
the MySQL account has permission to create databases. A fresh installation
does not need a manual SQL migration.


4. INSTALL BACKEND DEPENDENCIES
-------------------------------

Run from the project root:

  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip
  python -m pip install -r backend\requirements.txt

If PowerShell blocks activation, run this once and activate again:

  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\.venv\Scripts\Activate.ps1

You should see (.venv) at the beginning of the PowerShell prompt.


5. START THE BACKEND
--------------------

Use Terminal 1 and keep it open:

  .\.venv\Scripts\Activate.ps1
  cd backend
  python -m uvicorn app.asgi:app --reload --host 127.0.0.1 --port 8000

First startup creates the database tables and demo data.

Health check:
  http://127.0.0.1:8000/health

API documentation:
  http://127.0.0.1:8000/docs

The health check should show:
  {"status":"ok"}


6. INSTALL AND START THE FRONTEND
---------------------------------

Open Terminal 2 in the project root. Do not close Terminal 1:

  cd frontend
  npm install
  npm run dev

Open the URL printed by Vite, normally:
  http://localhost:5173

The frontend calls the backend at http://127.0.0.1:8000. For the easiest setup,
keep the backend on port 8000 and the frontend on port 5173.

Press Ctrl+C in a terminal to stop its server.


7. BUILD THE FRONTEND
---------------------

To create the production build from the project root, run:

  cd frontend
  npm install
  npm run build

This creates frontend\dist. It is generated output and is ignored by Git. It
can be recreated at any time by running the same commands again.


8. DEMO ACCOUNTS
----------------

The first backend startup creates:

  Role          Username   Password
  Student       amin       password123
  Student       sara       password123
  Teacher/Admin cikgu      password123

These accounts are for local demonstration only.


9. CHECK THE PROJECT
--------------------

Frontend tests and build:

  cd frontend
  npm test
  npm run build

Return to the project root before running backend tests. Backend tests require
a running MySQL server and a MySQL account that can create and delete
databases. The current test fixture uses the local
development password admin123 by default. If your MySQL password is different,
the application can still use DATABASE_URL, but the tests may need developer-
specific test configuration.

  .\.venv\Scripts\Activate.ps1
  python -m pytest backend\tests -v


10. PROJECT FOLDERS
-------------------

  .env.example          Safe local configuration template
  .gitignore            Files that must not be uploaded
  README.md             Full beginner guide
  README.txt            Plain-text beginner guide
  backend\app           FastAPI routes, models and services
  backend\migrations    SQL notes for existing databases
  backend\requirements.txt
                         Python dependencies
  backend\tests         Backend tests
  frontend\src          React pages, components and API client
  frontend\package.json Frontend scripts and dependencies
  frontend\vite.config.js
                         Vite configuration

Generated folders such as .venv, frontend\node_modules, frontend\dist,
.npm-cache, .pytest_cache, logs and local database files can be recreated and
should not be added to new commits. The .gitignore rules protect newly
generated copies.


11. LIBRARIES AND TOOLS
-----------------------

Libraries are installed automatically by pip and npm. You do not need to
download each library manually.

Backend documentation:

  FastAPI       https://fastapi.tiangolo.com/
  Uvicorn       https://www.uvicorn.org/
  SQLAlchemy    https://www.sqlalchemy.org/
  PyMySQL       https://pypi.org/project/PyMySQL/
  Pydantic      https://docs.pydantic.dev/
  python-dotenv https://pypi.org/project/python-dotenv/
  OpenAI Python https://pypi.org/project/openai/
  pytest        https://docs.pytest.org/
  HTTPX         https://www.python-httpx.org/

Frontend documentation:

  React         https://react.dev/
  Vite          https://vite.dev/
  Chart.js      https://www.chartjs.org/
  react-chartjs-2
                https://react-chartjs-2.js.org/
  Lucide React  https://lucide.dev/guide/packages/lucide-react


12. COMMON PROBLEMS
-------------------

"python" or "pip" is not recognized:
  Install Python with Add Python to PATH enabled. Restart PowerShell.

"npm" is not recognized:
  Install Node.js LTS. Restart PowerShell.

MySQL access denied or connection refused:
  Start the MySQL service and check the password in .env. DATABASE_URL must
  match the MySQL username, password, host and port.

The database does not exist:
  The backend normally creates adaptive_math_ai. The MySQL account needs
  permission to create databases. You can also create it once in Workbench.

The website shows a network error:
  Keep the backend running and check http://127.0.0.1:8000/health first.

OpenAI generation is unavailable:
  This is expected when OPENAI_API_KEY is empty or invalid. The application
  falls back to template questions and local hints.

A port is already in use:
  Stop the old process with Ctrl+C. Use backend port 8000 and frontend port
  5173 with the current application.


13. GITHUB AND SECURITY NOTES
-----------------------------

  - .env is local-only and ignored by .gitignore.
  - .env.example contains placeholders and is safe to commit.
  - Never commit API keys, database passwords, local database files or logs.
  - OPENAI_API_KEY is optional for local development.
  - Demo accounts and passwords are for testing only.
