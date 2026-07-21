-- Enable pgvector extension for embedding storage
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. Table: tickers
-- Tracks active watchlist items and metadata.
-- ============================================================================
CREATE TABLE IF NOT EXISTS tickers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    company_name VARCHAR(255) NOT NULL,
    sector VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tickers_symbol ON tickers(symbol);

-- ============================================================================
-- 2. Table: news_articles
-- Stores raw and cleaned extracted text payloads.
-- ============================================================================
CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker_id INT REFERENCES tickers(id) ON DELETE SET NULL,
    source_url TEXT NOT NULL UNIQUE,
    publisher VARCHAR(100) NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
    headline TEXT NOT NULL,
    raw_content TEXT,
    cleaned_content TEXT,
    content_hash VARCHAR(64) NOT NULL,
    scraped_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_news_articles_ticker_id ON news_articles(ticker_id);
CREATE INDEX IF NOT EXISTS idx_news_articles_content_hash ON news_articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_news_articles_published_at ON news_articles(published_at DESC);

-- ============================================================================
-- 3. Table: risk_assessments
-- Stores vector embeddings, NLP sentiment, and multi-horizon decision outputs.
-- ============================================================================
CREATE TABLE IF NOT EXISTS risk_assessments (
    id SERIAL PRIMARY KEY,
    article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    embedding vector(768), -- Vector size matching PhoBERT / ViFiNBERT dimension
    sentiment_score NUMERIC(4,3) NOT NULL, -- -1.000 to +1.000
    horizon_short VARCHAR(20) NOT NULL,    -- BUY_ACCELERATION, SELL, NEUTRAL
    horizon_medium VARCHAR(20) NOT NULL,   -- ACCUMULATE, REDUCE, HOLD
    horizon_long VARCHAR(20) NOT NULL,     -- STRATEGIC_HOLD, REBALANCE
    confidence_score NUMERIC(4,3) NOT NULL, -- 0.000 to 1.000
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_assessments_article_id ON risk_assessments(article_id);

-- Optional HNSW Vector Index for fast Cosine Similarity searches on embeddings
CREATE INDEX IF NOT EXISTS idx_risk_assessments_embedding 
ON risk_assessments USING hnsw (embedding vector_cosine_ops);