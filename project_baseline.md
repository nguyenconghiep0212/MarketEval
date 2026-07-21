# Project Blueprint: Technology Stack & Directory Architecture

This document establishes the official software architecture, database schemas, and folder structures for the **Intelligent News-Driven Risk Assessment & Trading Decision Support System (TDSS)** tailored for the Vietnamese market.

---

## 1. Core Technology Stack

To achieve high-throughput web crawling, context-aware processing of Vietnamese financial terminology, and low-latency dashboard rendering, the platform uses the following decoupled technology stack:

### 1.1. Backend & Automation Core
* **Language:** `Python 3.11+` (Industry standard for financial engineering, data wrangling, and machine learning pipelines).
* **Task Scheduling:** `APScheduler` (Advanced Python Scheduler). Runs lightweight, recurring internal chron loops to trigger scraper runs without needing heavy infrastructure overhead like Celery or Redis.
* **Network & API Client:** `HTTPX` (Asynchronous HTTP client supporting HTTP/2, excellent for high-speed API data pulling and scraping loops).

### 1.2. Web Scraping & Data Extraction Layer
* **Static Scraper:** `BeautifulSoup4` paired with `lxml` parsing (Ultra-fast, low memory footprint extraction for cleanly structured archive lists like CafeF/Vietstock).
* **Dynamic/SPA Scraper:** `Playwright for Python` (Asynchronous headless browser driver utilized exclusively as a tactical fallback to handle heavily obfuscated, JavaScript-rendered investor relation pages).
* **Anti-Detection:** `fake-useragent` (Dynamically swaps HTTP headers to mitigate IP rate-limiting blocks).

### 1.3. Intelligence, Vectorization & NLP Layer
* **Base Encoder Model:** `VinAI/phobert-base` or `ViFiNBERT` (Vietnamese Financial BERT). Crucial for translating local retail slang (*"đu đỉnh"*, *"lái lợn"*, *"bán tháo"*) into accurate statistical vector representations.
* **Inference Orchestration:** `Hugging Face Transformers` + `PyTorch` (Local tokenization and tensor computation loops).
* **Text Deduplication:** `Scikit-learn` (Implements rapid TF-IDF vector mapping and Cosine Similarity computations to isolate unique narrative clusters).

### 1.4. Storage & Persistence Framework
* **Primary Database Engine:** `PostgreSQL 16+` (Handles relational storage tracking system watchlists, active ticker states, parsed text arrays, and analytical logs).
* **Vector Vector Engine Extension:** `pgvector` (Keeps the tech stack lean by nesting high-dimensional text embeddings directly inside existing PostgreSQL tables instead of standing up an independent standalone vector database).

### 1.5. Interface & Downstream Communication
* **Data Visualization Interface:** `Streamlit` (Rapid Python frontend framework that translates data states into live dashboards with native layout adjustments, filtering modules, and analytics blocks).
* **Notification Gateways:** Asynchronous webhooks integrated into the `python-telegram-bot` engine for real-time delivery alerts.

---

## 2. Standardized Directory Layout

```
MarketEval/
│
├── .env.example                # Blueprint for system access tokens, proxy nodes, and database connection strings
├── .gitignore                  # Prevents internal caching arrays, system local configurations, and logs from committing
├── README.md                   # Core infrastructure documentation and developer onboarding runbook
├── requirements.txt            # Explicit pinning configurations for all pip package dependencies
│
├── backend/
│   ├── api/                        # FastAPI Local Backend Service Layer
│   │   ├── __init__.py
│   │   ├── main.py                 # Entry point for ASGI server startup and CORS configuration
│   │   └── routes/                 # Endpoint routing logic
│   │       ├── tickers.py          # Watchlist & market metadata endpoints
│   │       ├── risk.py             # Risk scores, sentiment vectors, horizon assessments
│   │       └── ws.py               # WebSocket stream for real-time push updates to desktop UI
│   │        
│   ├── config/                     # System-wide configuration configurations
│   │   ├── __init__.py
│   │   └── settings.py             # Global constants, database URIs, API timeouts, and environment loaders
│   │
│   ├── data/                       # Local volume directory for testing storage assets (Excluded from Git)
│   │   ├── raw/                    # Temporary staging area for raw, uncleaned HTML extracts
│   │   └── secure/                 # Local tracking storage logs or static testing fixture snapshots
│   │
│   ├── database/                   # Schema generation, migrations, and database interaction layer
│   │   ├── __init__.py
│   │   ├── connection.py           # Thread-safe PostgreSQL connection factory loops
│   │   ├── schema.sql              # Core SQL table layouts, indexing scripts, and pgvector parameters
│   │   └── queries.py              # Centralized data access objects (DAO) for transactional DB executions
│   │
│   └── src/                        # Core application workspace
│        ├── __init__.py
│        │
│        ├── ingestion/              # Ticker ingestion processing layer
│        │   ├── __init__.py
│        │   ├── validator.py        # Cross-checks watchlists and strips invalid character arrays
│        │   └── mapper.py           # Appends sector profiles and corporate identifier tokens to tickers
│        │
│        ├── scraping/               # Web extraction engines
│        │   ├── __init__.py
│        │   ├── base_scraper.py     # Base abstract class managing rotating headers, proxy pools, and rate-limiting
│        │   ├── cafef.py            # Targeted extraction pipeline customized for CafeF news flows
│        │   ├── vietstock.py        # Targeted extraction pipeline customized for Vietstock components
│        │   └── deduplicator.py     # Cosine Similarity script validating text uniqueness
│        │
│        ├── nlp/                    # Linguistic processing engine
│        │   ├── __init__.py
│        │   ├── model_loader.py     # Manages GPU/CPU allocation and token caching for PhoBERT/ViFiNBERT
│        │   └── sentiment.py        # Custom classification pipeline matching slang blocks to emotional polarity vectors
│        │
│        ├── matrix/                 # Strategic decision layer
│        │   ├── __init__.py
│        │   └── horizon_scorer.py   # Processes sentiment weight to derive Short, Medium, and Long-Term outputs
│        │
│        └── alerts/                 # Downstream messaging systems
│            ├── __init__.py
│            └── telegram_bot.py     # Manages asynchronous webhook messaging loops passing target risk alerts
│
└── ui/                         # Rainmeter & Embedded Web Dashboard Package
    ├── RiskDashboard.ini       # Rainmeter skin definition (Loads WebView2 plugin and transparent window frame)
    └── www/                    # Web frontend assets rendered inside WebView2
        ├── index.html          # Main HTML structure for desktop widget
        ├── css/
        │   └── styles.css      # Desktop skin styling (transparent backgrounds, glassmorphism UI)
        └── js/
            ├── app.js          # API client handling REST calls and WebSocket streaming from FastAPI
            └── chart.js        # TradingView Lightweight Charts & canvas rendering engine
```

---

## 3. Database Schema Overview (Conceptual Target)

To visualize how your data pieces fit together inside PostgreSQL, here is the relational schema architecture:

### 3.1. Table: `tickers`
Tracks your target watchlists and mapping metadata.
* `id` (SERIAL, Primary Key)
* `symbol` (VARCHAR(10), Unique, Indexed) - e.g., 'VPB', 'VNM'
* `company_name` (VARCHAR(255))
* `sector` (VARCHAR(100)) - e.g., 'Banking', 'Consumer Goods'
* `is_active` (BOOLEAN, Default True)

### 3.2. Table: `news_articles`
Stores raw extracted text and metadata scraped from local portals.
* `id` (UUID, Primary Key)
* `ticker_id` (INT, Foreign Key referencing `tickers.id`)
* `source_url` (TEXT, Unique)
* `publisher` (VARCHAR(100)) - e.g., 'CafeF', 'Vietstock'
* `published_at` (TIMESTAMP With Time Zone)
* `headline` (TEXT)
* `raw_content` (TEXT)
* `cleaned_content` (TEXT)
* `content_hash` (VARCHAR(64)) - Used for LSH/Exact match checks

### 3.3. Table: `risk_assessments`
Houses the final quant data computed by your model matrix.
* `id` (SERIAL, Primary Key)
* `article_id` (UUID, Foreign Key referencing `news_articles.id`)
* `embedding` (VECTOR(768)) - The PhoBERT/ViFiNBERT vector output for similarity searching
* `sentiment_score` (NUMERIC(4,3)) - Bound from -1.000 (Very Bearish) to +1.000 (Very Bullish)
* `horizon_short` (VARCHAR(20)) - BUY_ACCELERATION, SELL, NEUTRAL
* `horizon_medium` (VARCHAR(20)) - ACCUMULATE, REDUCE, HOLD
* `horizon_long` (VARCHAR(20)) - STRATEGIC_HOLD, REBALANCE
* `confidence_score` (NUMERIC(4,3)) - 0.000 to 1.000 scale
* `evaluated_at` (TIMESTAMP Default CURRENT_TIMESTAMP)
