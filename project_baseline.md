# Project Blueprint: Technology Stack & Directory Architecture

This document establishes the official software architecture, database schemas, and folder structures for the **Intelligent News-Driven Risk Assessment & Trading Decision Support System (TDSS)** tailored for the Vietnamese market.

---

## 1. Core Technology Stack

### 1.1. Backend & Automation Core
* **Language:** `Python 3.11+`
* **API Engine:** `FastAPI` + `Uvicorn` (Asynchronous ASGI framework powering REST endpoints and real-time WebSockets for UI updates).
* **Task Scheduling:** `APScheduler` (Triggers recurring background polling routines to fetch stock news without external dependencies like Celery or Redis).
* **HTTP & Webhooks:** `HTTPX` (Asynchronous HTTP client for Telegram alert delivery and external API requests).

### 1.2. Market Data & News Ingestion Layer
* **Data Ingestion SDK:** `vnstock` (Primary open-source library for streaming structured stock quotes, market metadata, and company news directly from financial data providers).
* **Data Deduplication:** `SHA-256 Hashing` (Generates unique 64-character hex digests of incoming news headlines and content to prevent duplicate database writes).

### 1.3. Intelligence, Vectorization & NLP Layer
* **Base Encoder Model:** `VinAI/phobert-base` or `ViFiNBERT` (Vietnamese Financial BERT model mapped to capture local financial context and market terminology).
* **Inference Orchestration:** `Hugging Face Transformers` + `PyTorch` (Local tokenization and tensor computation).
* **Vector Embeddings:** Direct translation of news items into 768-dimensional dense vectors for semantic risk matching.

### 1.4. Storage & Persistence Framework
* **Primary Database Engine:** `PostgreSQL 16+` (Relational storage for watchlists, news archives, risk logs, and system metadata).
* **Vector Engine Extension:** `pgvector` (Stores model embeddings directly inside PostgreSQL tables to allow fast vector similarity searches without needing an external vector DB).

### 1.5. Interface & Downstream Communication
* **Desktop UI Interface:** `Rainmeter` + `WebView2` plugin rendering a lightweight HTML/CSS/JS overlay on the desktop.
* **Secondary Analytics UI:** `Streamlit` (Rapid internal dashboard framework for debugging and model evaluation).
* **Alert Delivery:** `python-telegram-bot` (Asynchronous webhook integration sending real-time risk alerts directly to Telegram channels).

---

## 2. Standardized Directory Layout

```
MarketEval/
│
├── .env.example                # Blueprint for system access tokens, DB URIs, and environment configurations
├── .gitignore                  # Excludes Python bytecode, virtual environments, local database credentials, and logs
├── README.md                   # System operational guide and setup runbook
├── requirements.txt            # Dependency pin list (vnstock, fastapi, pgvector, torch, transformers, etc.)
│
├── backend/
│   ├── api/                        # FastAPI Service Layer
│   │   ├── __init__.py
│   │   ├── main.py                 # Entry point for ASGI server startup, CORS, and background tasks
│   │   └── routes/                 # Endpoint routing modules
│   │       ├── tickers.py          # Watchlist & market metadata management
│   │       ├── news.py             # Ingested news retrieval and filtering endpoints
│   │       ├── risk.py             # Risk assessments, sentiment scores, and horizon signals
│   │       └── ws.py               # WebSocket stream pushing live alerts to desktop UI
│   │        
│   ├── config/                     # Global configuration management
│   │   ├── __init__.py
│   │   └── settings.py             # Centralized settings, PostgreSQL URIs, model paths, and poll intervals
│   │
│   ├── database/                   # Database schemas, connections, and DAOs
│   │   ├── __init__.py
│   │   ├── connection.py           # Thread-safe PostgreSQL / asyncpg connection factory
│   │   ├── schema.sql              # PostgreSQL DDL script with pgvector extension setup
│   │   ├── queries.py              # Centralized SQL Data Access Objects (DAO)
│   │   └── seed_tickers.py         # Script to seed initial VN30 / target market tickers
│   │
│   └── src/                        # Core application business logic
│        ├── __init__.py
│        │
│        ├── source_crawlers/       # Data fetching & normalization via web crawler
│        │   └── __init__.py
│        │
│        ├── ingestion/              
│        │   ├── __init__.py
│        │   ├── deduplicator.py     # SHA-256 cryptographic hashing logic for content deduplication
│        │   └── mapper.py           # Maps raw crawled data outputs to database schema entities
│        │
│        ├── nlp/                    # Linguistic processing & Vectorization engine
│        │   ├── __init__.py
│        │   ├── model_loader.py     # Manages PhoBERT/ViFiNBERT load states (CPU/GPU) & tokenization
│        │   └── sentiment.py        # Maps financial news vectors to numerical sentiment scores
│        │
│        ├── matrix/                 # Strategic decision logic
│        │   ├── __init__.py
│        │   └── horizon_scorer.py   # Processes sentiment vectors to produce Short, Medium, & Long-Term risk actions
│        │
│        └── alerts/                 # External alert engine
│            ├── __init__.py
│            └── telegram_bot.py     # Asynchronous Telegram notification sender
│
└── ui/                         # Rainmeter & Embedded Web Dashboard Package
    ├── RiskDashboard.ini       # Rainmeter skin definition (Loads WebView2 transparent frame)
    └── www/                    # UI assets rendered in WebView2
        ├── index.html          # Desktop widget main layout
        ├── css/
        │   └── styles.css      # Custom styling (glassmorphism UI)
        └── js/
            ├── app.js          # REST and WebSocket client connected to FastAPI backend
            └── chart.js        # Lightweight charts rendering engine
```

---

## 3. Database Schema Overview

### 3.1. Table: `tickers`
* `id` (SERIAL, Primary Key)
* `symbol` (VARCHAR(10), Unique, Indexed) — e.g., `'VPB'`, `'VNM'`
* `company_name` (VARCHAR(255))
* `sector` (VARCHAR(100))
* `is_active` (BOOLEAN, Default `TRUE`)

### 3.2. Table: `news_articles`
* `id` (UUID, Primary Key)
* `ticker_id` (INT, Foreign Key referencing `tickers.id`)
* `source_url` (TEXT)
* `publisher` (VARCHAR(100)) — Extracted via `vnstock` payload metadata
* `published_at` (TIMESTAMP With Time Zone)
* `headline` (TEXT)
* `raw_content` (TEXT)
* `content_hash` (VARCHAR(64), Unique, Indexed) — SHA-256 hex digest (`SHA256(headline + content)`) to block duplicate entries

### 3.3. Table: `risk_assessments`
* `id` (SERIAL, Primary Key)
* `article_id` (UUID, Foreign Key referencing `news_articles.id`)
* `embedding` (`VECTOR(768)`) — Dense vector representation generated by PhoBERT / ViFiNBERT
* `sentiment_score` (NUMERIC(4,3)) — Bounded from `-1.000` (Bearish) to `+1.000` (Bullish)
* `horizon_short` (VARCHAR(20)) — `BUY_ACCELERATION`, `SELL`, `NEUTRAL`
* `horizon_medium` (VARCHAR(20)) — `ACCUMULATE`, `REDUCE`, `HOLD`
* `horizon_long` (VARCHAR(20)) — `STRATEGIC_HOLD`, `REBALANCE`
* `confidence_score` (NUMERIC(4,3)) — Model certainty score (`0.000` to `1.000`)
* `evaluated_at` (TIMESTAMP Default `CURRENT_TIMESTAMP`)
