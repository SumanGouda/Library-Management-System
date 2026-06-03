import requests
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash 


# ── Blueprint setup ──
# All routes here are registered under the main Flask app in app.py
books_bp = Blueprint("books", __name__)

FASTAPI_BASE_URL = "http://127.0.0.1:8000"


# ─────────────────────────────────────────────
# HELPER — call FastAPI
# ─────────────────────────────────────────────
def api(method: str, path: str, **kwargs):
    """Thin wrapper around requests. Returns (response | None, error | None)."""
    try:
        resp = getattr(requests, method)(
            f"{FASTAPI_BASE_URL}{path}", timeout=8, **kwargs
        )
        return resp, None
    except requests.exceptions.ConnectionError:
        return None, "Cannot reach the FastAPI server. Is it running?"
    except Exception as e:
        return None, str(e)


def _get_stats():
    """Fetch summary numbers shown in the 4 stat cards."""
    stats = {"total": 0, "available": 0, "on_loan": 0, "overdue": 0}

    resp, err = api("get", "/books/")
    if resp and resp.ok:
        books = resp.json()
        stats["total"]     = len(books)
        stats["available"] = sum(1 for b in books if b.get("available"))
        stats["on_loan"]   = stats["total"] - stats["available"]

    resp, err = api("get", "/loans/overdue/")
    if resp and resp.ok:
        stats["overdue"] = len(resp.json())

    return stats


def _get_overdue():
    """Fetch overdue loans with days_overdue and fine computed."""
    resp, err = api("get", "/loans/overdue/")
    if not resp or not resp.ok:
        return []

    today = date.today()
    result = []
    for r in resp.json():
        due        = date.fromisoformat(r["due_date"])
        days_over  = max(0, (today - due).days)
        r["days_overdue"] = days_over
        r["fine"]         = days_over * 5
        result.append(r)
    return result


# ─────────────────────────────────────────────
# DASHBOARD — main page
# ─────────────────────────────────────────────
@books_bp.route("/")
def dashboard():
    return render_template(
        "index.html",
        stats      = _get_stats(),
        overdue    = _get_overdue(),
        lookup     = None,
        customer   = None,
        history    = None,
        total_fine = 0,
        active_tab = "loan",
    )


# ─────────────────────────────────────────────
# BOOKS
# ─────────────────────────────────────────────
@books_bp.route("/books/lookup", methods=["POST"])
def book_lookup():
    isbn = request.form.get("isbn", "").strip().replace("-", "").replace(" ", "")

    if not isbn:
        flash("Enter an ISBN first.", "warning")
        return redirect(url_for("books.dashboard"))

    resp, err = api("get", f"/search-isbn/{isbn}")

    if err:
        flash(err, "danger")
        return redirect(url_for("books.dashboard"))

    if resp.ok:
        lookup = resp.json()   # dict with title, author, pages, genre, isbn
        return render_template(
            "index.html",
            stats      = _get_stats(),
            overdue    = _get_overdue(),
            lookup     = lookup,
            customer   = None,
            history    = None,
            total_fine = 0,
            active_tab = "loan",
        )

    flash("Could not fetch book details.", "danger")
    return redirect(url_for("books.dashboard"))


@books_bp.route("/books/save", methods=["POST"])
def book_save():
    payload = {
        "title":     request.form.get("title", ""),
        "author":    request.form.get("author", ""),
        "pages":     int(request.form.get("pages", 1)),
        "genre":     request.form.get("genre", "General"),
        "isbn":      request.form.get("isbn", ""),
        "available": True,
    }

    resp, err = api("post", "/books/", json=payload)

    if err:
        flash(err, "danger")
    elif resp.status_code == 201:
        flash(f"'{payload['title']}' saved successfully!", "success")
    else:
        flash("Failed to save book.", "danger")

    return redirect(url_for("books.dashboard"))


@books_bp.route("/books/remove", methods=["POST"])
def book_remove():
    isbn = request.form.get("isbn", "").strip().replace("-", "").replace(" ", "")

    if not isbn:
        flash("Enter an ISBN first.", "warning")
        return redirect(url_for("books.dashboard"))

    resp, err = api("delete", f"/books/{isbn}")

    if err:
        flash(err, "danger")
    elif resp.ok:
        flash(f"Book {isbn} removed.", "success")
    else:
        flash("Could not remove book.", "danger")

    return redirect(url_for("books.dashboard"))


@books_bp.route("/books/all")
def books_all():
    resp, err = api("get", "/books/")
    books = resp.json() if resp and resp.ok else []
    return render_template(
        "index.html",
        stats      = _get_stats(),
        overdue    = _get_overdue(),
        lookup     = None,
        customer   = None,
        history    = None,
        total_fine = 0,
        active_tab = "loan",
        all_books  = books,
    )


# ─────────────────────────────────────────────
# LOANS
# ─────────────────────────────────────────────
@books_bp.route("/loans/issue", methods=["POST"])
def loan_issue():
    isbn = request.form.get("isbn", "").strip().replace("-", "").replace(" ", "")
    cid  = request.form.get("customer_id", "").strip()

    if not isbn or not cid:
        flash("Enter both Customer ID and ISBN.", "warning")
        return redirect(url_for("books.dashboard"))

    payload = {
        "isbn":         isbn,
        "coustomer_id": int(cid),
        "issue_date":   date.today().isoformat(),
    }

    resp, err = api("post", "/loans/", json=payload)

    if err:
        flash(err, "danger")
    elif resp.status_code == 201:
        flash(f"Book issued to Customer {cid}.", "success")
    else:
        flash("Failed to issue book.", "danger")

    return redirect(url_for("books.dashboard"))


@books_bp.route("/loans/return", methods=["POST"])
def loan_return():
    isbn = request.form.get("isbn", "").strip().replace("-", "").replace(" ", "")
    cid  = request.form.get("customer_id", "").strip()

    if not isbn or not cid:
        flash("Enter both Customer ID and ISBN.", "warning")
        return redirect(url_for("books.dashboard"))

    payload = {
        "isbn":         isbn,
        "coustomer_id": int(cid),
    }

    resp, err = api("post", "/loans/return/", json=payload)

    if err:
        flash(err, "danger")
    elif resp.ok:
        flash("Book returned successfully.", "success")
    else:
        flash("Failed to return book.", "danger")

    return redirect(url_for("books.dashboard"))


@books_bp.route("/loans/history", methods=["POST"])
def loan_history():
    cid = request.form.get("customer_id", "").strip()

    if not cid:
        flash("Enter a Customer ID.", "warning")
        return redirect(url_for("books.dashboard"))

    resp, err = api("get", f"/loans/customer/{cid}")

    history    = []
    total_fine = 0

    if err:
        flash(err, "danger")
    elif resp.ok:
        today = date.today()
        for r in resp.json():
            due          = date.fromisoformat(r["due_date"])
            diff         = (today - due).days
            fine         = 0 if r["returned"] else max(0, diff * 5)
            days_overdue = max(0, diff) if not r["returned"] else 0
            days_left    = max(0, -diff) if not r["returned"] else 0
            total_fine  += fine
            history.append({**r, "fine": fine,
                            "days_overdue": days_overdue,
                            "days_left": days_left})
    else:
        flash("Could not fetch history.", "danger")

    return render_template(
        "index.html",
        stats       = _get_stats(),
        overdue     = _get_overdue(),
        lookup      = None,
        customer    = None,
        history     = history,
        history_cid = cid,
        total_fine  = total_fine,
        active_tab  = "history",
    )


@books_bp.route("/loans/overdue")
def loan_overdue():
    return render_template(
        "index.html",
        stats      = _get_stats(),
        overdue    = _get_overdue(),
        lookup     = None,
        customer   = None,
        history    = None,
        total_fine = 0,
        active_tab = "overdue",
    )


# ─────────────────────────────────────────────
# CUSTOMERS
# ─────────────────────────────────────────────
@books_bp.route("/customers/register", methods=["POST"])
def customer_register():
    cid   = request.form.get("customer_id", "").strip()
    name  = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()

    if not cid or not name:
        flash("ID and Name are required.", "warning")
        return redirect(url_for("books.dashboard"))

    payload = {
        "coustomer_id":  int(cid),
        "name":          name,
        "email_id":      email or "N/A",
        "mobile_number": int(phone) if phone.isdigit() else 0,
    }

    resp, err = api("post", "/customers/", json=payload)

    if err:
        flash(err, "danger")
    elif resp.status_code == 201:
        flash(f"{name} registered successfully!", "success")
    else:
        flash("Could not register customer.", "danger")

    return redirect(url_for("books.dashboard"))


@books_bp.route("/customers/lookup", methods=["POST"])
def customer_lookup():
    cid = request.form.get("customer_id", "").strip()

    if not cid:
        flash("Enter a Customer ID.", "warning")
        return redirect(url_for("books.dashboard"))

    resp, err = api("get", f"/customers/{cid}")

    customer = None
    if err:
        flash(err, "danger")
    elif resp.ok:
        customer = resp.json()
    else:
        flash("Customer not found.", "danger")

    return render_template(
        "index.html",
        stats      = _get_stats(),
        overdue    = _get_overdue(),
        lookup     = None,
        customer   = customer,
        history    = None,
        total_fine = 0,
        active_tab = "loan",
    )


@books_bp.route("/customers/delete", methods=["POST"])
def customer_delete():
    cid = request.form.get("customer_id", "").strip()

    if not cid:
        flash("Enter a Customer ID.", "warning")
        return redirect(url_for("books.dashboard"))

    resp, err = api("delete", f"/customers/{int(cid)}")

    if err:
        flash(err, "danger")
    elif resp.ok:
        flash(f"Customer {cid} deleted.", "success")
    else:
        flash("Could not delete customer.", "danger")

    return redirect(url_for("books.dashboard"))
