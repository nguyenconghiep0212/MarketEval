# MarketEval

The Project Roadmap

### Phase 1: Foundation & Storage
Set up the Python virtual environment and folder structure.
Initialize the PostgreSQL database and create the tables to hold our tickers and news articles.

### Phase 2: The Extraction Engine
Write the first targeted web scraper (e.g., targeting CafeF) using BeautifulSoup4 and HTTPX to pull down raw Vietnamese financial headlines and content.

### Phase 3: The Intelligence Layer (NLP)
Integrate the PhoBERT / ViFiNBERT model to analyze the scraped text and spit out a numerical sentiment score.

### Phase 4: The Decision Matrix
Write the logic that translates those NLP numbers into Short/Medium/Long-term risk assessments.

### Phase 5: Interface & Delivery
Hook up the Streamlit dashboard and Telegram webhooks so you can actually see and use the data.