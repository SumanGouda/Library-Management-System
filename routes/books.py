from fastapi import APIRouter, status, Form
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from utils.db_helpers import add_book_to_db, remove_book_from_db
from utils.helper import is_valid_isbn

router = APIRouter(prefix="/books", tags=["Books"])


# ── Pydantic model (kept for API/JSON use if needed later) ──
class AddBookRequest(BaseModel):
    isbn: str
    title: str
    author: str
    pages: int
    genre: str
    price: float = Field(..., gt=0, description="The manually entered market price of the book")
    quantity_to_add: int = Field(default=1, gt=0, description="Number of copies being added")


# ── Add or update book from HTML form ──
@router.post("/add", status_code=status.HTTP_303_SEE_OTHER)
async def add_or_update_book(
    isbn:            str   = Form(...),
    title:           str   = Form(...),
    author:          str   = Form(...),
    pages:           int   = Form(...),
    genre:           str   = Form(...),
    price:           float = Form(...),
    quantity_to_add: int   = Form(...),
):
    result = add_book_to_db(
        isbn=isbn,
        title=title,
        author=author,
        pages=pages,
        genre=genre,
        price=price,
        quantity=quantity_to_add
    )

    if result == "error":
        return RedirectResponse(
            url="/?error=Failed to save book. Please try again.",
            status_code=303
        )

    if result == "updated":
        return RedirectResponse(
            url=f"/?success=Book already exists. Added {quantity_to_add} more copies.",
            status_code=303
        )

    return RedirectResponse(
        url=f"/?success={title} saved successfully!",
        status_code=303
    )


# ── Delete book from HTML form ──
@router.post("/delete", status_code=status.HTTP_303_SEE_OTHER)
async def delete_book_form(isbn: str = Form(...)):
    if not is_valid_isbn(isbn):
        return RedirectResponse(
            url="/?error=Invalid ISBN. Please enter a valid 10 or 13 digit ISBN.",
            status_code=303
        )
    success = remove_book_from_db(isbn)

    if not success:
        return RedirectResponse(
            url=f"/?error=Cannot delete book {isbn}. It has active loans or does not exist.",
            status_code=303
        )

    return RedirectResponse(
        url=f"/?success=Book {isbn} deleted successfully.",
        status_code=303
    )