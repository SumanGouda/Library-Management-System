import sqlite3
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from routes.books import router as books_router
from utils.helper import is_valid_isbn, base_context, success_response, error_response
from services.google_api import fetch_book_details_by_isbn
from utils.db_helpers import (
    fetch_all_book_data,
    fetch_available_book_data,
    fetch_active_loan_data,
    fetch_overdue_customers_detailed_report
)

templates = Jinja2Templates(directory="templates")
DB_PATH = "database/library.db"

app = FastAPI()
app.include_router(books_router)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ── get stats helper ──
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM books")
        total = int(cursor.fetchone()[0])
        cursor.execute("SELECT COALESCE(SUM(available), 0) FROM books")
        available = int(cursor.fetchone()[0])
        cursor.execute("SELECT COUNT(*) FROM loans WHERE returned = 0")
        on_loan = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM loans WHERE returned = 0 AND due_date < date('now')")
        overdue = cursor.fetchone()[0]
    except sqlite3.Error as e:
        print(f"--- DATABASE ERROR: {e} ---")
        total, available, on_loan, overdue = 0, 0, 0, 0
    finally:
        cursor.close()
        conn.close()
    return total, available, on_loan, overdue


# ── dashboard ──
@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    total, available, on_loan, overdue = get_stats()

    error   = request.query_params.get("error", None)
    success = request.query_params.get("success", None)

    if error:
        return error_response(templates, request, error,
                              total=total, available=available,
                              on_loan=on_loan, overdue=overdue)
    if success:
        return success_response(templates, request, success,
                                total=total, available=available,
                                on_loan=on_loan, overdue=overdue)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=base_context(request,
                             total=total, available=available,
                             on_loan=on_loan, overdue=overdue)
    )
 
@app.post("/books/search", response_class=HTMLResponse)
async def search_book(request: Request, search_isbn: str = Form(...)):
    total, available, on_loan, overdue = get_stats()

    # validate ISBN
    if not is_valid_isbn(search_isbn):
        return error_response(templates, request,
                              "Invalid ISBN. Please enter a valid 10 or 13 digit ISBN.",
                              total=total, available=available,
                              on_loan=on_loan, overdue=overdue,
                              searched_isbn=search_isbn)

    # hit Google API
    result = fetch_book_details_by_isbn(search_isbn)

    if result["status"] != "success":
        return error_response(templates, request,
                              result["message"],
                              total=total, available=available,
                              on_loan=on_loan, overdue=overdue,
                              searched_isbn=search_isbn)

    return success_response(templates, request,
                            "Book found!",
                            total=total, available=available,
                            on_loan=on_loan, overdue=overdue,
                            book_data=result["book_data"],
                            searched_isbn=search_isbn)

@app.get("/stats/total", response_class=HTMLResponse)
async def stats_total(request: Request):
    total, available, on_loan, overdue = get_stats()
    rows = fetch_all_book_data()
    table = {
        "title": "All Books",
        "headers": ["ISBN", "Title", "Available", "Total Copies"],
        "rows": rows
    }
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=base_context(request,
                             total=total, available=available,
                             on_loan=on_loan, overdue=overdue,
                             table=table)
    )


@app.get("/stats/available", response_class=HTMLResponse)
async def stats_available(request: Request):
    total, available, on_loan, overdue = get_stats()
    rows = fetch_available_book_data()
    table = {
        "title": "Available Books",
        "headers": ["ISBN", "Title", "Available", "Total Copies"],
        "rows": rows
    }
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=base_context(request,
                             total=total, available=available,
                             on_loan=on_loan, overdue=overdue,
                             table=table)
    )


@app.get("/stats/on-loan", response_class=HTMLResponse)
async def stats_on_loan(request: Request):
    total, available, on_loan, overdue = get_stats()
    rows = fetch_active_loan_data()
    table = {
        "title": "Active Loans",
        "headers": ["ISBN", "Customer ID", "Fine (₹)"],
        "rows": rows
    }
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=base_context(request,
                             total=total, available=available,
                             on_loan=on_loan, overdue=overdue,
                             table=table)
    )


@app.get("/stats/overdue", response_class=HTMLResponse)
async def stats_overdue(request: Request):
    total, available, on_loan, overdue = get_stats()
    rows = fetch_overdue_customers_detailed_report()
    table = {
        "title": "Overdue Customers",
        "headers": ["Customer ID", "Name", "Phone", "Email", "Books Count", "Total Fine (₹)", "Overdue ISBNs"],
        "rows": rows
    }
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=base_context(request,
                             total=total, available=available,
                             on_loan=on_loan, overdue=overdue,
                             table=table)
    )