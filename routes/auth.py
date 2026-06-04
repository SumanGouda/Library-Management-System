import urllib.parse  
from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from utils.db_helpers import verify_librarian_email
from services.google_api import exchange_code_for_profile
import os
from dotenv import load_dotenv

load_dotenv()
 
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Secure configuration constants (Best practice: Move these to your .env file later)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI")

@router.post("/login-trigger")
async def login_trigger(request: Request, email: str = Form(...)):
    """
    Step 1: Librarian submits their email on the login card.
    We verify their identity via the database whitelist helper.
    If authorized, we redirect them cleanly to Google's sign-in server.
    """ 
    librarian = verify_librarian_email(email)
    
    if not librarian:
        # Redirect back to the dashboard or login page with an error query param
        return RedirectResponse(url="/?error=Access+denied:+This+email+is+not+a+registered+librarian.", status_code=303)

    # Build secure Google authentication query parameters
    oauth_params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "login_hint": email,         
        "prompt": "select_account"
    } 
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(oauth_params)}"
     
    return RedirectResponse(url=google_auth_url, status_code=303)


@router.get("/google-callback")
async def google_callback(request: Request, code: str = None, error: str = None):
    """
    Step 2: Google handles the password and sends the user back here with an authentication code.
    We securely exchange it for their actual email to log them in.
    """
    if error:
        return RedirectResponse(url=f"/?error=Google+Auth+Failed:+{error}", status_code=303)
        
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code from Google.")

    # Exchange the ticket code for the actual Google profile data
    result = exchange_code_for_profile(
        code=code,
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        redirect_uri=GOOGLE_REDIRECT_URI
    )
    
    if result["status"] == "error":
        return RedirectResponse(url=f"/?error={urllib.parse.quote(result['message'])}", status_code=303)
        
    google_email = result["profile"].get("email")
    
    # Double-check the email returned from Google against our whitelist table
    librarian = verify_librarian_email(google_email)
    if not librarian:
        return RedirectResponse(url="/?error=Access+denied:+Your+Google+account+is+not+authorized.", status_code=303)
        
    request.session["librarian_email"] = google_email
    
    return RedirectResponse(url="/?success=Welcome+back!+Successfully+logged+in.", status_code=303)