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
