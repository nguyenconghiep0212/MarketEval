import os
import requests
import pandas as pd
import streamlit as st

# NOTE: st.set_page_config is intentionally NOT called here.
# It's called once in main.py (the st.navigation entry point) —
# calling it again in this page would raise a StreamlitAPIException.

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
def fetch_news(tickers: list, limit: int = 50) -> list:
    """
    Fetch news articles (with sentiment scores) for one or more tickers via
    the POST /news/by-tickers endpoint. `limit` is applied PER ticker on the
    backend, so requesting several tickers returns up to `limit` articles for
    EACH of them, not `limit` total.
    """
    if not tickers:
        return []
    try:
        payload = {"tickers": tickers, "limit": limit}
        res = requests.post(f"{API_BASE_URL}/news/article-by-tickers", json=payload, timeout=10)
        if res.status_code == 200:
            return res.json().get("articles", [])
        else:
            st.error(f"Failed to fetch news feed: HTTP {res.status_code} — {res.text}")
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch news feed: {e}")
    return []


def resolve_selected_tickers(selected: str, all_options: list) -> list:
    """Turns a single selectbox choice ('ALL' or one symbol) into the ticker
    array the by-tickers endpoint expects."""
    if selected == "ALL":
        return [s for s in all_options if s != "ALL"]
    return [selected]


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
    return [t["symbol"] for t in tickers_data if "symbol" in t]


# -------------------------------------------------------------------
# MAIN CONTENT — the sidebar (title, nav, API status, refresh, footer)
# now lives centrally in main.py, rendered on every page. This page
# only needs to know whether the API is online to gate its own content.
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
        selected_tickers = resolve_selected_tickers(feed_ticker, ticker_options)
        articles = fetch_news(tickers=selected_tickers, limit=feed_limit)
        df_articles = pd.DataFrame(articles)

        # KPI metrics are calculated directly from the articles currently
        # listed below (i.e. exactly what's on screen for this ticker/limit
        # selection) — not a separate aggregate query.
        total_articles = len(articles)
        if not df_articles.empty and "sentiment_score" in df_articles.columns:
            valid_scores = df_articles["sentiment_score"].dropna()
            avg_sentiment = valid_scores.mean() if not valid_scores.empty else 0.0
            bullish_count = (valid_scores >= 0.20).sum()
            bearish_count = (valid_scores <= -0.20).sum()
            unscored_count = df_articles["sentiment_score"].isna().sum()
        else:
            avg_sentiment = 0.0
            bullish_count = 0
            bearish_count = 0
            unscored_count = total_articles

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Ingested Articles", total_articles)
        k2.metric("Average Sentiment Score", f"{avg_sentiment:+.3f}", delta=get_sentiment_badge(avg_sentiment))
        k3.metric("Bullish Signals", int(bullish_count))
        k4.metric("Bearish Signals", int(bearish_count))

        if unscored_count:
            st.caption(f"ℹ️ {unscored_count} article(s) haven't been scored by the intelligence pipeline yet and are excluded from the average.")

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
        analytics_selected_tickers = resolve_selected_tickers(analytics_ticker, ticker_options)
        analytics_articles = fetch_news(tickers=analytics_selected_tickers, limit=analytics_limit)
        df_analytics = pd.DataFrame(analytics_articles)

        st.subheader("Sentiment Score Distribution")

        if not df_analytics.empty and "sentiment_score" in df_analytics.columns and not df_analytics["sentiment_score"].dropna().empty:
            st.bar_chart(df_analytics["sentiment_score"].dropna(), use_container_width=True)
        else:
            st.info("Insufficient sentiment score data available to build analytics charts.")