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

        res = requests.post(f"{API_BASE_URL}/news/article-by-tickers", json={"tickers": [ticker] if ticker != "ALL" else [], "limit": limit}, timeout=5)
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


def ticker_options_list(tickers_data: list) -> list:
    return ["ALL"] + [t["symbol"] for t in tickers_data if "symbol" in t]


# -------------------------------------------------------------------
# MAIN CONTENT — normal page flow, full width minus the reserved
# right padding above. Not nested inside the status panel.
# -------------------------------------------------------------------

st.title("📈 MarketEval Intelligence & Risk Dashboard")
st.markdown("Real-time NLP sentiment evaluation, news aggregation, and multi-horizon trading risk signals.")

api_online = check_api_health()

if not api_online:
    st.warning("⚠️ Cannot fetch real-time intelligence. The backend API server is unresponsive.")
    st.stop()

tickers_data = fetch_tickers()
ticker_options = ticker_options_list(tickers_data)

tab_feed, tab_risk, tab_analytics = st.tabs(
    ["📰 Ingested News Feed", "🎯 Risk & Horizon Signals", "📊 Sentiment Distribution"]
)

# =====================================================================
# TAB 1: News Feed — owns its own side menu (ticker filter + limit)
# =====================================================================
with tab_feed:
    side_col, content_col = st.columns([1, 4], gap="large")

    with side_col:
        st.markdown("#### Filters")
        feed_ticker = st.selectbox(
            "Ticker", options=ticker_options, key="feed_ticker"
        )
        feed_limit = st.slider(
            "Article Limit", min_value=10, max_value=200, value=50, step=10, key="feed_limit"
        )
        if st.button("🔄 Refresh Feed", key="feed_refresh"):
            fetch_news.clear()
            st.rerun()

    with content_col:
        articles = fetch_news(ticker=feed_ticker, limit=feed_limit)
        df_articles = pd.DataFrame(articles)

        total_articles = len(articles)
        if not df_articles.empty and "sentiment_score" in df_articles.columns:
            valid_scores = df_articles["sentiment_score"].dropna()
            avg_sentiment = valid_scores.mean() if not valid_scores.empty else 0.0
            bullish_count = (valid_scores >= 0.20).sum()
            bearish_count = (valid_scores <= -0.20).sum()
        else:
            avg_sentiment = 0.0
            bullish_count = 0
            bearish_count = 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Ingested Articles", total_articles)
        k2.metric("Average Sentiment Score", f"{avg_sentiment:+.3f}", delta=get_sentiment_badge(avg_sentiment))
        k3.metric("Bullish Signals", int(bullish_count))
        k4.metric("Bearish Signals", int(bearish_count))

        st.markdown("---")
        st.subheader(f"Latest News Articles ({feed_ticker})")

        if df_articles.empty:
            st.info("No news articles found for the selected filter.")
        else:
            display_df = df_articles.copy()
            if "sentiment_score" in display_df.columns:
                display_df["Sentiment"] = display_df["sentiment_score"].apply(get_sentiment_badge)

            columns_to_show = [
                col for col in
                ["published_at", "ticker_symbol", "publisher", "headline", "Sentiment", "source_url"]
                if col in display_df.columns
            ]

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

# =====================================================================
# TAB 2: Risk & Horizon Signals — owns its own side menu (ticker only)
# =====================================================================
with tab_risk:
    side_col, content_col = st.columns([1, 4], gap="large")

    with side_col:
        st.markdown("#### Filters")
        risk_ticker = st.selectbox(
            "Ticker", options=ticker_options, key="risk_ticker"
        )
        if st.button("🔄 Refresh Signals", key="risk_refresh"):
            fetch_risk_summary.clear()
            st.rerun()

    with content_col:
        risk_signals = fetch_risk_summary(ticker=risk_ticker)

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

# =====================================================================
# TAB 3: Sentiment Distribution — owns its own side menu (ticker + limit)
# =====================================================================
with tab_analytics:
    side_col, content_col = st.columns([1, 4], gap="large")

    with side_col:
        st.markdown("#### Filters")
        analytics_ticker = st.selectbox(
            "Ticker", options=ticker_options, key="analytics_ticker"
        )
        analytics_limit = st.slider(
            "Article Limit", min_value=10, max_value=200, value=50, step=10, key="analytics_limit"
        )
        if st.button("🔄 Refresh Analytics", key="analytics_refresh"):
            fetch_news.clear()
            st.rerun()

    with content_col:
        analytics_articles = fetch_news(ticker=analytics_ticker, limit=analytics_limit)
        df_analytics = pd.DataFrame(analytics_articles)

        st.subheader("Sentiment Score Distribution")

        if not df_analytics.empty and "sentiment_score" in df_analytics.columns and not df_analytics["sentiment_score"].dropna().empty:
            st.bar_chart(df_analytics["sentiment_score"].dropna(), use_container_width=True)
        else:
            st.info("Insufficient sentiment score data available to build analytics charts.")