import os
import requests
import pandas as pd
import streamlit as st

# NOTE: st.set_page_config is intentionally NOT called here.
# It's called once in main.py (the st.navigation entry point) —
# calling it again in this page would raise a StreamlitAPIException.

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")

DEFAULT_SOURCE_COUNT = 4  # CafeF, Vietstock, StockBiz, StockBiz_Financial_Report

# --- API HELPER FUNCTIONS ---
def fetch_all_tickers() -> pd.DataFrame:
    try:
        res = requests.get(f"{API_BASE_URL}/tickers/all", timeout=5)
        if res.status_code == 200:
            data = res.json().get("tickers", [])
            return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Failed to fetch tickers: {e}")
    return pd.DataFrame()

def create_new_ticker(symbol: str, name: str, sector: str):
    payload = {"symbol": symbol, "company_name": name, "sector": sector}
    res = requests.post(f"{API_BASE_URL}/tickers/", json=payload)
    if res.status_code == 201:
        st.success(f"Added {symbol} and seeded its {DEFAULT_SOURCE_COUNT} crawler sources (CafeF, Vietstock, StockBiz, StockBiz Financial Report).")
    else:
        st.error(f"Failed to add {symbol}. It might already exist.")

def toggle_ticker(ticker_id: int, current_status: bool):
    payload = {"is_active": not current_status}
    res = requests.put(f"{API_BASE_URL}/tickers/{ticker_id}/toggle", json=payload)
    if res.status_code == 200:
        st.success("Status updated.")
    else:
        st.error("Failed to update status.")

def delete_ticker(ticker_id: int):
    res = requests.delete(f"{API_BASE_URL}/tickers/{ticker_id}")
    if res.status_code == 204:
        st.success("Ticker deleted successfully.")
    else:
        st.error("Failed to delete ticker.")

def seed_missing_sources() -> dict:
    """Backfills crawler sources for any ticker missing one or more of the
    4 standard publishers."""
    try:
        res = requests.post(f"{API_BASE_URL}/tickers/seed-sources", timeout=20)
        if res.status_code == 200:
            return res.json()
        else:
            st.error(f"Failed to seed sources: HTTP {res.status_code} — {res.text}")
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to seed sources: {e}")
    return {}


# --- UI LAYOUT ---
st.title("⚙️ Ticker Management")
st.markdown("Add new stocks to the watchlist, toggle crawling status, or remove them entirely.")
st.caption("Every new ticker automatically gets crawler sources seeded for CafeF, Vietstock, StockBiz (news), and StockBiz (financial reports).")

# --- Persisted feedback from the seed-sources backfill (survives the rerun
# triggered by the button below, so the summary is still visible after) ---
if "seed_sources_summary" in st.session_state:
    summary = st.session_state.pop("seed_sources_summary")
    if summary.get("tickers_updated", 0) > 0:
        st.success(
            f"Added {summary.get('total_sources_added', 0)} source(s) across "
            f"{summary.get('tickers_updated', 0)} ticker(s) "
            f"(checked {summary.get('tickers_checked', 0)} ticker(s) with missing sources)."
        )
        if summary.get("details"):
            st.dataframe(pd.DataFrame(summary["details"]), hide_index=True, use_container_width=True)
    else:
        st.info("All tickers already have their crawler sources — nothing to backfill.")

# Fetch data
df_tickers = fetch_all_tickers()

# --- TOP SECTION: ADD NEW TICKER + BACKFILL SOURCES ---
top_col1, top_col2 = st.columns([2, 1])

with top_col1:
    with st.expander("➕ Add New Ticker", expanded=False):
        with st.form("add_ticker_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                new_symbol = st.text_input("Ticker Symbol (e.g., FPT)", max_chars=10).upper()
            with col2:
                new_name = st.text_input("Company Name")
            with col3:
                new_sector = st.text_input("Sector")

            submitted = st.form_submit_button("Add Ticker")
            if submitted:
                if new_symbol and new_name:
                    create_new_ticker(new_symbol, new_name, new_sector)
                    st.rerun()  # Refresh the page to show the new data
                else:
                    st.warning("Symbol and Company Name are required.")

with top_col2:
    missing_count = 0
    if not df_tickers.empty and "source_count" in df_tickers.columns:
        missing_count = int((df_tickers["source_count"] < DEFAULT_SOURCE_COUNT).sum())

    button_label = "🌱 Seed Missing Sources"
    if missing_count:
        button_label += f" ({missing_count})"

    if st.button(button_label, use_container_width=True, disabled=(missing_count == 0 and not df_tickers.empty)):
        summary = seed_missing_sources()
        if summary:
            st.session_state["seed_sources_summary"] = summary
        st.rerun()

st.divider()

# --- BOTTOM SECTION: DATA TABLE & MANAGEMENT ---
st.subheader("Current Watchlist")

if df_tickers.empty:
    st.info("No tickers found. Please add one above.")
else:
    # Display the dataframe cleanly, including source coverage (e.g. "4/4")
    display_df = df_tickers.copy()
    if "source_count" in display_df.columns:
        display_df["sources"] = display_df["source_count"].apply(
            lambda c: f"{int(c)}/{DEFAULT_SOURCE_COUNT}"
        )

    columns_to_show = [
        col for col in ["symbol", "company_name", "sector", "is_active", "sources"]
        if col in display_df.columns
    ]

    st.dataframe(
        display_df[columns_to_show],
        column_config={
            "symbol": "Symbol",
            "company_name": "Company Name",
            "sector": "Sector",
            "is_active": "Active",
            "sources": st.column_config.TextColumn("Crawler Sources"),
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.divider()

    st.markdown("### Actions")
    colA, colB = st.columns(2)

    # Generate a map for the selectboxes
    ticker_map = {f"{row['symbol']} - {row['company_name']}": row for _, row in df_tickers.iterrows()}

    with colA:
        st.markdown("**Toggle Activation Status**")
        toggle_selection = st.selectbox("Select Ticker to Toggle", options=list(ticker_map.keys()), key="toggle_select")
        selected_toggle_data = ticker_map[toggle_selection]

        current_state = "ACTIVE 🟢" if selected_toggle_data["is_active"] else "INACTIVE 🔴"
        st.caption(f"Current Status: **{current_state}**")

        if st.button("Toggle Status"):
            toggle_ticker(selected_toggle_data["id"], selected_toggle_data["is_active"])
            st.rerun()

    with colB:
        st.markdown("**Danger Zone: Delete Ticker**")
        delete_selection = st.selectbox("Select Ticker to Delete", options=list(ticker_map.keys()), key="delete_select")
        selected_delete_data = ticker_map[delete_selection]

        st.caption("⚠️ *Warning: Deleting a ticker automatically wipes all its associated news, PDFs, vector embeddings, and crawler sources.*")

        if st.button("🗑️ Permanently Delete", type="primary"):
            delete_ticker(selected_delete_data["id"])
            st.rerun()