# MarketEval

MarketEval is a Python-based project for scraping Vietnamese financial news, analyzing sentiment, and turning it into trading-risk signals.

## Project Roadmap

### Phase 1: Foundation & Storage
Set up the Python virtual environment and folder structure.
Initialize PostgreSQL and create the tables for tickers and news articles.

### Phase 2: The Extraction Engine
Build the first targeted scraper, starting with a source such as CafeF, using BeautifulSoup4 and HTTPX to collect headlines and article content.

### Phase 3: The Intelligence Layer
Integrate PhoBERT or ViFiNBERT to analyze scraped text and generate sentiment scores.

### Phase 4: The Decision Matrix
Translate NLP output into short-, medium-, and long-term risk assessments.

### Phase 5: Interface & Delivery
Connect the Streamlit dashboard and Telegram alerts so the results are visible and actionable.

## Setup

All commands below assume you are inside the `backend` directory unless noted otherwise.

### 1. Create the virtual environment

```powershell
cd .\backend\
python -m venv .venv
```

### 2. Activate the virtual environment

```powershell
cd .\backend\
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv\Scripts\Activate.ps1
```

### 3. Upgrade pip and install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Playwright browser binaries

This is required for the SPA scraping fallback.

```powershell
playwright install chromium
```

## PostgreSQL Setup

If PostgreSQL is already running and you know the password, open `psql` and create the database:

1. Open SQL Shell (psql).
2. Accept the defaults for server, database, port, and username.
3. Enter the password for the `postgres` user.
4. When you reach the `postgres=#` prompt, run:

```sql
CREATE DATABASE marketeval;
ALTER USER postgres WITH PASSWORD 'postgres';
```

## PostgreSQL Password Reset

Use this only if you need to temporarily reset the local `postgres` password.

### 1. Open `pg_hba.conf` as Administrator

Open Notepad as administrator, then open the PostgreSQL data folder, which is usually located at `C:\Program Files\PostgreSQL\<version>\data\`.

Change the file filter to All Files so you can open `pg_hba.conf`.

### 2. Enable trust mode temporarily

Find the IPv4 and IPv6 local connection rules and change them to `trust`:

```plaintext
# IPv4 local connections:
host    all             all             127.0.0.1/32            trust
# IPv6 local connections:
host    all             all             ::1/128                 trust
```

Save the file and close Notepad.

### 3. Restart PostgreSQL

Open Services, find `postgresql-x64-<version>`, and restart it.

### 4. Reset the password and create the database

Open SQL Shell (psql), press Enter through the prompts, and run:

```sql
ALTER USER postgres WITH PASSWORD 'postgres';
CREATE DATABASE marketeval;
```

### 5. Restore the security settings

Re-open `pg_hba.conf`, change `trust` back to `scram-sha-256` or `md5`, save the file, and restart PostgreSQL again.

## Notes

- The backend lives under `backend/`.
- The UI assets live under `ui/`.
- Database schema definitions live under `backend/database/`.


========================================================

## Init Database
python -m backend.database.init_db.py
python -m backend.database.seed_db.py

## Run Backend
<!-- uvicorn backend.main:app --reload --reload-dir backend --reload-exclude .venv --port 8000 -->
uvicorn backend.main:app --reload --port 8000 

## Run Desktop app
python -m desktop_app

## Run Web
streamlit run D:\Personal\MarketEval\ui\dashboard.py