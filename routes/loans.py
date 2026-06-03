from fastapi import APIRouter, status, Form
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from utils.db_helpers import book_issue, book_return

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
    isbn:        str = Form(...),
    customer_id: int = Form(...),
    date_borrowed: str = Form(...),
    date_due:    str = Form(...),
):
    result = book_issue(
        isbn=isbn,
        customer_id=customer_id,
        date_borrowed=date_borrowed,
        date_due=date_due
    )

    if result == "not_found":
        return RedirectResponse(
            url=f"/?error=Cannot issue book. Customer ID {customer_id} does not exist.",
            status_code=303
        )

    if result == "unavailable":
        return RedirectResponse(
            url=f"/?error=Cannot issue book {isbn}. No copies are currently available.",
            status_code=303
        )

    if result == "database_error":
        return RedirectResponse(
            url="/?error=An unexpected error occurred while saving the loan.",
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