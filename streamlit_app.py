import streamlit as st
import requests
import json
import pandas as pd
from typing import Dict, Any, Optional
from datetime import date
import pathlib
import time

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
FASTAPI_BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Book Management System",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────
# LOAD EXTERNAL CSS
# ─────────────────────────────────────────────
def load_css(file_name: str):
    css_path = pathlib.Path(file_name)
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning(f"⚠️ CSS file '{file_name}' not found. Make sure style.css is in the same folder as streamlit_app.py.")

load_css("style.css")

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
for key, default in {
    "view_db": False,
    "fetched_book_data": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def api(method: str, path: str, **kwargs):
    """Thin wrapper around requests; returns (response | None, error_str | None)."""
    try:
        resp = getattr(requests, method)(f"{FASTAPI_BASE_URL}{path}", timeout=8, **kwargs)
        return resp, None
    except requests.exceptions.ConnectionError:
        return None, "🚨 Cannot reach the FastAPI server. Is it running?"
    except Exception as e:
        return None, str(e)

def show_error(response, fallback="An unknown error occurred."):
    try:
        detail = response.json().get("detail", fallback)
    except Exception:
        detail = fallback
    st.error(f"Error {response.status_code}: {detail}")

def success_and_rerun(msg: str):
    st.cache_data.clear()
    st.success(msg)
    time.sleep(0.8)
    st.rerun()

@st.cache_data(ttl=6)
def fetch_all_books() -> pd.DataFrame:
    resp, err = api("get", "/books/")
    if err:
        st.error(err)
        return pd.DataFrame()
    if resp.status_code == 200:
        data = resp.json()
        return pd.DataFrame(data) if data else pd.DataFrame()
    return pd.DataFrame()

@st.cache_data(ttl=6)
def fetch_overdue() -> pd.DataFrame:
    resp, err = api("get", "/loans/overdue/")
    if err:
        return pd.DataFrame()
    if resp.status_code == 200:
        data = resp.json()
        return pd.DataFrame(data) if data else pd.DataFrame()
    return pd.DataFrame()

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("""
<div class="bms-header">
    <h1>📚 Book Management System</h1>
    <p>Library Operations Dashboard</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# DATABASE FULL VIEW
# ─────────────────────────────────────────────
if st.session_state.view_db:
    st.subheader("📊 Full Book Database")

    if st.button("← Back to Dashboard", key="back_btn"):
        st.session_state.view_db = False
        st.rerun()

    df = fetch_all_books()
    if not df.empty:
        search = st.text_input("🔍 Filter by Title or Author", placeholder="Type to search...")
        if search:
            mask = (
                df["title"].str.contains(search, case=False, na=False) |
                df["author"].str.contains(search, case=False, na=False)
            )
            df = df[mask]
        st.dataframe(df, use_container_width=True, height=520)
        st.caption(f"{len(df)} record(s) shown")
    else:
        st.info("No books found in the database.")
    st.stop()

# ─────────────────────────────────────────────
# MAIN DASHBOARD  ── 3 columns
# ─────────────────────────────────────────────
col1, col2, col3 = st.columns([1.5, 2, 1.1])

# ══════════════════════════════════════════════
# COL 1 — Books (Add / Remove)
# ══════════════════════════════════════════════
with col1:
    st.subheader("🔍 Add / Remove Book")

    search_isbn = st.text_input("ISBN (10 or 13 digits)", key="isbn_input",
                                placeholder="e.g. 9780141036144")
    cleaned = search_isbn.strip().replace("-", "").replace(" ", "")

    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        if st.button("LOOKUP ISBN", key="btn_lookup"):
            if not cleaned:
                st.warning("Enter an ISBN first.")
            else:
                st.session_state.fetched_book_data = None
                with st.spinner("Fetching from Google Books…"):
                    resp, err = api("get", f"/search-isbn/{cleaned}")
                if err:
                    st.error(err)
                elif resp.status_code == 200:
                    st.session_state.fetched_book_data = resp.json()
                    st.success("Book details fetched. Review below ↓")
                else:
                    show_error(resp, "Could not fetch book details.")

    with btn_col2:
        if st.button("REMOVE BOOK", key="btn_remove"):
            if not cleaned:
                st.warning("Enter an ISBN first.")
            else:
                st.session_state.fetched_book_data = None
                with st.spinner("Removing…"):
                    resp, err = api("delete", f"/books/{cleaned}")
                if err:
                    st.error(err)
                elif resp.status_code == 200:
                    success_and_rerun(f"Book {cleaned} removed.")
                else:
                    show_error(resp, "Could not remove book.")

    # ── Review & Save panel ──
    if st.session_state.fetched_book_data:
        st.divider()
        d = st.session_state.fetched_book_data
        st.markdown("**Review & Save**")

        final_title  = st.text_input("Title",  value=d.get("title", ""), key="rv_title")
        final_author = st.text_input("Author", value=d.get("author", ""), key="rv_author")
        final_pages  = st.number_input("Pages", value=int(d.get("pages", 1)),
                                       min_value=1, key="rv_pages")
        final_genre  = st.text_input("Genre",  value=d.get("genre", "General"), key="rv_genre")
        st.caption(f"ISBN: **{d.get('isbn', '')}**")

        if st.button("SAVE TO DATABASE", key="btn_save"):
            payload = {
                "title":     final_title,
                "author":    final_author,
                "pages":     int(final_pages),
                "available": True,
                "isbn":      d.get("isbn", ""),
                "genre":     final_genre,
            }
            resp, err = api("post", "/books/", json=payload)
            if err:
                st.error(err)
            elif resp.status_code == 201:
                st.session_state.fetched_book_data = None
                success_and_rerun(f"'{final_title}' saved successfully!")
            else:
                show_error(resp, "Failed to save book.")

# ══════════════════════════════════════════════
# COL 2 — Loans & Borrower History
# ══════════════════════════════════════════════
with col2:
    tab_loan, tab_history, tab_overdue = st.tabs(["🔄 LOAN / RETURN", "📋 HISTORY", "⚠️ OVERDUE"])

    # ── LOAN / RETURN ──
    with tab_loan:
        st.markdown("")
        loan_cid   = st.text_input("Customer ID",  key="loan_cid",  placeholder="e.g. 1001")
        loan_isbn  = st.text_input("Book ISBN",     key="loan_isbn", placeholder="e.g. 9780141036144")

        c_issue, c_return = st.columns(2)

        with c_issue:
            if st.button("ISSUE BOOK", key="btn_issue"):
                if not loan_isbn or not loan_cid:
                    st.warning("Enter both Customer ID and ISBN.")
                else:
                    try:
                        cid_int = int(loan_cid)
                    except ValueError:
                        st.error("Customer ID must be an integer.")
                        st.stop()

                    payload = {
                        "isbn":          loan_isbn.strip().replace("-", "").replace(" ", ""),
                        "coustomer_id":  cid_int,
                        "issue_date":    date.today().isoformat(),
                    }
                    with st.spinner("Issuing book…"):
                        resp, err = api("post", "/loans/", json=payload)
                    if err:
                        st.error(err)
                    elif resp.status_code == 201:
                        success_and_rerun(f"Book issued to Customer {cid_int}.")
                    else:
                        show_error(resp, "Failed to issue book.")

        with c_return:
            if st.button("RETURN BOOK", key="btn_return"):
                if not loan_isbn or not loan_cid:
                    st.warning("Enter both Customer ID and ISBN.")
                else:
                    try:
                        cid_int = int(loan_cid)
                    except ValueError:
                        st.error("Customer ID must be an integer.")
                        st.stop()

                    payload = {
                        "isbn":         loan_isbn.strip().replace("-", "").replace(" ", ""),
                        "coustomer_id": cid_int,
                    }
                    with st.spinner("Returning book…"):
                        resp, err = api("post", "/loans/return/", json=payload)
                    if err:
                        st.error(err)
                    elif resp.status_code == 200:
                        success_and_rerun("Book returned successfully.")
                    else:
                        show_error(resp, "Failed to return book.")

    # ── BORROWER HISTORY ──
    with tab_history:
        st.markdown("")
        hist_cid = st.text_input("Customer ID", key="hist_cid", placeholder="e.g. 1001")

        if st.button("VIEW HISTORY", key="btn_history"):
            if not hist_cid:
                st.warning("Enter a Customer ID.")
            else:
                with st.spinner("Fetching history…"):
                    resp, err = api("get", f"/loans/customer/{hist_cid.strip()}")

                if err:
                    st.error(err)
                elif resp.status_code == 200:
                    records = resp.json()
                    if not records:
                        st.info("No borrowing history found.")
                    else:
                        df = pd.DataFrame(records)
                        df["due_date"] = pd.to_datetime(df["due_date"]).dt.date
                        today = date.today()

                        def days_status(row):
                            if row["returned"]:
                                return "✅ Returned"
                            diff = (row["due_date"] - today).days
                            return f"🚨 {abs(diff)}d overdue" if diff < 0 else f"{diff}d remaining"

                        def calc_fine(row):
                            if row["returned"]:
                                return 0.0
                            diff = (row["due_date"] - today).days
                            return 0.0 if diff >= 0 else abs(diff) * 5.0

                        df["Status"]   = df.apply(days_status, axis=1)
                        df["Fine (₹)"] = df.apply(calc_fine, axis=1)

                        display = df.rename(columns={"isbn": "ISBN"})[
                            ["ISBN", "issue_date", "due_date", "Status", "Fine (₹)"]
                        ]

                        def style_status(val):
                            if "Returned" in str(val):
                                return "color:#4caf82; font-weight:600"
                            if "overdue" in str(val):
                                return "color:#cf6679; font-weight:600"
                            return "color:#e8d5a3"

                        st.dataframe(
                            display.style.applymap(style_status, subset=["Status"]),
                            use_container_width=True
                        )

                        total_fine = df["Fine (₹)"].sum()
                        if total_fine > 0:
                            st.error(f"Total Outstanding Fine: ₹{total_fine:.0f}")
                        else:
                            st.success("No outstanding fines.")
                else:
                    show_error(resp, "Could not fetch history.")

    # ── OVERDUE LOANS ──
    with tab_overdue:
        st.markdown("")
        if st.button("REFRESH OVERDUE LIST", key="btn_overdue"):
            st.cache_data.clear()

        df_od = fetch_overdue()
        if df_od.empty:
            st.success("No overdue loans — all clear! ✅")
        else:
            st.error(f"{len(df_od)} overdue loan(s) found.")
            df_od["due_date"] = pd.to_datetime(df_od["due_date"]).dt.date
            today = date.today()
            df_od["Days Overdue"] = df_od["due_date"].apply(
                lambda d: max(0, (today - d).days)
            )
            df_od["Fine (₹)"] = df_od["Days Overdue"] * 5
            st.dataframe(
                df_od[["isbn", "coustomer_id", "issue_date", "due_date",
                        "Days Overdue", "Fine (₹)"]],
                use_container_width=True
            )
            st.caption(f"Total fines outstanding: ₹{df_od['Fine (₹)'].sum():.0f}")

# ══════════════════════════════════════════════
# COL 3 — Customers & Quick Stats
# ══════════════════════════════════════════════
with col3:
    st.subheader("👤 Customers")

    # ── Register ──
    with st.expander("➕ Register Customer", expanded=False):
        with st.form("reg_form", clear_on_submit=True):
            r_id    = st.text_input("Customer ID",   placeholder="e.g. 1001")
            r_name  = st.text_input("Full Name",     placeholder="Jane Doe")
            r_email = st.text_input("Email",         placeholder="jane@example.com")
            r_phone = st.text_input("Phone Number",  placeholder="9876543210")

            if st.form_submit_button("REGISTER"):
                if not r_id or not r_name:
                    st.warning("ID and Name are required.")
                else:
                    try:
                        payload = {
                            "coustomer_id":  int(r_id),
                            "name":          r_name,
                            "email_id":      r_email or "N/A",
                            "mobile_number": int(r_phone) if r_phone.isdigit() else 0,
                        }
                        resp, err = api("post", "/customers/", json=payload)
                        if err:
                            st.error(err)
                        elif resp.status_code == 201:
                            st.success(f"✅ {r_name} registered!")
                        else:
                            show_error(resp, "Could not register.")
                    except ValueError:
                        st.error("Customer ID must be an integer.")

    # ── Lookup ──
    with st.expander("🔎 Lookup Customer", expanded=False):
        lk_id = st.text_input("Customer ID", key="lk_id", placeholder="e.g. 1001")
        if st.button("SEARCH", key="btn_lookup_cust"):
            if not lk_id:
                st.warning("Enter a Customer ID.")
            else:
                resp, err = api("get", f"/customers/{lk_id.strip()}")
                if err:
                    st.error(err)
                elif resp.status_code == 200:
                    c = resp.json()
                    st.markdown(f"""
                    **{c['name']}**  
                    📧 {c['email_id']}  
                    📞 {c['mobile_number']}  
                    🪪 ID: `{c['coustomer_id']}`
                    """)
                else:
                    show_error(resp, "Customer not found.")

    # ── Delete ──
    with st.expander("🗑️ Delete Customer", expanded=False):
        with st.form("del_form", clear_on_submit=True):
            d_id = st.text_input("Customer ID", placeholder="e.g. 1001")
            if st.form_submit_button("DELETE"):
                if not d_id.strip():
                    st.warning("Enter a Customer ID.")
                else:
                    try:
                        resp, err = api("delete", f"/customers/{int(d_id)}")
                        if err:
                            st.error(err)
                        elif resp.status_code == 200:
                            st.success("Customer deleted.")
                        else:
                            show_error(resp, "Could not delete customer.")
                    except ValueError:
                        st.error("Customer ID must be an integer.")

    st.divider()

    # ── Quick Stats ──
    st.subheader("📈 Stats")
    df_books = fetch_all_books()
    if not df_books.empty:
        total     = len(df_books)
        available = int(df_books["available"].sum())
        on_loan   = total - available

        st.markdown(f"""
        <div class="metric-box">
            <div class="label">Total Books</div>
            <div class="value">{total}</div>
        </div>
        <div class="metric-box">
            <div class="label">Available</div>
            <div class="value" style="color:#4caf82">{available}</div>
        </div>
        <div class="metric-box">
            <div class="label">On Loan</div>
            <div class="value" style="color:#cf8090">{on_loan}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No books in database yet.")

    st.divider()

    if st.button("📊 OPEN FULL DATABASE", key="open_db"):
        st.session_state.view_db = True
        st.rerun()
