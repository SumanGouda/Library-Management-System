from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import requests
import json
import os
import sqlite3
from datetime import date, timedelta

# --- Configuration & Paths ---
app = FastAPI()
DB_FILE_PATH = "library.db"
GOOGLE_BOOKS_API_URL = "https://www.googleapis.com/books/v1/volumes"

# --- Pydantic Models ---
class Book(BaseModel):
    title: str
    author: str
    pages: int
    available: bool = True
    isbn: str
    genre: str

class LoanRecord(BaseModel):
    isbn: str
    coustomer_id: int
    issue_date: date = Field(default_factory=date.today)
    due_date: date = Field(
        default_factory=lambda: date.today() + timedelta(days=30)
    )
    returned: bool = False

class ReturnRequest(BaseModel):
    isbn: str
    coustomer_id: int

class RegisterCostomer(BaseModel):
    coustomer_id: int
    name: str
    email_id: str
    mobile_number: int

# --- Database Setup ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Create all tables if they don't exist."""
    conn = get_db_connection()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS customers (
            coustomer_id   INTEGER PRIMARY KEY,
            name           TEXT    NOT NULL,
            email_id       TEXT    NOT NULL,
            mobile_number  INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS books (
            isbn      TEXT    PRIMARY KEY,
            title     TEXT    NOT NULL,
            author    TEXT    NOT NULL,
            pages     INTEGER NOT NULL,
            available INTEGER NOT NULL DEFAULT 1,
            genre     TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS loans (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            isbn         TEXT    NOT NULL,
            coustomer_id INTEGER NOT NULL,
            issue_date   TEXT    NOT NULL,
            due_date     TEXT    NOT NULL,
            returned     INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (isbn)         REFERENCES books(isbn),
            FOREIGN KEY (coustomer_id) REFERENCES customers(coustomer_id)
        );
    ''')
    conn.commit()
    conn.close()

# Initialise DB on startup
init_db()

# ─────────────────────────────────────────────
# CUSTOMER ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/customers/", status_code=201)
def register_user(user: RegisterCostomer):
    conn = get_db_connection()
    try:
        existing = conn.execute(
            'SELECT 1 FROM customers WHERE coustomer_id = ?',
            (user.coustomer_id,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="User ID already registered.")

        conn.execute(
            'INSERT INTO customers (coustomer_id, name, email_id, mobile_number) VALUES (?, ?, ?, ?)',
            (user.coustomer_id, user.name, user.email_id, user.mobile_number)
        )
        conn.commit()
        return user
    finally:
        conn.close()


@app.get("/customers/{customer_id}")
def get_customer(customer_id: int):
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM customers WHERE coustomer_id = ?', (customer_id,)
    ).fetchone()
    conn.close()
    if not user:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return dict(user)


@app.delete("/customers/{customer_id}")
def delete_customer(customer_id: int):
    conn = get_db_connection()
    try:
        # Check for active (unreturned) loans
        active = conn.execute(
            'SELECT COUNT(*) FROM loans WHERE coustomer_id = ? AND returned = 0',
            (customer_id,)
        ).fetchone()[0]
        if active:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete: customer has {active} book(s) still issued."
            )

        cursor = conn.execute(
            'DELETE FROM customers WHERE coustomer_id = ?', (customer_id,)
        )
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Customer not found.")
        return {"message": "Customer successfully deleted."}
    finally:
        conn.close()


# ─────────────────────────────────────────────
# BOOK ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/books/", response_model=List[Book])
def get_all_books():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    return [Book(**dict(r)) for r in rows]


@app.get("/books/{isbn}")
def get_book(isbn: str):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM books WHERE isbn = ?', (isbn,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found.")
    return dict(row)


@app.post("/books/", status_code=201)
def add_book(book: Book):
    conn = get_db_connection()
    try:
        existing = conn.execute(
            'SELECT 1 FROM books WHERE isbn = ?', (book.isbn,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="ISBN already exists.")

        conn.execute(
            'INSERT INTO books (isbn, title, author, pages, available, genre) VALUES (?, ?, ?, ?, ?, ?)',
            (book.isbn, book.title, book.author, book.pages, int(book.available), book.genre)
        )
        conn.commit()
        return book
    finally:
        conn.close()


@app.delete("/books/{isbn}")
def delete_book(isbn: str):
    conn = get_db_connection()
    try:
        active = conn.execute(
            'SELECT COUNT(*) FROM loans WHERE isbn = ? AND returned = 0', (isbn,)
        ).fetchone()[0]
        if active:
            raise HTTPException(status_code=400, detail="Cannot delete: book is currently on loan.")

        cursor = conn.execute('DELETE FROM books WHERE isbn = ?', (isbn,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Book not found.")
        return {"message": "Book deleted successfully."}
    finally:
        conn.close()


@app.get("/search-isbn/{isbn}")
def lookup_book(isbn: str):
    clean_isbn = isbn.strip().replace("-", "").replace(" ", "")

    # If already in our DB, just return it
    conn = get_db_connection()
    row = conn.execute('SELECT 1 FROM books WHERE isbn = ?', (clean_isbn,)).fetchone()
    conn.close()
    if row:
        raise HTTPException(status_code=400, detail="Book already in local database.")

    # Fetch from Google Books
    try:
        response = requests.get(
            f"{GOOGLE_BOOKS_API_URL}?q=isbn:{clean_isbn}", timeout=5
        )
        response.raise_for_status()
        data = response.json()
        if data.get("totalItems", 0) == 0:
            raise HTTPException(status_code=404, detail="Not found in Google Books API.")

        vol = data["items"][0]["volumeInfo"]
        return {
            "isbn": clean_isbn,
            "title": vol.get("title", "Unknown"),
            "author": ", ".join(vol.get("authors", ["Unknown"])),
            "pages": vol.get("pageCount", 0),
            "genre": vol.get("categories", ["General"])[0],
            "available": True
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ─────────────────────────────────────────────
# LOAN ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/loans/", status_code=201)
def issue_book(loan: LoanRecord):
    conn = get_db_connection()
    try:
        # 1. Verify customer exists
        user = conn.execute(
            'SELECT 1 FROM customers WHERE coustomer_id = ?', (loan.coustomer_id,)
        ).fetchone()
        if not user:
            raise HTTPException(status_code=403, detail="Customer not registered.")

        # 2. Verify book exists and is available
        book_row = conn.execute(
            'SELECT available FROM books WHERE isbn = ?', (loan.isbn,)
        ).fetchone()
        if not book_row:
            raise HTTPException(status_code=404, detail="Book not found.")
        if not book_row["available"]:
            raise HTTPException(status_code=400, detail="Book is currently unavailable.")

        # 3. Insert loan record
        conn.execute(
            '''INSERT INTO loans (isbn, coustomer_id, issue_date, due_date, returned)
               VALUES (?, ?, ?, ?, 0)''',
            (loan.isbn, loan.coustomer_id,
             loan.issue_date.isoformat(), loan.due_date.isoformat())
        )

        # 4. Mark book as unavailable
        conn.execute('UPDATE books SET available = 0 WHERE isbn = ?', (loan.isbn,))
        conn.commit()
        return loan
    finally:
        conn.close()


@app.post("/loans/return/")
def return_book(req: ReturnRequest):
    conn = get_db_connection()
    try:
        # Find most recent active loan for this book + customer
        loan_row = conn.execute(
            '''SELECT id FROM loans
               WHERE isbn = ? AND coustomer_id = ? AND returned = 0
               ORDER BY id DESC LIMIT 1''',
            (req.isbn, req.coustomer_id)
        ).fetchone()
        if not loan_row:
            raise HTTPException(status_code=404, detail="No active loan found.")

        # Mark loan as returned
        conn.execute('UPDATE loans SET returned = 1 WHERE id = ?', (loan_row["id"],))

        # Mark book as available again
        conn.execute('UPDATE books SET available = 1 WHERE isbn = ?', (req.isbn,))
        conn.commit()

        # Return updated book info
        book = conn.execute('SELECT * FROM books WHERE isbn = ?', (req.isbn,)).fetchone()
        return dict(book)
    finally:
        conn.close()


@app.get("/loans/customer/{coustomer_id}")
def get_customer_history(coustomer_id: int):
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT * FROM loans WHERE coustomer_id = ?', (coustomer_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/loans/overdue/")
def get_overdue_loans():
    """Return all loans that are past their due date and not yet returned."""
    today = date.today().isoformat()
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT * FROM loans WHERE due_date < ? AND returned = 0', (today,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
