import json
import urllib.request
import os
from urllib.error import URLError
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_BOOKS_API_KEY")

def fetch_book_details_by_isbn(isbn: str) -> dict:
    """
    Queries the Google Books API using an ISBN.
    Returns a cleaned dictionary ready to match your database columns.
    """
    clean_isbn = isbn.replace("-", "").replace(" ", "")
    api_url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{clean_isbn}&key={API_KEY}"  # ← key added here

    DEFAULT_COVER_IMAGE = "../assets/default_cover.png"

    try:
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read().decode())

        if "items" not in data:
            return {"status": "not_found", "message": "No book found with this ISBN."}

        volume_info = data["items"][0]["volumeInfo"]

        title      = volume_info.get("title", "Unknown Title")
        authors    = ", ".join(volume_info.get("authors", ["Unknown Author"]))
        pages      = volume_info.get("pageCount", 0)

        categories = volume_info.get("categories", ["General"])
        genre      = categories[0] if categories else "General"

        image_links = volume_info.get("imageLinks", {})
        cover_image = image_links.get("thumbnail", DEFAULT_COVER_IMAGE).replace("http://", "https://")

        return {
            "status": "success",
            "book_data": {
                "isbn":          clean_isbn,
                "title":         title,
                "author":        authors,
                "pages":         int(pages),
                "genre":         genre,
                "cover_image_url": cover_image
            }
        }

    except URLError as e:
        print(f"Network error trying to reach Google Books API: {e}")
        return {"status": "error", "message": "Could not connect to external book service."}
    except Exception as e:
        print(f"Unexpected error parsing book data: {e}")
        return {"status": "error", "message": "An error occurred while fetching book details."}