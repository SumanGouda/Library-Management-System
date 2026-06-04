from fastapi import APIRouter, status, Form
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from utils.db_helpers import book_issue, book_return
from utils.helper import is_valid_isbn

router = APIRouter(prefix="/loans", tags=["Loans"])


# ── Pydantic models (kept for API/JSON use if needed later) ──
class LoanSchema(BaseModel):
    isbn: str
    customer_id: int
    issue_date: str     # "YYYY-MM-DD"
    due_date: str       # "YYYY-MM-DD"
    fine_amount: float = 0.0
    returned: int = 0   # 0 = active loan, 1 = book returned

class ReturnBookRequest(BaseModel):
    customer_id: int
    isbn: str


# ── Issue book from HTML form ──
@router.post("/issue", status_code=status.HTTP_303_SEE_OTHER)
async def issue_book_endpoint(
    isbn:          str = Form(...),
    customer_id:   int = Form(...),
    date_borrowed: str = Form(...),
    date_due:      str = Form(...),
):
    # validate ISBN 
    if not is_valid_isbn(isbn):
        return RedirectResponse(
            url="/?error=Invalid ISBN. Please enter a valid 10 or 13 digit ISBN.",
            status_code=303
        )
    # hit the DB 
    result = book_issue(
        isbn=isbn,
        customer_id=customer_id,
        date_borrowed=date_borrowed,
        date_due=date_due
    )
    error_messages = {
        "not_found":      f"Customer ID {customer_id} does not exist.",
        "already_issued": f"Customer {customer_id} already has book {isbn} issued.",
        "fine_pending":   f"Customer {customer_id} has an outstanding fine. Please clear dues first.",
        "book_not_found": f"Book {isbn} does not exist in the inventory.",
        "out_of_stock":   f"Book {isbn} has no copies currently available.",
        "database_error": "An unexpected error occurred while saving the loan.",
    }
    if result in error_messages:
        return RedirectResponse(
            url=f"/?error={error_messages[result]}",
            status_code=303
        )

    return RedirectResponse(
        url=f"/?success=Book {isbn} successfully issued to Customer {customer_id}!",
        status_code=303
    )


# ── Return book from HTML form ──
@router.post("/return", status_code=status.HTTP_303_SEE_OTHER)
async def return_book_endpoint(
    customer_id: int = Form(...),
    isbn:        str = Form(...),
):  
    # Validate ISBN
    if not is_valid_isbn(isbn):
        return RedirectResponse(
            url="/?error=Invalid ISBN. Please enter a valid 10 or 13 digit ISBN.",
            status_code=303
        )
    # Hit the DB
    result = book_return(customer_id, isbn)

    if result["status"] == "error":
        return RedirectResponse(
            url=f"/?error={result['message']}",
            status_code=303
        )

    if result["status"] == "fine_pending":
        return RedirectResponse(
            url=f"/?error=Cannot return book. Outstanding fine of Rs.{result['fine_amount']}. Please clear dues first.",
            status_code=303
        )

    return RedirectResponse(
        url=f"/?success={result['message']}",
        status_code=303
    )