import os
import requests
import pandas as pd
import streamlit as st

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

st.sidebar.title("📊 MarketEval")

api_online = check_api_health()
if api_online:
    st.sidebar.success("🟢 API Server: Online")
else:
    st.sidebar.error("🔴 API Server: Offline")
    st.sidebar.info(
        f"Connecting to: `{API_BASE_URL}`\n"
        "Please ensure FastAPI is running via `uvicorn backend.main:app --reload --reload-dir backend --port 8000`"
    )


if st.sidebar.button("🔄 Refresh All Data"):
    st.cache_data.clear()
    st.rerun()

# Explicitly declare the pages that should appear in the nav.
# main.py is intentionally NOT in this list, so it never shows up as a tab —
# it only acts as the router that decides which page script to execute.
pages = [
    st.Page("pages/1_Dashboard.py", title="Dashboard", icon="📈", default=True),
    st.Page("pages/2_Ticker_Management.py", title="Ticker Management", icon="⚙️"),
]

pg = st.navigation(pages)
pg.run()

st.sidebar.markdown("---")
st.sidebar.caption("MarketEval v1.0")
st.sidebar.caption("Vietnamese Financial Intelligence Engine.")
