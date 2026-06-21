# Library Management System

A production-ready, highly secure web application designed specifically for desktop librarian dashboards. Built with a minimal Dark Cyan theme using FastAPI, SQLite, and Google OAuth 2.0.

## 🚀 Features

- **Modular Backend:** API endpoints are separated into clean, decoupled router files.
- **Librarian Whitelist Gatekeeper:** Custom authentication loop that restricts login access to authorized emails specified in the local database.
- **Google OAuth 2.0:** Secure, frameworkless single-sign-on implementation.
- **Google Books API Integration:** Dynamic metadata search that parses volatile JSON payloads into structured SQL records.
- **Vibe Coded UI:** A custom-designed CSS administrative dashboard centered around a layout using *Syne* and *DM Mono* typography.

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone [https://github.com/SumanGouda/Library-Management-System.git](https://github.com/SumanGouda/Library-Management-System.git)
cd Library-Management-System
```

2. Configure Environment Variables
Create a .env file in the root directory (this file is ignored by git via .gitignore). Add your secret parameters:
GOOGLE_CLIENT_ID="your-google-client-id"
GOOGLE_CLIENT_SECRET="your-google-client-secret"
SESSION_SECRET_KEY="your-random-secure-session-string"

3. Initialize the Relational Database
Create a new SQLite database file named library.db inside the database/ directory. Structure your tables to include:

- auth_allowed_librarians
- books
- customers
- loans

4. Seed the Whitelist Admin Account
Because access control is locked down natively by email verification, you must manually execute an initial SQL entry to whitelist your account before signing in:

```sql
INSERT INTO auth_allowed_librarians (email) VALUES ('your.email@gmail.com');
```
5. Install Dependencies & Run
```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

# 📄 Documentation & Schema Details
For a deeper dive into the specific relational database tables, structural keys, and full architecture descriptions, visit the core project documentation page:
👉 DeepWiki Database Schema : https://deepwiki.com/SumanGouda/Library-Management-System