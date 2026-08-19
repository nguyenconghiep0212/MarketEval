import os
import requests
import pandas as pd
import streamlit as st

# Configure Streamlit page settings
st.set_page_config(
    page_title="MarketEval Intelligence Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API Endpoint Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
HEALTH_CHECK_URL = API_BASE_URL.replace("/api", "")

# -------------------------------------------------------------------
# API HELPER FUNCTIONS (WITH CACHING)
# -------------------------------------------------------------------

@st.cache_data(ttl=10)
def check_api_health() -> bool:
    """Verifies that the FastAPI backend server is online."""
    try:
        res = requests.get(HEALTH_CHECK_URL, timeout=3)
        return res.status_code == 200
    except requests.exceptions.RequestException:
        return False


@st.cache_data(ttl=60)
def fetch_tickers() -> list:
    """Fetch active stock tickers from FastAPI."""
    try:
        res = requests.get(f"{API_BASE_URL}/tickers/all", timeout=5)
        if res.status_code == 200:
            return res.json().get("tickers", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch tickers: {e}")
    return []


@st.cache_data(ttl=15)
def fetch_news(ticker: str = "ALL", limit: int = 50) -> list:
    """Fetch scraped news articles and sentiment scores from FastAPI."""
    try:
        params = {"limit": limit}
        if ticker != "ALL":
            params["ticker"] = ticker
        
        res = requests.get(f"{API_BASE_URL}/news", params=params, timeout=5)
        if res.status_code == 200:
            return res.json().get("articles", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch news feed: {e}")
    return []


@st.cache_data(ttl=15)
def fetch_risk_summary(ticker: str = "ALL") -> list:
    """Fetch aggregated risk signals and multi-horizon scores from FastAPI."""
    try:
        params = {}
        if ticker != "ALL":
            params["ticker"] = ticker
            
        res = requests.get(f"{API_BASE_URL}/risk", params=params, timeout=5)
        if res.status_code == 200:
            return res.json().get("assessments", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch risk signals: {e}")
    return []


# -------------------------------------------------------------------
# HELPER UI UTILITIES
# -------------------------------------------------------------------

def get_sentiment_badge(score: float) -> str:
    """Converts a numerical sentiment score (-1.0 to +1.0) into a visual badge."""
    if score is None:
        return "⚪ N/A"
    if score >= 0.20:
        return f"🟢 Bullish ({score:+.2f})"
    elif score <= -0.20:
        return f"🔴 Bearish ({score:+.2f})"
    else:
        return f"🟡 Neutral ({score:+.2f})"


# -------------------------------------------------------------------
# DASHBOARD SIDEBAR
# -------------------------------------------------------------------

st.sidebar.title("📊 MarketEval Controls")

# API Health Status Indicator
api_online = check_api_health()
if api_online:
    st.sidebar.success("🟢 API Server: Online")
else:
    st.sidebar.error("🔴 API Server: Offline")
    st.sidebar.info(f"Connecting to: `{API_BASE_URL}`\nPlease ensure FastAPI is running via `uvicorn backend.main:app --reload`")

st.sidebar.markdown("---")

# Ticker Filter Selector
tickers_data = fetch_tickers() if api_online else []
ticker_options = ["ALL"] + [t["symbol"] for t in tickers_data if "symbol" in t]
selected_ticker = st.sidebar.selectbox("Select Target Ticker", options=ticker_options)

# Record Fetch Limit
article_limit = st.sidebar.slider("News Query Limit", min_value=10, max_value=200, value=50, step=10)

# Refresh Button
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("MarketEval v1.0 | Vietnamese Financial Intelligence Engine")


# -------------------------------------------------------------------
# MAIN CONTENT AREA
# -------------------------------------------------------------------

st.title("📈 MarketEval Intelligence & Risk Dashboard")
st.markdown("Real-time NLP sentiment evaluation, news aggregation, and multi-horizon trading risk signals.")

if not api_online:
    st.warning("⚠️ Cannot fetch real-time intelligence. The backend API server is unresponsive.")
    st.stop()

# Fetch data for current view
articles = fetch_news(ticker=selected_ticker, limit=article_limit)
risk_signals = fetch_risk_summary(ticker=selected_ticker)

# -------------------------------------------------------------------
# TOP KPI METRICS ROW
# -------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

total_articles = len(articles)
df_articles = pd.DataFrame(articles)

if not df_articles.empty and "sentiment_score" in df_articles.columns:
    valid_scores = df_articles["sentiment_score"].dropna()
    avg_sentiment = valid_scores.mean() if not valid_scores.empty else 0.0
    bullish_count = (valid_scores >= 0.20).sum()
    bearish_count = (valid_scores <= -0.20).sum()
else:
    avg_sentiment = 0.0
    bullish_count = 0
    bearish_count = 0

with col1:
    st.metric("Total Ingested Articles", total_articles)

with col2:
    st.metric("Average Sentiment Score", f"{avg_sentiment:+.3f}", delta=get_sentiment_badge(avg_sentiment))

with col3:
    st.metric("Bullish Signals", int(bullish_count))

with col4:
    st.metric("Bearish Signals", int(bearish_count))

st.markdown("---")

# -------------------------------------------------------------------
# TABBED INTERFACE
# -------------------------------------------------------------------

tab_feed, tab_risk, tab_analytics = st.tabs(["📰 Ingested News Feed", "🎯 Risk & Horizon Signals", "📊 Sentiment Distribution"])

# --- TAB 1: News Feed ---
with tab_feed:
    st.subheader(f"Latest News Articles ({selected_ticker})")
    
    if df_articles.empty:
        st.info("No news articles found for the selected filter.")
    else:
        # Format table columns
        display_df = df_articles.copy()
        
        if "sentiment_score" in display_df.columns:
            display_df["Sentiment"] = display_df["sentiment_score"].apply(get_sentiment_badge)
        
        # Select key columns to display
        columns_to_show = [col for col in ["published_at", "ticker_symbol", "publisher", "headline", "Sentiment", "source_url"] if col in display_df.columns]
        
        st.dataframe(
            display_df[columns_to_show],
            column_config={
                "source_url": st.column_config.LinkColumn("Source Article"),
                "published_at": st.column_config.DatetimeColumn("Published At", format="DD/MM/YYYY HH:mm"),
                "ticker_symbol": "Ticker",
                "publisher": "Source",
                "headline": "Headline"
            },
            hide_index=True,
            use_container_width=True
        )

# --- TAB 2: Multi-Horizon Risk Assessment ---
with tab_risk:
    st.subheader("Decision Matrix & Risk Horizons")
    
    if not risk_signals:
        st.info("No risk matrix evaluations available yet. Run the intelligence pipeline to generate signals.")
    else:
        df_risk = pd.DataFrame(risk_signals)
        
        for _, row in df_risk.iterrows():
            with st.expander(f"📍 {row.get('ticker_symbol', 'N/A')} - {row.get('headline', 'Untitled Article')[:80]}..."):
                r_col1, r_col2, r_col3 = st.columns(3)
                
                with r_col1:
                    st.markdown("**Short-Term Horizon (1-3 Days)**")
                    st.info(row.get("horizon_short", "NEUTRAL"))
                    
                with r_col2:
                    st.markdown("**Medium-Term Horizon (1-4 Weeks)**")
                    st.warning(row.get("horizon_medium", "NEUTRAL"))
                    
                with r_col3:
                    st.markdown("**Long-Term Horizon (1-6 Months)**")
                    st.success(row.get("horizon_long", "NEUTRAL"))
                    
                st.caption(f"Evaluated score: {row.get('sentiment_score', 0.0):.3f} | Article ID: {row.get('article_id', 'N/A')}")

# --- TAB 3: Sentiment Analytics ---
with tab_analytics:
    st.subheader("Sentiment Score Distribution")
    
    if not df_articles.empty and "sentiment_score" in df_articles.columns and not df_articles["sentiment_score"].dropna().empty:
        # Histogram of sentiment distribution
        st.bar_chart(df_articles["sentiment_score"].dropna(), use_container_width=True)
    else:
        st.info("Insufficient sentiment score data available to build analytics charts.")