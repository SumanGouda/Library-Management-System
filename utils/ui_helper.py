import streamlit as st
import time

def show_error(response, fallback="An unknown error occurred."):
    """Displays a Streamlit error message from a response object."""
    from utils.helper import extract_error_detail   
    detail = extract_error_detail(response, fallback)
    st.error(f"Error {response.status_code}: {detail}")

def success_and_rerun(msg: str):
    """Shows a success message, clears cache, and reruns the Streamlit app."""
    st.cache_data.clear()
    st.success(msg)
    time.sleep(0.8)
    st.rerun()