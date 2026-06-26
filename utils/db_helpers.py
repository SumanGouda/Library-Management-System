import sqlite3  
from datetime import datetime
from utils.helper import calculate_fine

DB_PATH = "database/library.db"

def add_customer_data(customer_id: int, name: str, email_id: str, mobile_number: int, date_of_birth: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        check_query = "SELECT 1 FROM customers WHERE customer_id = ?"
        cursor.execute(check_query, (customer_id,))
        if cursor.fetchone() is not None:
            return False  
            
        # Included date_of_birth in the INSERT statement
        insert_query = """
            INSERT INTO customers (customer_id, name, email_id, mobile_number, date_of_birth) 
            VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(insert_query, (customer_id, name, email_id, mobile_number, date_of_birth))
        conn.commit()
        return True
        
    finally:
        cursor.close()
        conn.close()
        
def delete_customer_data(customer_id: int) -> str:
    """
    Attempts to delete a customer record.
    Returns:
        - "deleted" if successfully removed.
        - "active_loan" if the customer has an active loan and cannot be deleted.
        - "fine_pending" if the customer has an outstanding fine and cannot be deleted.
        - "not_found" if the customer doesn't exist.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:  
        check_query = "SELECT active_loan FROM customers WHERE customer_id = ?"
        cursor.execute(check_query, (customer_id,))
        result = cursor.fetchone()
        
        if result is None:
            return "not_found"
            
        if result[0] == 1:
            return "active_loan"
            
        fine_query = """
            SELECT COALESCE(SUM(fine_amount), 0.0) 
            FROM loans 
            WHERE customer_id = ? AND returned = 0
        """
        cursor.execute(fine_query, (customer_id,))
        total_fine = cursor.fetchone()[0]
        
        if total_fine > 0:
            print(f"Delete blocked: Customer {customer_id} owes ₹{total_fine:.2f} in outstanding fines.")
            return "fine_pending"
             
        delete_query = "DELETE FROM customers WHERE customer_id = ?"
        cursor.execute(delete_query, (customer_id,))
        conn.commit()
        return "deleted"
        
    finally:
        cursor.close()
        conn.close()
              
def get_customer_data(customer_id: int):
    conn = sqlite3.connect(DB_PATH)

    conn.row_factory = lambda cursor, row: {
        col[0]: row[idx] for idx, col in enumerate(cursor.description)
    }
    cursor = conn.cursor()

    try:
        # ── Basic customer info ──
        customer_query = "SELECT customer_id, name, email_id, mobile_number, date_of_birth FROM customers WHERE customer_id = ?"
        cursor.execute(customer_query, (customer_id,))
        customer = cursor.fetchone()

        if not customer:
            return None

        # ── Currently issued books (active, not returned) ──
        cursor.execute("""
            SELECT COUNT(*) as count FROM loans 
            WHERE customer_id = ? AND returned = 0
        """, (customer_id,))
        customer["books_currently_issued"] = cursor.fetchone()["count"]

        # ── Total books returned (lifetime) ──
        cursor.execute("""
            SELECT COUNT(*) as count FROM loans 
            WHERE customer_id = ? AND returned = 1
        """, (customer_id,))
        customer["books_returned"] = cursor.fetchone()["count"]

        # ── Currently overdue books ──
        cursor.execute("""
            SELECT COUNT(*) as count FROM loans 
            WHERE customer_id = ? AND returned = 0 AND due_date < date('now')
        """, (customer_id,))
        customer["books_overdue"] = cursor.fetchone()["count"]

        # ── Total outstanding fine ──
        cursor.execute("""
            SELECT COALESCE(SUM(fine_amount), 0.0) as total_fine 
            FROM loans 
            WHERE customer_id = ? AND returned = 0
        """, (customer_id,))
        customer["total_fine_amount"] = cursor.fetchone()["total_fine"]

        # ── Total books borrowed ever (lifetime activity) ──
        cursor.execute("""
            SELECT COUNT(*) as count FROM loans 
            WHERE customer_id = ?
        """, (customer_id,))
        customer["total_books_borrowed"] = cursor.fetchone()["count"]

        # ── Most recently issued book ──
        cursor.execute("""
            SELECT b.title, l.issue_date, l.due_date 
            FROM loans l
            JOIN books b ON l.isbn = b.isbn
            WHERE l.customer_id = ?
            ORDER BY l.issue_date DESC
            LIMIT 1
        """, (customer_id,))
        last_loan = cursor.fetchone()
        customer["last_borrowed_book"] = last_loan["title"] if last_loan else None
        customer["last_due_date"] = last_loan["due_date"] if last_loan else None

        return customer

    finally:
        cursor.close()
        conn.close()
               
def update_customer_data(customer_id: int, email_id: str, mobile_number: int) -> bool: 
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try: 
        check_query = "SELECT 1 FROM customers WHERE customer_id = ?"
        cursor.execute(check_query, (customer_id,))
        if cursor.fetchone() is None:
            return False
             
        update_query = """
            UPDATE customers 
            SET email_id = ?, mobile_number = ? 
            WHERE customer_id = ?
        """
        cursor.execute(update_query, (email_id, mobile_number, customer_id))
        conn.commit()
        return True
        
    finally:
        cursor.close()
        conn.close()
        
def get_customer_count() -> int:
    """Returns the total number of customers registered in the library."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = "SELECT COUNT(*) FROM customers"
        cursor.execute(query)
        result = cursor.fetchone()
        return result[0] if result else 0
    finally:
        cursor.close()
        conn.close()
        
def sync_active_loans_fines() -> int:
    """
    Scans all active loans, calculates the tiered fine based on today's date,
    and updates the fine_amount column in the database securely using id.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        query = """
            SELECT l.id, l.isbn, l.customer_id, l.due_date, b.price
            FROM loans l
            JOIN books b ON l.isbn = b.isbn
            WHERE l.returned = 0
        """
        cursor.execute(query)
        active_loans = cursor.fetchall()
        
        updated_count = 0
        for loan in active_loans:
            loan_id, isbn, customer_id, date_due_str, book_price = loan
            current_fine = calculate_fine(date_due_str, book_price)
            
            update_query = """
                UPDATE loans
                SET fine_amount = ?
                WHERE id = ?
            """
            cursor.execute(update_query, (current_fine, loan_id))
            updated_count += 1
            
        conn.commit()
        return updated_count

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error during daily fine sync: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()    
  
def __clear_customer_fines(customer_id: int) -> bool:
    """
    Resets the fine_amount to 0.0 for all active loans belonging to a specific customer.
    Returns True if successful, False otherwise.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        query = """
            UPDATE loans
            SET fine_amount = 0.0
            WHERE customer_id = ? AND returned = 0
        """
        cursor.execute(query, (customer_id,))
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error while clearing fines for customer {customer_id}: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def pay_fine(customer_id: int, payment_amount: float) -> dict:
    """
    Processes a fine payment for a customer:
    1. Finds the total outstanding fine balance across active loans.
    2. Validates that the payment amount doesn't exceed the total fine owed.
    3. Subtracts the payment from the outstanding fine records.
    4. Automatically invokes clear_customer_fines if the remaining balance hits 0.
    """ 
    if payment_amount <= 0:
        return {"status": "error", "message": "Payment amount must be greater than 0."}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try: 
        cursor.execute("""
            SELECT SUM(fine_amount) 
            FROM loans 
            WHERE customer_id = ? AND returned = 0
        """, (customer_id,))
        
        result = cursor.fetchone()[0]
        total_fine = result if result is not None else 0.0
 
        if total_fine == 0:
            return {"status": "error", "message": "This customer has no active fines to pay."}
        
        # Validate that the payment amount doesn't exceed the outstanding fine
        if payment_amount > total_fine:
            return {
                "status": "error", 
                "message": f"Overpayment blocked. Customer owes ₹{total_fine:.2f}, but you attempted to pay ₹{payment_amount:.2f}."
            }

        # Calculate what the fine balance will be after this transaction
        remaining_fine = total_fine - payment_amount

        if remaining_fine == 0:
            cursor.close()
            conn.close() 
            
            success = __clear_customer_fines(customer_id)
            if success:
                return {"status": "success", "message": "Fine paid in full! All customer restrictions cleared."}
            else:
                return {"status": "error", "message": "Payment calculated to 0, but failed to execute system clear."}
        
        else:
            # Partial Payment Logic: Distribute and subtract payment from active loans
            # (For simple tracking, we apply it directly to their unreturned loan rows)
            cursor.execute("""
                SELECT loan_id, fine_amount 
                FROM loans 
                WHERE customer_id = ? AND returned = 0 AND fine_amount > 0
            """, (customer_id,))
            active_fined_loans = cursor.fetchall()

            running_payment = payment_amount
            for loan_id, current_loan_fine in active_fined_loans:
                if running_payment <= 0:
                    break
                
                if running_payment >= current_loan_fine: 
                    running_payment -= current_loan_fine
                    cursor.execute("UPDATE loans SET fine_amount = 0 WHERE loan_id = ?", (loan_id,))
                else:
                    # Deduct the remaining payment portion from this loan's fine balance
                    new_loan_fine = current_loan_fine - running_payment
                    running_payment = 0
                    cursor.execute("UPDATE loans SET fine_amount = ? WHERE loan_id = ?", (new_loan_fine, loan_id))

            conn.commit()
            return {
                "status": "partial_success", 
                "message": f"Payment of ₹{payment_amount:.2f} accepted. Remaining balance: ₹{remaining_fine:.2f}."
            }

    except sqlite3.Error as e: 
        if conn:
            conn.rollback()
        print(f"Database error inside pay_fine: {e}")
        return {"status": "error", "message": "An internal database error occurred."}
    finally: 
        try:
            cursor.close()
            conn.close()
        except:
            pass

def book_issue(isbn: str, customer_id: int, date_borrowed: str, date_due: str) -> str:
    """
    Handles issuing a book to a customer.
    Returns:
        - "success" if the book is issued.
        - "not_found" if the customer doesn't exist.
        - "out_of_stock" if no copies are available on the shelf.
        - "fine_pending" if the customer has an active unpaid fine.
        - "database_error" if something goes wrong.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try: 
        # Verify customer exists
        cursor.execute("SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,))
        if cursor.fetchone() is None:
            return "not_found" 
        
        # Verify customer does not already have this book issued
        cursor.execute("""
            SELECT 1 FROM loans 
            WHERE customer_id = ? AND isbn = ? AND returned = 0
        """, (customer_id, isbn))
        if cursor.fetchone() is not None:
            print(f"Issue blocked: Customer {customer_id} already has book {isbn} issued.")
            return "already_issued"
            
        # Verify customer does not have any active fines across unreturned loans
        cursor.execute("""
            SELECT SUM(fine_amount) 
            FROM loans 
            WHERE customer_id = ? AND returned = 0
        """, (customer_id,))
        fine_result = cursor.fetchone()[0]
        total_fine = fine_result if fine_result is not None else 0.0
        
        if total_fine > 0:
            print(f"Issue blocked: Customer {customer_id} has an active fine of ₹{total_fine:.2f}.")
            return "fine_pending"

        # Verify the book is actually in stock on the shelf
        cursor.execute("SELECT available FROM books WHERE isbn = ?", (isbn,))
        book_result = cursor.fetchone()
        
        if not book_result:
            return "book_not_found"  
            
        current_available = book_result[0]
        if current_available <= 0:
            print(f"Issue blocked: Book {isbn} is currently out of stock.")
            return "out_of_stock"
            
        # Process the loan transaction
        loan_query = """
            INSERT INTO loans (isbn, customer_id, issue_date, due_date, returned, fine_amount)
            VALUES (?, ?, ?, ?, 0, 0.0)
        """
        cursor.execute(loan_query, (isbn, customer_id, date_borrowed, date_due))
         
        # Mark customer as having an active loan
        customer_update_query = """
            UPDATE customers
            SET active_loan = 1
            WHERE customer_id = ?
        """
        cursor.execute(customer_update_query, (customer_id,))
         
        # Reduce shelf counter by 1
        book_update_query = """
            UPDATE books
            SET available = available - 1
            WHERE isbn = ?
        """
        cursor.execute(book_update_query, (isbn,))
         
        conn.commit()
        return "success"
        
    except sqlite3.Error as e:
        conn.rollback()   
        print(f"Database error during book issue: {e}")
        return "database_error"
        
    finally:
        cursor.close()
        conn.close()
            
def book_return(customer_id: int, isbn: str) -> dict:
    """
    Handles the step-by-step logic for returning a book:
    1. Checks if the customer exists.
    2. Checks if the customer actually has this book issued (active loan).
    3. Checks if there is an unpaid fine on this specific loan.
    4. Marks the book as returned and updates availability.
    5. Resets active_loan flag if no more active loans remain.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try: 
        cursor.execute("SELECT name FROM customers WHERE customer_id = ?", (customer_id,))
        if not cursor.fetchone():
            return {"status": "error", "message": "Customer does not exist."}
 
        cursor.execute("""
            SELECT fine_amount FROM loans
            WHERE customer_id = ? AND isbn = ? AND returned = 0
            LIMIT 1
        """, (customer_id, isbn))
        loan = cursor.fetchone()

        if not loan:
            return {"status": "error", "message": "This book is not currently issued to this customer."}
 
        fine_amount = loan[0]
        if fine_amount > 0:
            return {
                "status":      "fine_pending",
                "message":     f"Cannot return book. Outstanding fine of ₹{fine_amount:.2f}.",
                "fine_amount": fine_amount
            }
        cursor.execute("""
            UPDATE loans
            SET returned = 1
            WHERE customer_id = ? AND isbn = ? AND returned = 0
        """, (customer_id, isbn))

        #  increment book availability 
        cursor.execute("""
            UPDATE books
            SET available = available + 1
            WHERE isbn = ?
        """, (isbn,))

        # reset active_loan if no more active loans
        cursor.execute("""
            SELECT COUNT(*) FROM loans
            WHERE customer_id = ? AND returned = 0
        """, (customer_id,))
        remaining_loans = cursor.fetchone()[0]

        if remaining_loans == 0:
            cursor.execute("""
                UPDATE customers
                SET active_loan = 0
                WHERE customer_id = ?
            """, (customer_id,))

        conn.commit()
        return {"status": "success", "message": "Book has been successfully returned!"}

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error during book return: {e}")
        return {"status": "error", "message": "An internal database error occurred."}
    finally:
        cursor.close()
        conn.close()
        
def add_book_to_db(isbn: str, title: str, author: str, pages: int, genre: str, price: float, quantity: int = 1) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT quantity, available FROM books WHERE isbn = ?", (isbn,))
        existing_book = cursor.fetchone()

        if existing_book:
            current_qty, current_avail = existing_book 
             
            new_qty = current_qty + quantity
            new_avail = current_avail + quantity
             
            cursor.execute("""
                UPDATE books
                SET quantity = ?, available = ?, price = ?
                WHERE isbn = ?
            """, (new_qty, new_avail, price, isbn))
            conn.commit()
            return "updated"

        else:
            # For a completely brand new book title, both total stock 
            # and shelf availability start at the exact quantity added.
            cursor.execute("""
                INSERT INTO books (isbn, title, author, pages, available, genre, price, quantity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (isbn, title, author, pages, quantity, genre, price, quantity))
            conn.commit()
            return "inserted"

    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error inside add_book_to_db: {e}")
        return "error"
    finally:
        cursor.close()
        conn.close()
               
def remove_book_from_db(isbn: str, qty_to_remove: int = 1) -> bool:
    """
    Reduces the stock of a book by qty_to_remove. 
    Only completely deletes the master catalog row from the books table 
    if total quantity hits 0 AND there are no active, unreturned loans.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try: 
        # Check for active loans
        cursor.execute(
            "SELECT COUNT(*) FROM loans WHERE isbn = ? AND returned = 0", 
            (isbn,)
        )
        active_loans = cursor.fetchone()[0]
        
        # Get current inventory numbers
        cursor.execute("SELECT quantity, available FROM books WHERE isbn = ?", (isbn,))
        book_stock = cursor.fetchone()
        
        if not book_stock:
            print(f"Book {isbn} not found in inventory.")
            return False
            
        current_qty, current_avail = book_stock
        
        # Safety Gate: You can't remove more books than are physically sitting on your shelf
        if qty_to_remove > current_avail:
            print(f"Cannot remove {qty_to_remove} copies. Only {current_avail} copies are physically available on shelf.")
            return False

        new_qty = current_qty - qty_to_remove
        new_avail = current_avail - qty_to_remove

        # 3. Decision: Do we completely erase the title row or just lower the stock numbers?
        if new_qty == 0:
            if active_loans > 0:
                print(f"Cannot fully purge book {isbn}: {active_loans} copy/copies are still out on active loans.")
                return False
                
            # Safe to completely delete catalog row if you own 0 copies and 0 are checked out
            cursor.execute("DELETE FROM books WHERE isbn = ?", (isbn,))
        else:
            # Just lower the stock count counters
            cursor.execute("""
                UPDATE books 
                SET quantity = ?, available = ? 
                WHERE isbn = ?
            """, (new_qty, new_avail, isbn))
            
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Database error while removing book {isbn}: {e}")
        return False
    finally:
        cursor.close()
        conn.close()
        
def fetch_all_book_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT isbn, title, available, quantity FROM books")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
        
def fetch_available_book_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT isbn, title, available, quantity 
            FROM books 
            WHERE available > 0
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
        
def fetch_active_loan_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Pulls targeted columns for active unreturned loans
        cursor.execute("""
            SELECT isbn, customer_id, fine_amount 
            FROM loans 
            WHERE returned != 1
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()
        
def fetch_overdue_customers_detailed_report():
    """
    Fetches a list of all overdue customers, including a dynamically 
    generated string of all ISBNs they currently have overdue.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        query = """
            SELECT 
                c.customer_id,
                c.name,
                c.mobile_number,
                c.email_id,
                COUNT(l.id)              AS unreturned_books_count,
                SUM(l.fine_amount)       AS net_fine_amount,
                GROUP_CONCAT(l.isbn, ', ') AS overdue_isbns
            FROM customers c
            JOIN loans l ON c.customer_id = l.customer_id
            WHERE l.returned = 0
            GROUP BY c.customer_id, c.name, c.mobile_number, c.email_id
            HAVING SUM(l.fine_amount) > 0
        """
        cursor.execute(query)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close() 

def verify_librarian_email(email):
    """
    Checks if an email exists in the auth_allowed_librarians whitelist table.
    Returns the (librarian_id, name) tuple if found, otherwise None.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT librarian_id, name 
            FROM auth_allowed_librarians 
            WHERE email_id = ?
        """, (email,))
        return cursor.fetchone()
    finally:
        cursor.close()
        conn.close()
        
def admin_email(database_path = DB_PATH, librarian_id = "LIB001") -> str: 

    query = "SELECT email_id FROM auth_allowed_librarians WHERE librarian_id = ?;"
    
    try:
        # Establish connection to your local library.db file
        conn = sqlite3.connect(database_path)
        cursor = conn.cursor()
        
        # Execute the query safely using a parameterized input to prevent SQL injection
        cursor.execute(query, (librarian_id,))
        result = cursor.fetchone()
        
        # Close connection loops
        cursor.close()
        conn.close()
        
        # Return the email if found, otherwise return a descriptive notice
        if result:
            return result[0]
        return f"No librarian found with ID: {librarian_id}"
        
    except sqlite3.Error as e:
        return f"Database error occurred: {e}"      
        
        
        
        
        
        
        
        
        
        
        
        
            