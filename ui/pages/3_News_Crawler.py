import os
import requests
import streamlit as st

# NOTE: st.set_page_config is intentionally NOT called here.
# It's called once in main.py (the st.navigation entry point).

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")


def fetch_active_ticker_symbols() -> list:
    """Fetches only active tickers (is_active=True) for the multiselect."""
    try:
        res = requests.get(f"{API_BASE_URL}/tickers/all", timeout=5)
        if res.status_code == 200:
            tickers = res.json().get("tickers", [])
            return sorted(t["symbol"] for t in tickers if t.get("is_active"))
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to fetch tickers: {e}")
    return []


# --- UI LAYOUT ---
st.title("🕸️ News Crawling")
st.markdown(
    "Select one or more active tickers and crawl their news sources "
    "(CafeF, Vietstock, StockBiz). Each selected ticker is crawled "
    "**concurrently**, and progress streams live in the console below."
)

if "crawl_log_lines" not in st.session_state:
    st.session_state["crawl_log_lines"] = []

active_symbols = fetch_active_ticker_symbols()

if not active_symbols:
    st.info(
        "No active tickers found. Add or activate a ticker on the "
        "Ticker Management page first."
    )
    st.stop()

side_col, content_col = st.columns([1, 3], gap="large")

with side_col:
    st.markdown("#### Select Tickers")

    select_all = st.checkbox("Select all active tickers", key="crawl_select_all")
    default_selection = active_symbols if select_all else st.session_state.get(
        "crawl_ticker_multiselect", []
    )

    selected_tickers = st.multiselect(
        "Active Tickers",
        options=active_symbols,
        default=default_selection,
        key="crawl_ticker_multiselect",
    )
    st.caption(f"{len(selected_tickers)} of {len(active_symbols)} selected")

    start_clicked = st.button(
        "🚀 Start Crawling",
        type="primary",
        use_container_width=True,
        disabled=(len(selected_tickers) == 0),
    )

    if st.button("🧹 Clear Console", use_container_width=True):
        st.session_state["crawl_log_lines"] = []
        st.rerun()

    st.markdown("---")
    st.caption(
        "Each ticker runs as its own concurrent crawl task on the backend. "
        "Within a ticker, all of its sources (CafeF, Vietstock, StockBiz "
        "news, StockBiz financial reports) also run concurrently."
    )

with content_col:
    st.markdown("#### Console")

    CONSOLE_HEIGHT_VH = 65  # fill most of the available viewport height

    # CSS-fix the console's height and make it scroll internally instead of
    # growing the page — targets the keyed container below via the
    # `st-key-<key>` class Streamlit generates for st.container(key=...).
    st.markdown(
        f"""
        <style>
        div.st-key-crawl_console {{
            height: {CONSOLE_HEIGHT_VH}vh;
            overflow-y: auto;
            border: 1px solid rgba(250, 250, 250, 0.2);
            border-radius: 0.5rem;
        }}
        div.st-key-crawl_console pre {{
            height: 100%;
            margin: 0;
            overflow-y: auto;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="crawl_console"):
        console_placeholder = st.empty()

    def render_console():
        text = "\n".join(st.session_state["crawl_log_lines"])
        console_placeholder.code(
            text or "Console is empty. Select tickers and click Start Crawling.",
            language="bash",
        )

    render_console()

    if start_clicked:
        st.session_state["crawl_log_lines"] = []
        log_lines = st.session_state["crawl_log_lines"]

        try:
            with requests.post(
                f"{API_BASE_URL}/crawl/run",
                json={"tickers": selected_tickers},
                stream=True,
                timeout=(10, 900),  # 10s to connect, up to 15 min to read
            ) as response:
                if response.status_code != 200:
                    log_lines.append(
                        f"❌ Failed to start crawl: HTTP {response.status_code} — {response.text}"
                    )
                    render_console()
                else:
                    for raw_line in response.iter_lines(decode_unicode=True):
                        if not raw_line:
                            continue
                        log_lines.append(raw_line)
                        render_console()
        except requests.exceptions.RequestException as e:
            log_lines.append(f"❌ Connection error: {e}")
            render_console()

        st.success("Crawl stream ended — see the console above for the full log.")