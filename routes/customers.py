from fastapi import APIRouter, status, Form
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from utils.db_helpers import get_customer_data, add_customer_data, delete_customer_data, update_customer_data, get_customer_count
from utils.helper import is_adult

router = APIRouter(prefix="/customers", tags=["Customers"])


# ── Pydantic models (kept for API/JSON use if needed later) ──
class CustomerSchema(BaseModel):
    customer_id: int
    name: str
    email_id: str = "N/A"
    mobile_number: int = 0
    date_of_birth: str      # "YYYY-MM-DD"

class CustomerUpdateSchema(BaseModel):
    email_id: str
    mobile_number: int


# ── Register customer from HTML form ──
@router.post("/", status_code=status.HTTP_303_SEE_OTHER)
async def register_customer(
    customer_id:   int = Form(...),
    name:          str = Form(...),
    email_id:      str = Form("N/A"),
    mobile_number: int = Form(0),
    date_of_birth: str = Form(...),
):
    if not is_adult(date_of_birth):
        return RedirectResponse(
            url="/?error=Registration denied. Customer must be 18 or older.",
            status_code=303
        )

    success = add_customer_data(
        customer_id=customer_id,
        name=name,
        email_id=email_id,
        mobile_number=mobile_number,
        date_of_birth=date_of_birth
    )

    if not success:
        return RedirectResponse(
            url=f"/?error=A customer with ID {customer_id} already exists.",
            status_code=303
        )

    return RedirectResponse(
        url=f"/?success={name} registered successfully!",
        status_code=303
    )


# ── Lookup customer via GET (used by HTML form) ──
@router.get("/lookup")
async def lookup_customer(customer_id: int):
    customer = get_customer_data(customer_id)
    if not customer:
        return RedirectResponse(
            url=f"/?error=Customer {customer_id} not found.",
            status_code=303
        )
    return customer


# ── Update customer from HTML form ──
@router.post("/update", status_code=status.HTTP_303_SEE_OTHER)
async def update_customer(
    customer_id:   int = Form(...),
    email_id:      str = Form(...),
    mobile_number: int = Form(...),
):
    success = update_customer_data(
        customer_id=customer_id,
        email_id=email_id,
        mobile_number=mobile_number
    )

    if not success:
        return RedirectResponse(
            url=f"/?error=Customer {customer_id} not found.",
            status_code=303
        )

    return RedirectResponse(
        url=f"/?success=Customer {customer_id} updated successfully!",
        status_code=303
    )


# ── Delete customer from HTML form ──
@router.post("/delete", status_code=status.HTTP_303_SEE_OTHER)
async def delete_customer(customer_id: int = Form(...)):
    result = delete_customer_data(customer_id)

    if result == "not_found":
        return RedirectResponse(
            url=f"/?error=Customer {customer_id} not found.",
            status_code=303
        )

    if result == "active_loan":
        return RedirectResponse(
            url=f"/?error=Cannot delete customer {customer_id}. They have an active loan.",
            status_code=303
        )

    return RedirectResponse(
        url=f"/?success=Customer {customer_id} deleted successfully.",
        status_code=303
    )


# ── Get total customer count (API) ──
@router.get("/count")
async def total_customer_count():
    total = get_customer_count()
    return {"total_customers": total}