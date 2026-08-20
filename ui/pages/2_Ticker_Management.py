import os
import requests
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Ticker Management", page_icon="⚙️", layout="wide")

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")

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
        st.success(f"Added {symbol} successfully!")
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

# --- UI LAYOUT ---
st.title("⚙️ Ticker Management")
st.markdown("Add new stocks to the watchlist, toggle crawling status, or remove them entirely.")

# Fetch data
df_tickers = fetch_all_tickers()

# --- TOP SECTION: ADD NEW TICKER ---
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

st.divider()

# --- BOTTOM SECTION: DATA TABLE & MANAGEMENT ---
st.subheader("Current Watchlist")

if df_tickers.empty:
    st.info("No tickers found. Please add one above.")
else:
    # Display the dataframe cleanly
    st.dataframe(
        df_tickers[["symbol", "company_name", "sector", "is_active"]],
        use_container_width=True,
        hide_index=True
    )

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
        
        st.caption("⚠️ *Warning: Deleting a ticker automatically wipes all its associated news, PDFs, and vector embeddings.*")
        
        if st.button("🗑️ Permanently Delete", type="primary"):
            delete_ticker(selected_delete_data["id"])
            st.rerun()