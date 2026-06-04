import requests
from datetime import datetime 
from fastapi import Request
from fastapi.templating import Jinja2Templates

def base_context(request: Request, **kwargs) -> dict:
    context = {
        "request":       request,         
        "session":       request.session,   
        "book_data":     None,
        "searched_isbn": None,
        "search_error":  None,
        "error":         None,
        "success":       None,
        "total":         0,
        "available":     0,
        "on_loan":       0,
        "overdue":       0,
        "table":         None,  
    }
    context.update(kwargs)
    return context

def success_response(templates: Jinja2Templates, request: Request,
                     message: str, **kwargs):
    """Returns a template response with a success toast message."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=base_context(request, success=message, **kwargs)
    )
 
def error_response(templates: Jinja2Templates, request: Request,
                   message: str, **kwargs):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=base_context(request, error=message, **kwargs)  
    )
    
def api(FASTAPI_BASE_URL: str, method: str, path: str, **kwargs): 
    try:
        resp = getattr(requests, method)(f"{FASTAPI_BASE_URL}{path}", timeout=8, **kwargs)
        return resp, None
    except requests.exceptions.ConnectionError:
        return None, "🚨 Cannot reach the FastAPI server. Is it running?"
    except Exception as e:
        return None, str(e)

def extract_error_detail(response, fallback="An unknown error occurred.") -> str: 
    try:
        return response.json().get("detail", fallback)
    except Exception:
        return fallback

def calculate_fine(date_due_str: str, book_price: float) -> float:
    """
    Calculates the fine based on tiered brackets:
    - Month 1 (Days 1-30): 2 per day
    - Months 2-3 (Days 31-90): 10 per day
    - Months 4-9 (Days 91-270): 30 per day
    - Months 10-12 (Days 271-360): 50 per day
    - Beyond 1 Year (>360 days): Instantly hits the max 3x book price cap
    
    The fine is strictly capped at 3x the book price at any stage.
    """ 
    max_fine_cap = book_price * 3
 
    due_date = datetime.strptime(date_due_str, "%Y-%m-%d").date()
    today = datetime.today().date()
    
    if today <= due_date:
        return 0.0
        
    overdue_days = (today - due_date).days 
    
    if overdue_days > 360:
        return max_fine_cap

    fine = 0.0

    # Bracket 1: Days 1 to 30 (Rate: 2)
    if overdue_days > 0:
        days_in_bracket = min(overdue_days, 30)
        fine += days_in_bracket * 2
        overdue_days -= days_in_bracket
 
    if overdue_days > 0:
        days_in_bracket = min(overdue_days, 60) # 90 - 30 = 60 days max here
        fine += days_in_bracket * 10
        overdue_days -= days_in_bracket

    # Bracket 3: Days 91 to 270 (Rate: 30)
    if overdue_days > 0:
        days_in_bracket = min(overdue_days, 180) # 270 - 90 = 180 days max here
        fine += days_in_bracket * 30
        overdue_days -= days_in_bracket

    # Bracket 4: Days 271 to 360 (Rate: 50)
    if overdue_days > 0:
        days_in_bracket = min(overdue_days, 90) # 360 - 270 = 90 days max here
        fine += days_in_bracket * 50

    # Final safety check: ensure the accumulated fine doesn't exceed 3x book price
    return min(fine, max_fine_cap)

def is_adult(date_of_birth_str: str) -> bool: 
    try: 
        dob = datetime.strptime(date_of_birth_str, "%Y-%m-%d").date()
        today = datetime.today().date()
         
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        
        return age >= 18
    except ValueError: 
        return False
    
def is_valid_isbn(isbn: str) -> bool:
    """Validates ISBN-10 or ISBN-13 format."""
    clean = isbn.replace("-", "").replace(" ", "")

    if len(clean) == 10: 
        if not clean[:9].isdigit() or (clean[9] not in "0123456789X"):
            return False
        total = sum((10 - i) * (10 if c == 'X' else int(c))
                    for i, c in enumerate(clean))
        return total % 11 == 0

    elif len(clean) == 13: 
        if not clean.isdigit():
            return False
        total = sum(int(c) * (1 if i % 2 == 0 else 3)
                    for i, c in enumerate(clean))
        return total % 10 == 0

    return False