import os
import requests
import pandas as pd
import streamlit as st

# st.set_page_config must be called exactly once, here in the entry point,
# BEFORE st.navigation(). Remove any st.set_page_config(...) calls from
# the individual page files (pages/2_Dashboard.py, pages/1_Ticker_Management.py)
# or Streamlit will raise a "can only be called once" error.
st.set_page_config(
    page_title="MarketEval Intelligence Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Explicitly declare the pages that should appear in the nav.
# main.py is intentionally NOT in this list, so it never shows up as a tab —
# it only acts as the router that decides which page script to execute.
pages = [
    st.Page("pages/1_Dashboard.py", title="Dashboard", icon="📈", default=True),
    st.Page("pages/2_Ticker_Management.py", title="Ticker Management", icon="⚙️"),
]

pg = st.navigation(pages)
pg.run()

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
# GLOBAL SIDEBAR — app-level chrome only, NOT tab-specific filters
# -------------------------------------------------------------------

st.sidebar.title("📊 MarketEval")

api_online = check_api_health()
if api_online:
    st.sidebar.success("🟢 API Server: Online")
else:
    st.sidebar.error("🔴 API Server: Offline")
    st.sidebar.info(
        f"Connecting to: `{API_BASE_URL}`\n"
        "Please ensure FastAPI is running via `uvicorn backend.main:app --reload`"
    )

st.sidebar.markdown("---")

if st.sidebar.button("🔄 Refresh All Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("MarketEval v1.0 | Vietnamese Financial Intelligence Engine")
st.sidebar.caption("Each tab below has its own filters — the sidebar only holds app-wide controls.")
