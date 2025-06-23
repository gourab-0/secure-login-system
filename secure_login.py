import hashlib
import os
import sqlite3
import time
import secrets
import hmac
import base64
import struct
from getpass import getpass

class SecureLoginSystem:
    def __init__(self, db_name="secure_users.db"):
        """Initialize the login system with a database connection."""
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.current_user = None
        
    def create_tables(self):
        """Create necessary database tables if they don't exist."""
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            two_factor_enabled INTEGER DEFAULT 0,
            two_factor_secret TEXT
        )
        ''')
        self.conn.commit()
        
    def hash_password(self, password, salt=None):
        """Hash a password with a salt using SHA-256."""
        if not salt:
            salt = secrets.token_hex(16)
        hash_obj = hashlib.sha256(salt.encode() + password.encode())
        password_hash = hash_obj.hexdigest()
        return password_hash, salt
        
    def register_user(self, username, password):
        """Register a new user with a hashed password."""
        # Check if user already exists
        self.cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if self.cursor.fetchone():
            print("Username already exists!")
            return False
            
        # Hash the password with a salt
        password_hash, salt = self.hash_password(password)
        
        # Insert the new user into the database
        self.cursor.execute(
            "INSERT INTO users (username, password_hash, password_salt, two_factor_enabled) VALUES (?, ?, ?, 0)",
            (username, password_hash, salt)
        )
        self.conn.commit()
        print(f"User {username} registered successfully!")
        return True
        
    def generate_totp_code(self, secret, time_step=30):
        """Generate a simple TOTP code."""
        # Get current timestamp and convert to counter value
        counter = int(time.time() // time_step)
        counter_bytes = struct.pack('>Q', counter)
        
        # Create HMAC-SHA1 hash
        h = hmac.new(base64.b32decode(secret, True), counter_bytes, hashlib.sha1).digest()
        
        # Extract a 4-byte dynamic binary code from the HMAC
        offset = h[-1] & 0x0F
        binary = ((h[offset] & 0x7F) << 24) | ((h[offset + 1] & 0xFF) << 16) | ((h[offset + 2] & 0xFF) << 8) | (h[offset + 3] & 0xFF)
        
        # Generate a 6-digit TOTP code
        return str(binary % 1000000).zfill(6)
        
    def verify_totp(self, secret, code):
        """Verify a TOTP code."""
        # Generate a code and compare
        return self.generate_totp_code(secret) == code
        
    def enable_2fa(self, username):
        """Enable two-factor authentication for a user."""
        if not self.current_user or self.current_user != username:
            print("You must be logged in to enable 2FA.")
            return None
            
        # Generate a secret key for TOTP
        secret = base64.b32encode(os.urandom(10)).decode('utf-8')
        
        # Save the secret to the database
        self.cursor.execute(
            "UPDATE users SET two_factor_enabled = 1, two_factor_secret = ? WHERE username = ?",
            (secret, username)
        )
        self.conn.commit()
        
        print("Two-factor authentication enabled!")
        print(f"Your secret key: {secret}")
        print("Please store this key securely.")
        print(f"Your current TOTP code: {self.generate_totp_code(secret)}")
        print("This code will change every 30 seconds.")
        return secret
        
    def login(self, username, password, totp_code=None):
        """Authenticate a user with password and optional 2FA."""
        # Get user from database
        self.cursor.execute(
            "SELECT password_hash, password_salt, two_factor_enabled, two_factor_secret FROM users WHERE username = ?", 
            (username,)
        )
        user_data = self.cursor.fetchone()
        
        if not user_data:
            print("Invalid username or password.")
            return False
            
        password_hash, salt, two_factor_enabled, two_factor_secret = user_data
        
        # Verify password
        calculated_hash, _ = self.hash_password(password, salt)
        if calculated_hash != password_hash:
            print("Invalid username or password.")
            return False
            
        # Check if 2FA is enabled
        if two_factor_enabled:
            if not totp_code:
                print("Two-factor authentication is required.")
                return "2FA_REQUIRED"
                
            # Verify TOTP code
            if not self.verify_totp(two_factor_secret, totp_code):
                print("Invalid two-factor code.")
                return False
                
        print(f"Login successful! Welcome, {username}!")
        self.current_user = username
        return True
        
    def logout(self):
        """Log out the current user."""
        if self.current_user:
            print(f"Goodbye, {self.current_user}!")
            self.current_user = None
        else:
            print("No user is currently logged in.")
            
    def display_users(self):
        """Display all users in the database (for demonstration purposes)."""
        self.cursor.execute("SELECT id, username, two_factor_enabled FROM users")
        users = self.cursor.fetchall()
        
        if not users:
            print("No users registered.")
            return
            
        headers = ["ID", "Username", "2FA Enabled"]
        rows = [[user[0], user[1], "Yes" if user[2] else "No"] for user in users]
        print("\nRegistered Users:")
        print("-" * 40)
        print(f"{'ID':<5}{'Username':<20}{'2FA Enabled':<10}")
        print("-" * 40)
        for row in rows:
            print(f"{row[0]:<5}{row[1]:<20}{'Yes' if row[2] == 'Yes' else 'No':<10}")
        
    def close(self):
        """Close the database connection."""
        self.conn.close()

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def main():
    login_system = SecureLoginSystem()
    
    while True:
        clear_screen()
        print("\n===== SECURE LOGIN SYSTEM =====")
        print("1. Register")
        print("2. Login")
        print("3. Enable Two-Factor Authentication")
        print("4. View Users")
        print("5. Logout")
        print("6. Exit")
        
        choice = input("\nEnter your choice (1-6): ")
        
        if choice == '1':
            username = input("Enter username: ")
            password = getpass("Enter password: ")
            confirm_password = getpass("Confirm password: ")
            
            if password != confirm_password:
                print("Passwords do not match!")
                time.sleep(2)
                continue
                
            login_system.register_user(username, password)
            time.sleep(2)
            
        elif choice == '2':
            username = input("Enter username: ")
            password = getpass("Enter password: ")
            
            login_result = login_system.login(username, password)
            
            if login_result == "2FA_REQUIRED":
                totp_code = input("Enter your two-factor code: ")
                login_system.login(username, password, totp_code)
                
            time.sleep(2)
            
        elif choice == '3':
            if not login_system.current_user:
                print("You must be logged in to enable two-factor authentication.")
                time.sleep(2)
                continue
                
            login_system.enable_2fa(login_system.current_user)
            input("\nPress Enter to continue...")
            
        elif choice == '4':
            login_system.display_users()
            input("\nPress Enter to continue...")
            
        elif choice == '5':
            login_system.logout()
            time.sleep(2)
            
        elif choice == '6':
            print("Thank you for using the Secure Login System!")
            login_system.close()
            break
            
        else:
            print("Invalid choice. Please try again.")
            time.sleep(2)

if __name__ == "__main__":
    main()