-- ==========================================
-- STEP 1: NON-DESTRUCTIVE SCHEMA INIT
-- ==========================================
-- Intentionally non-destructive: preserve existing data on repeated runs.
-- For clean resets in local development, run explicit DROP statements manually.
DROP TABLE IF EXISTS risk_assessments CASCADE;
DROP TABLE IF EXISTS news_articles CASCADE;
DROP TABLE IF EXISTS financial_analysis_articles CASCADE;
DROP TABLE IF EXISTS crawler_sources CASCADE;
DROP TABLE IF EXISTS tickers CASCADE;
DROP TABLE IF EXISTS article_attachments CASCADE;
DROP TABLE IF EXISTS article_embeddings CASCADE;

-- ==========================================
-- STEP 2: ENABLE EXTENSIONS
-- ==========================================
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ==========================================
-- STEP 3: CREATE TABLES & INDEXES
-- ==========================================

-- 1. Tickers Table
CREATE TABLE IF NOT EXISTS tickers (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) UNIQUE NOT NULL,
    company_name VARCHAR(255),
    sector VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Crawler Sources Table
CREATE TABLE IF NOT EXISTS crawler_sources (
    id SERIAL PRIMARY KEY,
    ticker_id INT REFERENCES tickers(id) ON DELETE CASCADE,
    publisher VARCHAR(50) NOT NULL,       -- e.g., 'CafeF', 'VnEconomy'
    pool_url TEXT NOT NULL,               -- Search/category pool URL
    is_active BOOLEAN DEFAULT TRUE,
    last_crawled_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_crawler_sources_ticker ON crawler_sources(ticker_id);

-- 3. News Articles Table
CREATE TABLE IF NOT EXISTS news_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker_id INT REFERENCES tickers(id) ON DELETE CASCADE,
    source_url TEXT,
    publisher VARCHAR(100),                              
    published_at TIMESTAMP WITH TIME ZONE,
    headline TEXT NOT NULL,
    raw_content TEXT,
    pdf_url TEXT,
    is_pdf_download_url Boolean DEFAULT FALSE,
    content_hash VARCHAR(64) UNIQUE NOT NULL,             -- SHA-256 (headline + body)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_news_ticker_published ON news_articles(ticker_id, published_at DESC);

-- 4. Risk Assessments Table
CREATE TABLE IF NOT EXISTS risk_assessments (
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
ALTER TABLE risk_assessments DROP COLUMN article_id;

ALTER TABLE risk_assessments 
ADD COLUMN news_article_id UUID UNIQUE REFERENCES news_articles(id) ON DELETE CASCADE,
ADD COLUMN financial_analysis_id UUID UNIQUE REFERENCES financial_analysis_articles(id) ON DELETE CASCADE;

ALTER TABLE risk_assessments ADD CONSTRAINT chk_risk_assessments_single_parent CHECK (
    (news_article_id IS NOT NULL AND financial_analysis_id IS NULL)
    OR (news_article_id IS NULL AND financial_analysis_id IS NOT NULL)
);
-- 5. HNSW Vector Index for Fast K-NN Searches
CREATE INDEX IF NOT EXISTS idx_risk_embedding ON risk_assessments 
USING hnsw (embedding vector_cosine_ops);


-- 6. Financial analysis articles table
CREATE TABLE IF NOT EXISTS financial_analysis_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker_id INT REFERENCES tickers(id) ON DELETE CASCADE,
    source_url TEXT,
    publisher VARCHAR(100),                              
    published_at TIMESTAMP WITH TIME ZONE,
    headline TEXT NOT NULL,
    raw_content TEXT,
    pdf_url TEXT,
    is_pdf_download_url Boolean DEFAULT FALSE,
    content_hash VARCHAR(64) UNIQUE NOT NULL,             -- SHA-256 (headline + body)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_financial_analysis_ticker_published ON financial_analysis_articles(ticker_id, published_at DESC);

-- 7. Article Attachments Table
CREATE TABLE IF NOT EXISTS article_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    news_article_id UUID REFERENCES news_articles(id) ON DELETE CASCADE,
    financial_analysis_id UUID REFERENCES financial_analysis_articles(id) ON DELETE CASCADE,
    file_url TEXT NOT NULL,
    file_name TEXT,
    raw_content TEXT NOT NULL,
    content_hash VARCHAR(64) UNIQUE NOT NULL,
    CONSTRAINT chk_article_attachments_single_parent CHECK (
        (news_article_id IS NOT NULL AND financial_analysis_id IS NULL)
        OR (news_article_id IS NULL AND financial_analysis_id IS NOT NULL)
    ),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attachments_news_article_id ON article_attachments(news_article_id);
CREATE INDEX IF NOT EXISTS idx_attachments_financial_analysis_id ON article_attachments(financial_analysis_id);

-- 8. Create the unified embeddings table
CREATE TABLE IF NOT EXISTS article_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Nullable foreign keys pointing to potential source tables
    news_article_id UUID REFERENCES news_articles(id) ON DELETE CASCADE,
    financial_analysis_id UUID REFERENCES financial_analysis_articles(id) ON DELETE CASCADE,
    attachment_id UUID REFERENCES article_attachments(id) ON DELETE CASCADE,
    
    -- Chunk Metadata
    chunk_index INT NOT NULL DEFAULT 0,
    chunk_text TEXT NOT NULL,
    
    -- 768-dimensional dense vector (PhoBERT / vietnamese-bi-encoder standard)
    embedding vector(768) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- ENFORCE: Exactly ONE parent reference must be provided per embedding
    CONSTRAINT check_embedding_single_parent CHECK (
        (
            (news_article_id IS NOT NULL)::INT + 
            (financial_analysis_id IS NOT NULL)::INT + 
            (attachment_id IS NOT NULL)::INT
        ) = 1
    )
);

CREATE INDEX IF NOT EXISTS idx_article_embeddings_vector 
ON article_embeddings 
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_embeddings_news_article 
ON article_embeddings(news_article_id) 
WHERE news_article_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_embeddings_fin_analysis 
ON article_embeddings(financial_analysis_id) 
WHERE financial_analysis_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_embeddings_attachment 
ON article_embeddings(attachment_id) 
WHERE attachment_id IS NOT NULL;