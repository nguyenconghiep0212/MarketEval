import os
import requests
import streamlit as st

# st.set_page_config must be called exactly once, here in the entry point,
# BEFORE st.navigation(). Do NOT call it again in the individual page files
# (pages/2_Dashboard.py, pages/1_Ticker_Management.py) or Streamlit will
# raise a "can only be called once" error.
st.set_page_config(
    page_title="MarketEval Intelligence Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
HEALTH_CHECK_URL = API_BASE_URL.replace("/api", "")


@st.cache_data(ttl=10)
def check_api_health() -> bool:
    """Verifies that the FastAPI backend server is online."""
    try:
        res = requests.get(HEALTH_CHECK_URL, timeout=3)
        return res.status_code == 200
    except requests.exceptions.RequestException:
        return False


# Explicitly declare the pages that should appear in the nav.
# main.py is intentionally NOT in this list, so it never shows up as a tab —
# it only acts as the router that decides which page script to execute.
pages = [
    st.Page("pages/1_Dashboard.py", title="Dashboard", icon="📈", default=True),
    st.Page("pages/2_Ticker_Management.py", title="Ticker Management", icon="⚙️"),
    st.Page("pages/3_News_Crawler.py", title="News Crawler", icon="🕸️"),
]

# position="hidden" stops Streamlit from auto-injecting its own nav widget
# at the very top of the sidebar. We build the sidebar ourselves below, in
# whatever order we want — st.page_link() renders a link to each Page.
pg = st.navigation(pages, position="hidden")

with st.sidebar:
    # 1. TITLE — to the front (top of the sidebar)
    st.title("📊 MarketEval")
    
    st.markdown("")

    # 2. NAV — in the middle
    for page in pages:
        st.page_link(page)

    st.markdown("---")

    # 3. STATUS / ACTIONS / FOOTER — after the nav, shown on every page
    #    since this block lives in main.py, not inside a specific page.
    api_online = check_api_health()
    if api_online:
        st.success("API Server: Online")
    else:
        st.error("API Server: Offline")
        st.caption(
            f"Connecting to: `{API_BASE_URL}`\n\n"
            "Ensure FastAPI is running via `uvicorn backend.main:app --reload`"
        )

    if st.button("🔄 Refresh All Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.caption("MarketEval v1.0")
    st.caption("Vietnamese Financial Intelligence Engine")

pg.run()