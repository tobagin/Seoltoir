import sqlite3
import os
from datetime import datetime
import json # For session data
from .debug import debug_print

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._create_tables()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _create_tables(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT,
                visit_count INTEGER DEFAULT 1,
                last_visit TIMESTAMP NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                added_date TIMESTAMP NOT NULL
            )
        """)

        # Session table for full session restore
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                window_id INTEGER,
                tab_index INTEGER,
                url TEXT NOT NULL,
                title TEXT,
                is_private INTEGER DEFAULT 0,
                serialized_state TEXT
            )
        """)

        # Zoom levels table for per-site zoom persistence
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zoom_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL UNIQUE,
                zoom_level REAL NOT NULL DEFAULT 1.0,
                last_updated TIMESTAMP NOT NULL
            )
        """)

        # Search engines table for search engine management
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_engines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                url TEXT NOT NULL,
                keyword TEXT UNIQUE,
                favicon_url TEXT,
                suggestions_url TEXT,
                is_default INTEGER DEFAULT 0,
                is_builtin INTEGER DEFAULT 0,
                position INTEGER DEFAULT 0,
                created_date TIMESTAMP NOT NULL,
                last_used TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def add_history_entry(self, url: str, title: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        try:
            cursor.execute("""
                INSERT INTO history (url, title, last_visit)
                VALUES (?, ?, ?)
            """, (url, title, now))
        except sqlite3.IntegrityError:
            cursor.execute("""
                UPDATE history
                SET visit_count = visit_count + 1, last_visit = ?, title = ?
                WHERE url = ?
            """, (now, title, url))
        conn.commit()
        conn.close()

    def get_history(self, limit=100) -> list[tuple]: # Change limit to None for all history
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT url, title, last_visit
            FROM history
            ORDER BY last_visit DESC
            LIMIT ?
        """, (limit,) if limit is not None else ()) # Handle limit=None for all history
        # For limit=None, the query will be `ORDER BY last_visit DESC` without LIMIT

        history_entries = cursor.fetchall()
        conn.close()
        return history_entries

    def clear_history(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM history")
        conn.commit()
        conn.close()
        debug_print("History cleared.")

    def add_bookmark(self, url: str, title: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        try:
            cursor.execute("""
                INSERT INTO bookmarks (url, title, added_date)
                VALUES (?, ?, ?)
            """, (url, title, now))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            debug_print(f"Bookmark for {url} already exists.")
            conn.close()
            return False

    def remove_bookmark(self, url: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bookmarks WHERE url = ?", (url,))
        conn.commit()
        conn.close()

    def get_bookmarks(self) -> list[tuple]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT url, title, added_date FROM bookmarks ORDER BY title ASC")
        bookmarks = cursor.fetchall()
        conn.close()
        return bookmarks

    def is_bookmarked(self, url: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM bookmarks WHERE url = ?", (url,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def get_all_non_bookmarked_domains(self) -> list[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT SUBSTR(url, INSTR(url, '//') + 2, INSTR(SUBSTR(url, INSTR(url, '//') + 2), '/') - 1) FROM history WHERE url NOT IN (SELECT url FROM bookmarks)")
        domains = [row[0] for row in cursor.fetchall() if row[0]]
        conn.close()
        return list(set(domains))

    def save_session(self, session_data: list[dict]):
        """Saves current session tabs to the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session") # Clear previous session
        for i, tab_data in enumerate(session_data):
            cursor.execute("""
                INSERT INTO session (window_id, tab_index, url, title, is_private, serialized_state)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                1, # Simple window_id for now, assuming single window
                i,
                tab_data.get("url", ""),
                tab_data.get("title", ""),
                1 if tab_data.get("is_private", False) else 0,
                tab_data.get("serialized_state", "") # Store serialized state if available
            ))
        conn.commit()
        conn.close()
        debug_print(f"Session saved with {len(session_data)} tabs.")

    def load_session(self) -> list[dict]:
        """Loads session tabs from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT url, title, is_private, serialized_state
            FROM session
            ORDER BY tab_index ASC
        """)
        session_entries = []
        for url, title, is_private_int, serialized_state in cursor.fetchall():
            session_entries.append({
                "url": url,
                "title": title,
                "is_private": bool(is_private_int),
                "serialized_state": serialized_state # Deserialize later in WebKit
            })
        conn.close()
        debug_print(f"Loaded session with {len(session_entries)} tabs.")
        return session_entries

    def get_zoom_level(self, domain: str) -> float:
        """Get the zoom level for a specific domain."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT zoom_level FROM zoom_levels WHERE domain = ?", (domain,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else 1.0  # Default zoom level is 1.0 (100%)

    def set_zoom_level(self, domain: str, zoom_level: float):
        """Set the zoom level for a specific domain."""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        try:
            cursor.execute("""
                INSERT INTO zoom_levels (domain, zoom_level, last_updated)
                VALUES (?, ?, ?)
            """, (domain, zoom_level, now))
        except sqlite3.IntegrityError:
            cursor.execute("""
                UPDATE zoom_levels
                SET zoom_level = ?, last_updated = ?
                WHERE domain = ?
            """, (zoom_level, now, domain))
        conn.commit()
        conn.close()
        debug_print(f"Set zoom level for {domain} to {zoom_level}")

    def remove_zoom_level(self, domain: str):
        """Remove the zoom level setting for a specific domain."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM zoom_levels WHERE domain = ?", (domain,))
        conn.commit()
        conn.close()
        debug_print(f"Removed zoom level for {domain}")

    def get_all_zoom_levels(self) -> list[tuple]:
        """Get all zoom level settings."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT domain, zoom_level, last_updated FROM zoom_levels ORDER BY domain ASC")
        zoom_levels = cursor.fetchall()
        conn.close()
        return zoom_levels

    def add_search_engine(self, name: str, url: str, keyword: str = None, favicon_url: str = None, 
                         suggestions_url: str = None, is_default: bool = False, is_builtin: bool = False) -> bool:
        """Add a new search engine."""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        # Get next position
        cursor.execute("SELECT MAX(position) FROM search_engines")
        max_position = cursor.fetchone()[0]
        position = (max_position + 1) if max_position is not None else 0
        
        try:
            cursor.execute("""
                INSERT INTO search_engines (name, url, keyword, favicon_url, suggestions_url, 
                                           is_default, is_builtin, position, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, url, keyword, favicon_url, suggestions_url, 
                  1 if is_default else 0, 1 if is_builtin else 0, position, now))
            
            # If this is being set as default, unset all other defaults
            if is_default:
                cursor.execute("UPDATE search_engines SET is_default = 0 WHERE name != ?", (name,))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            debug_print(f"Search engine {name} already exists or keyword {keyword} is taken.")
            conn.close()
            return False

    def update_search_engine(self, engine_id: int, name: str, url: str, keyword: str = None, 
                           favicon_url: str = None, suggestions_url: str = None, is_default: bool = False) -> bool:
        """Update an existing search engine."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE search_engines 
                SET name = ?, url = ?, keyword = ?, favicon_url = ?, suggestions_url = ?, is_default = ?
                WHERE id = ?
            """, (name, url, keyword, favicon_url, suggestions_url, 1 if is_default else 0, engine_id))
            
            # If this is being set as default, unset all other defaults
            if is_default:
                cursor.execute("UPDATE search_engines SET is_default = 0 WHERE id != ?", (engine_id,))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            debug_print(f"Search engine name {name} already exists or keyword {keyword} is taken.")
            conn.close()
            return False

    def remove_search_engine(self, engine_id: int):
        """Remove a search engine."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM search_engines WHERE id = ?", (engine_id,))
        conn.commit()
        conn.close()

    def get_search_engines(self) -> list[tuple]:
        """Get all search engines ordered by position."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, url, keyword, favicon_url, suggestions_url, is_default, is_builtin, position, created_date, last_used
            FROM search_engines 
            ORDER BY position ASC
        """)
        engines = cursor.fetchall()
        conn.close()
        return engines

    def get_search_engine_by_id(self, engine_id: int) -> tuple:
        """Get a specific search engine by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, url, keyword, favicon_url, suggestions_url, is_default, is_builtin, position, created_date, last_used
            FROM search_engines 
            WHERE id = ?
        """, (engine_id,))
        result = cursor.fetchone()
        conn.close()
        return result

    def get_search_engine_by_keyword(self, keyword: str) -> tuple:
        """Get a search engine by keyword."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, url, keyword, favicon_url, suggestions_url, is_default, is_builtin, position, created_date, last_used
            FROM search_engines 
            WHERE keyword = ?
        """, (keyword,))
        result = cursor.fetchone()
        conn.close()
        return result

    def get_default_search_engine(self) -> tuple:
        """Get the default search engine."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, url, keyword, favicon_url, suggestions_url, is_default, is_builtin, position, created_date, last_used
            FROM search_engines 
            WHERE is_default = 1
        """)
        result = cursor.fetchone()
        conn.close()
        return result

    def set_default_search_engine(self, engine_id: int):
        """Set a search engine as default."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE search_engines SET is_default = 0")  # Unset all defaults
        cursor.execute("UPDATE search_engines SET is_default = 1 WHERE id = ?", (engine_id,))
        conn.commit()
        conn.close()

    def update_search_engine_last_used(self, engine_id: int):
        """Update the last used timestamp for a search engine."""
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute("UPDATE search_engines SET last_used = ? WHERE id = ?", (now, engine_id))
        conn.commit()
        conn.close()

    def reorder_search_engines(self, engine_positions: list[tuple]):
        """Reorder search engines by updating their positions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        for engine_id, position in engine_positions:
            cursor.execute("UPDATE search_engines SET position = ? WHERE id = ?", (position, engine_id))
        conn.commit()
        conn.close()

    def search_engines_exist(self) -> bool:
        """Check if any search engines exist in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM search_engines")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
