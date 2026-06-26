from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from services.otp_services import generate_otp, send_email_otp
from utils.db_helpers import add_customer_data
from utils.helper import is_adult
from datetime import datetime, timedelta

router = APIRouter(prefix="/customers", tags=["OTP Verification"])
OTP_VALID_MINUTES = 5
otp_store = {}


@router.post("/send-otp")
async def send_otp(
    name:          str = Form(...),
    email_id:      str = Form(...),
    mobile_number: str = Form(...),
    customer_id:   str = Form(...),
    date_of_birth: str = Form(...),
):
    try:
        if not is_adult(date_of_birth):
            return JSONResponse({"status": "error", "message": "Customer must be 18 or older."})
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"Invalid date format: {e}"})

    email_otp = generate_otp()

    otp_store[customer_id] = {
        "email_otp":     email_otp,
        "name":          name,
        "email_id":      email_id,
        "mobile_number": mobile_number,
        "date_of_birth": date_of_birth,
        "expires_at":    datetime.now() + timedelta(minutes=OTP_VALID_MINUTES),
    }

    try:
        send_email_otp(email_id, email_otp)
    except Exception as e:
        if customer_id in otp_store:
            del otp_store[customer_id]
        return JSONResponse({"status": "error", "message": f"Failed to send OTP: {e}"})

    return JSONResponse({"status": "success", "message": "OTP sent successfully."})


@router.post("/verify-otp", status_code=status.HTTP_303_SEE_OTHER)
async def verify_otp_endpoint(
    customer_id: str = Form(...),
    email_otp:   str = Form(...),
):
    record = otp_store.get(customer_id)

    if not record:
        return RedirectResponse(
            url="/?error=No OTP request found. Please try registering again.",
            status_code=303
        )

    if datetime.now() > record["expires_at"]:
        del otp_store[customer_id]
        return RedirectResponse(
            url="/?error=OTP expired. Please request a new one.",
            status_code=303
        )

    if email_otp != record["email_otp"]:
        return RedirectResponse(
            url="/?error=Incorrect OTP. Please try again.",
            status_code=303
        )

    try:
        success = add_customer_data(
            customer_id=int(customer_id),
            name=record["name"],
            email_id=record["email_id"],
            mobile_number=int(record["mobile_number"]),
            date_of_birth=record["date_of_birth"]
        )
    except ValueError:
        del otp_store[customer_id]
        return RedirectResponse(
            url="/?error=Registration failed due to corrupt ID or mobile format.",
            status_code=303
        )
    except Exception as e:
        del otp_store[customer_id]
        return RedirectResponse(
            url=f"/?error=Database operational fault occurred: {e}",
            status_code=303
        )

    del otp_store[customer_id]

    if not success:
        return RedirectResponse(
            url=f"/?error=A customer with ID {customer_id} already exists.",
            status_code=303
        )

    return RedirectResponse(
        url=f"/?success={record['name']} registered successfully!",
        status_code=303
    )