# MarketEval

The Project Roadmap

#### Phase 1: Foundation & Storage
Set up the Python virtual environment and clean project folder layout.
Install PostgreSQL 16+ with the pgvector extension enabled.
Execute schema migration scripts (schema.sql) to instantiate tickers, news_articles, and risk_assessments tables.

#### Phase 2: vnstock Ingestion Pipeline & Deduplication
Implement vnstock_client.py to poll financial news and market disclosures systematically.
Build the SHA-256 deduplicator.py pipeline to hash incoming news blocks and verify uniqueness against content_hash indexes before writing to PostgreSQL.
Set up APScheduler loops inside FastAPI to keep data fetching running automatically in the background.


#### Phase 3: Intelligence Layer (NLP & Vectorization)
Integrate PhoBERT or ViFiNBERT model loaders using PyTorch and Hugging Face.
Implement text vectorization to store 768-dimensional embeddings into PostgreSQL pgvector columns.
Develop the sentiment analysis classifier to produce bounded scores (-1.0 to +1.0).
    -1.000: Strongly Bearish (negative market impact/pessimistic outlook).
    +1.000: Strongly Bullish (positive market impact/optimistic outlook).
                           ┌────────────────────────┐
                           │ Raw Articles & PDFs    │
                           └───────────┬────────────┘
                                       │
                           ┌───────────▼────────────┐
                           │  src/intelligence/     │
                           │     text_chunker.py    │
                           └───────────┬────────────┘
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
          ┌─────────────────────┐             ┌─────────────────────┐
          │   embeddings.py     │             │    sentiment.py     │
          │ (PhoBERT Bi-Encoder)│             │ (ViFiNBERT / Model) │
          └──────────┬──────────┘             └──────────┬──────────┘
                     │ (768-dim Vector)                  │ (-1.0 to +1.0)
                     └─────────────────┬─────────────────┘
                                       │
                           ┌───────────▼────────────┐
                           │ PostgreSQL + pgvector  │
                           └────────────────────────┘

#### Phase 4: Decision Matrix & Risk Assessment
Write horizon_scorer.py logic to evaluate historical vector trends and sentiment scores.
Generate automated actionable signal outputs across Short, Medium, and Long-Term horizons.

#### Phase 5: UI Integration & Automated Delivery
Construct FastAPI REST endpoints and WebSocket streams (ws.py).
Connect the Rainmeter + WebView2 desktop overlay to display live risk indices and signals.
Wire up asynchronous Telegram bot webhooks to broadcast critical financial alerts instantly.