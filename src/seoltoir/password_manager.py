import gi
gi.require_version("Secret", "1")
from gi.repository import Secret, GLib, Gio
import json
import hashlib
import secrets
import string
import urllib.parse
from datetime import datetime
import threading
from .debug import debug_print

class PasswordManager:
    """Secure password management using libsecret/GNOME Keyring."""
    
    SCHEMA_NAME = "io.github.tobagin.seoltoir.password"
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self._schema = None
        self._setup_secret_schema()
        self._lock = threading.RLock()
        
    def _setup_secret_schema(self):
        """Set up the Secret Service schema for storing passwords."""
        try:
            self._schema = Secret.Schema.new(
                self.SCHEMA_NAME,
                Secret.SchemaFlags.NONE,
                {
                    "domain": Secret.SchemaAttributeType.STRING,
                    "username": Secret.SchemaAttributeType.STRING,
                    "url": Secret.SchemaAttributeType.STRING,
                    "application": Secret.SchemaAttributeType.STRING,
                }
            )
            debug_print("[PASSWORD] Secret schema initialized")
        except Exception as e:
            debug_print(f"[PASSWORD] Error setting up schema: {e}")
            self._schema = None

    def _get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return url

    def save_password(self, url: str, username: str, password: str, title: str = None) -> bool:
        """Save a password securely to the keyring."""
        if not self._schema:
            debug_print("[PASSWORD] Schema not available")
            return False
            
        with self._lock:
            try:
                domain = self._get_domain_from_url(url)
                
                # Create attributes for the password entry
                attributes = {
                    "domain": domain,
                    "username": username,
                    "url": url,
                    "application": "Seoltoir Browser"
                }
                
                # Create a descriptive label
                label = title or f"Seoltoir: {username}@{domain}"
                
                # Store password synchronously for now
                # In production, you might want to use async version
                Secret.password_store_sync(
                    self._schema,
                    attributes,
                    Secret.COLLECTION_DEFAULT,
                    label,
                    password,
                    None
                )
                
                # Store metadata in database
                self._store_password_metadata(url, username, domain, title)
                
                debug_print(f"[PASSWORD] Saved password for {username}@{domain}")
                return True
                
            except Exception as e:
                debug_print(f"[PASSWORD] Error saving password: {e}")
                return False

    def get_password(self, url: str, username: str) -> str:
        """Retrieve a password from the keyring."""
        if not self._schema:
            return None
            
        with self._lock:
            try:
                domain = self._get_domain_from_url(url)
                
                attributes = {
                    "domain": domain,
                    "username": username,
                    "url": url,
                    "application": "Seoltoir Browser"
                }
                
                password = Secret.password_lookup_sync(
                    self._schema,
                    attributes,
                    None
                )
                
                if password:
                    # Update last used time
                    self._update_password_last_used(url, username)
                    debug_print(f"[PASSWORD] Retrieved password for {username}@{domain}")
                    
                return password
                
            except Exception as e:
                debug_print(f"[PASSWORD] Error retrieving password: {e}")
                return None

    def get_passwords_for_domain(self, url: str) -> list:
        """Get all saved passwords for a domain."""
        if not self._schema:
            return []
            
        with self._lock:
            try:
                domain = self._get_domain_from_url(url)
                
                # Get metadata from database first
                metadata_list = self._get_password_metadata_for_domain(domain)
                passwords = []
                
                for metadata in metadata_list:
                    username = metadata.get('username')
                    stored_url = metadata.get('url', url)
                    
                    attributes = {
                        "domain": domain,
                        "username": username,
                        "url": stored_url,
                        "application": "Seoltoir Browser"
                    }
                    
                    password = Secret.password_lookup_sync(
                        self._schema,
                        attributes,
                        None
                    )
                    
                    if password:
                        passwords.append({
                            'username': username,
                            'url': stored_url,
                            'domain': domain,
                            'title': metadata.get('title'),
                            'last_used': metadata.get('last_used'),
                            'created': metadata.get('created')
                        })
                
                debug_print(f"[PASSWORD] Found {len(passwords)} passwords for {domain}")
                return passwords
                
            except Exception as e:
                debug_print(f"[PASSWORD] Error getting passwords for domain: {e}")
                return []

    def delete_password(self, url: str, username: str) -> bool:
        """Delete a password from the keyring."""
        if not self._schema:
            return False
            
        with self._lock:
            try:
                domain = self._get_domain_from_url(url)
                
                attributes = {
                    "domain": domain,
                    "username": username,
                    "url": url,
                    "application": "Seoltoir Browser"
                }
                
                deleted = Secret.password_clear_sync(
                    self._schema,
                    attributes,
                    None
                )
                
                if deleted:
                    # Remove metadata from database
                    self._delete_password_metadata(url, username)
                    debug_print(f"[PASSWORD] Deleted password for {username}@{domain}")
                    
                return deleted
                
            except Exception as e:
                debug_print(f"[PASSWORD] Error deleting password: {e}")
                return False

    def get_all_passwords(self) -> list:
        """Get all saved passwords metadata."""
        try:
            return self._get_all_password_metadata()
        except Exception as e:
            debug_print(f"[PASSWORD] Error getting all passwords: {e}")
            return []

    def update_password(self, url: str, username: str, new_password: str) -> bool:
        """Update an existing password."""
        return self.save_password(url, username, new_password)

    def password_exists(self, url: str, username: str) -> bool:
        """Check if a password exists for the given URL and username."""
        password = self.get_password(url, username)
        return password is not None

    def generate_password(self, length: int = 16, use_symbols: bool = True, 
                         use_numbers: bool = True, use_uppercase: bool = True, 
                         use_lowercase: bool = True) -> str:
        """Generate a secure password."""
        chars = ""
        
        if use_lowercase:
            chars += string.ascii_lowercase
        if use_uppercase:
            chars += string.ascii_uppercase
        if use_numbers:
            chars += string.digits
        if use_symbols:
            chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"
            
        if not chars:
            chars = string.ascii_letters + string.digits
            
        # Ensure we have at least one character from each selected set
        password = []
        if use_lowercase and string.ascii_lowercase:
            password.append(secrets.choice(string.ascii_lowercase))
        if use_uppercase and string.ascii_uppercase:
            password.append(secrets.choice(string.ascii_uppercase))
        if use_numbers and string.digits:
            password.append(secrets.choice(string.digits))
        if use_symbols:
            password.append(secrets.choice("!@#$%^&*()_+-=[]{}|;:,.<>?"))
            
        # Fill the rest randomly
        for _ in range(length - len(password)):
            password.append(secrets.choice(chars))
            
        # Shuffle the password
        secrets.SystemRandom().shuffle(password)
        
        return ''.join(password)

    def calculate_password_strength(self, password: str) -> dict:
        """Calculate password strength and return score with details."""
        if not password:
            return {"score": 0, "level": "Very Weak", "feedback": []}
            
        score = 0
        feedback = []
        
        # Length scoring
        length = len(password)
        if length >= 12:
            score += 25
        elif length >= 8:
            score += 15
        elif length >= 6:
            score += 10
        else:
            feedback.append("Password should be at least 8 characters long")
            
        # Character variety scoring
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        variety_score = sum([has_lower, has_upper, has_digit, has_symbol])
        score += variety_score * 10
        
        if not has_lower:
            feedback.append("Add lowercase letters")
        if not has_upper:
            feedback.append("Add uppercase letters")
        if not has_digit:
            feedback.append("Add numbers")
        if not has_symbol:
            feedback.append("Add symbols")
            
        # Entropy and patterns
        unique_chars = len(set(password))
        if unique_chars / length > 0.7:
            score += 15
        else:
            feedback.append("Avoid repeated characters")
            
        # Common patterns penalty
        common_patterns = ["123", "abc", "qwe", "password", "admin"]
        for pattern in common_patterns:
            if pattern.lower() in password.lower():
                score -= 10
                feedback.append(f"Avoid common patterns like '{pattern}'")
                
        # Cap score at 100
        score = min(score, 100)
        
        # Determine level
        if score >= 80:
            level = "Very Strong"
        elif score >= 60:
            level = "Strong"
        elif score >= 40:
            level = "Medium"
        elif score >= 20:
            level = "Weak"
        else:
            level = "Very Weak"
            
        return {
            "score": score,
            "level": level,
            "feedback": feedback
        }

    # Database metadata methods
    def _store_password_metadata(self, url: str, username: str, domain: str, title: str):
        """Store password metadata in database."""
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            # Create passwords metadata table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS password_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    username TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    created TIMESTAMP NOT NULL,
                    last_used TIMESTAMP,
                    UNIQUE(domain, username, url)
                )
            """)
            
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO password_metadata 
                (domain, username, url, title, created, last_used)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (domain, username, url, title, now, now))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            debug_print(f"[PASSWORD] Error storing metadata: {e}")

    def _get_password_metadata_for_domain(self, domain: str) -> list:
        """Get password metadata for a domain."""
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT username, url, title, created, last_used 
                FROM password_metadata 
                WHERE domain = ?
                ORDER BY last_used DESC
            """, (domain,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'username': row[0],
                    'url': row[1],
                    'title': row[2],
                    'created': row[3],
                    'last_used': row[4]
                })
                
            conn.close()
            return results
            
        except Exception as e:
            debug_print(f"[PASSWORD] Error getting metadata: {e}")
            return []

    def _get_all_password_metadata(self) -> list:
        """Get all password metadata."""
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT domain, username, url, title, created, last_used 
                FROM password_metadata 
                ORDER BY last_used DESC
            """)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'domain': row[0],
                    'username': row[1],
                    'url': row[2],
                    'title': row[3],
                    'created': row[4],
                    'last_used': row[5]
                })
                
            conn.close()
            return results
            
        except Exception as e:
            debug_print(f"[PASSWORD] Error getting all metadata: {e}")
            return []

    def _update_password_last_used(self, url: str, username: str):
        """Update last used timestamp for a password."""
        try:
            domain = self._get_domain_from_url(url)
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            cursor.execute("""
                UPDATE password_metadata 
                SET last_used = ? 
                WHERE domain = ? AND username = ? AND url = ?
            """, (now, domain, username, url))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            debug_print(f"[PASSWORD] Error updating last used: {e}")

    def _delete_password_metadata(self, url: str, username: str):
        """Delete password metadata."""
        try:
            domain = self._get_domain_from_url(url)
            conn = self.db_manager._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM password_metadata 
                WHERE domain = ? AND username = ? AND url = ?
            """, (domain, username, url))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            debug_print(f"[PASSWORD] Error deleting metadata: {e}")