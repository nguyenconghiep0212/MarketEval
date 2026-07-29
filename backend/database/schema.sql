-- ==========================================
-- STEP 1: DROP ALL EXISTING TABLES
-- ==========================================
DROP TABLE IF EXISTS risk_assessments CASCADE;
DROP TABLE IF EXISTS news_articles CASCADE;
DROP TABLE IF EXISTS crawler_sources CASCADE;
DROP TABLE IF EXISTS tickers CASCADE;
DROP TABLE IF EXISTS article_attachments CASCADE;

-- ==========================================
-- STEP 2: ENABLE EXTENSIONS
-- ==========================================
CREATE EXTENSION IF NOT EXISTS vector;

-- ==========================================
-- STEP 3: CREATE TABLES & INDEXES
-- ==========================================

-- 1. Tickers Table
CREATE TABLE tickers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    company_name VARCHAR(255),
    sector VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Crawler Sources Table
CREATE TABLE crawler_sources (
    id SERIAL PRIMARY KEY,
    ticker_id INT REFERENCES tickers(id) ON DELETE CASCADE,
    publisher VARCHAR(50) NOT NULL,       -- e.g., 'CafeF', 'VnEconomy'
    pool_url TEXT NOT NULL,               -- Search/category pool URL
    is_active BOOLEAN DEFAULT TRUE,
    last_crawled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_crawler_sources_ticker ON crawler_sources(ticker_id);

-- 3. News Articles Table
CREATE TABLE news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker_id INT REFERENCES tickers(id) ON DELETE CASCADE,
    source_url TEXT,
    publisher VARCHAR(100),                              
    published_at TIMESTAMP WITH TIME ZONE,
    headline TEXT NOT NULL,
    raw_content TEXT,
    pdf_url TEXT,
    content_hash VARCHAR(64) UNIQUE NOT NULL,             -- SHA-256 (headline + body)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE news_articles ADD COLUMN IF NOT EXISTS pdf_url TEXT;
CREATE INDEX idx_news_ticker_published ON news_articles(ticker_id, published_at DESC);

-- 4. Risk Assessments Table
CREATE TABLE risk_assessments (
    id SERIAL PRIMARY KEY,
    article_id UUID UNIQUE REFERENCES news_articles(id) ON DELETE CASCADE,
    embedding VECTOR(768),                               -- 768-dim PhoBERT output vector
    sentiment_score NUMERIC(4,3),                        -- -1.000 to +1.000
    horizon_short VARCHAR(20),                           -- BUY_ACCELERATION, SELL, NEUTRAL
    horizon_medium VARCHAR(20),                          -- ACCUMULATE, REDUCE, HOLD
    horizon_long VARCHAR(20),                            -- STRATEGIC_HOLD, REBALANCE
    confidence_score NUMERIC(4,3),                       -- 0.000 to 1.000
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. HNSW Vector Index for Fast K-NN Searches
CREATE INDEX idx_risk_embedding ON risk_assessments 
USING hnsw (embedding vector_cosine_ops);

-- 6. Article Attachments Table
CREATE TABLE IF NOT EXISTS article_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID NOT NULL REFERENCES news_articles(id) ON DELETE CASCADE,
    file_url TEXT NOT NULL,
    file_name TEXT,
    raw_content TEXT NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attachments_article_id ON article_attachments(article_id);