import json
import urllib.parse
from typing import Optional, List, Dict, Any
from .database import DatabaseManager
from .debug import debug_print
from gi.repository import Gio

class SearchEngineManager:
    """Manages search engines with database storage and GSettings integration."""
    
    DEFAULT_SEARCH_ENGINES = [
        {
            "name": "DuckDuckGo",
            "url": "https://duckduckgo.com/?q=%s",
            "keyword": "ddg",
            "favicon_url": "https://duckduckgo.com/favicon.ico",
            "suggestions_url": "https://duckduckgo.com/ac/?q=%s&type=list",
            "is_default": True,
            "is_builtin": True
        },
        {
            "name": "Google",
            "url": "https://www.google.com/search?q=%s",
            "keyword": "g",
            "favicon_url": "https://www.google.com/favicon.ico",
            "suggestions_url": "https://suggestqueries.google.com/complete/search?client=firefox&q=%s",
            "is_default": False,
            "is_builtin": True
        },
        {
            "name": "Bing",
            "url": "https://www.bing.com/search?q=%s",
            "keyword": "b",
            "favicon_url": "https://www.bing.com/favicon.ico",
            "suggestions_url": "https://www.bing.com/osjson.aspx?query=%s",
            "is_default": False,
            "is_builtin": True
        },
        {
            "name": "Yahoo",
            "url": "https://search.yahoo.com/search?p=%s",
            "keyword": "y",
            "favicon_url": "https://search.yahoo.com/favicon.ico",
            "suggestions_url": "https://search.yahoo.com/sugg/gossip/gossip-us-ura/?output=sd1&command=%s",
            "is_default": False,
            "is_builtin": True
        },
        {
            "name": "Startpage",
            "url": "https://www.startpage.com/sp/search?query=%s",
            "keyword": "sp",
            "favicon_url": "https://www.startpage.com/favicon.ico",
            "suggestions_url": None,
            "is_default": False,
            "is_builtin": True
        },
        {
            "name": "SearXNG",
            "url": "https://searx.be/search?q=%s",
            "keyword": "sx",
            "favicon_url": "https://searx.be/favicon.ico",
            "suggestions_url": "https://searx.be/autocompleter?q=%s",
            "is_default": False,
            "is_builtin": True
        }
    ]
    
    def __init__(self, database_manager: DatabaseManager):
        self.db = database_manager
        self.settings = Gio.Settings.new("io.github.tobagin.seoltoir")
        self._initialize_search_engines()
    
    def _initialize_search_engines(self):
        """Initialize search engines from defaults and migrate from GSettings if needed."""
        # Check if we need to migrate from GSettings
        if not self.db.search_engines_exist():
            self._migrate_from_gsettings()
            
        # If still no engines, populate defaults
        if not self.db.search_engines_exist():
            self._populate_default_engines()
    
    def _migrate_from_gsettings(self):
        """Migrate search engines from GSettings to database."""
        search_engines_json = self.settings.get_strv("search-engines")
        selected_engine_name = self.settings.get_string("selected-search-engine-name")
        
        if search_engines_json:
            debug_print("Migrating search engines from GSettings to database...")
            for engine_json in search_engines_json:
                try:
                    engine_data = json.loads(engine_json)
                    is_default = engine_data.get("name") == selected_engine_name
                    
                    self.db.add_search_engine(
                        name=engine_data.get("name", ""),
                        url=engine_data.get("url", ""),
                        keyword=engine_data.get("keyword"),
                        favicon_url=engine_data.get("favicon_url"),
                        suggestions_url=engine_data.get("suggestions_url"),
                        is_default=is_default,
                        is_builtin=engine_data.get("is_builtin", False)
                    )
                except json.JSONDecodeError:
                    debug_print(f"Failed to parse search engine JSON: {engine_json}")
            
            debug_print(f"Migrated {len(search_engines_json)} search engines from GSettings")
    
    def _populate_default_engines(self):
        """Populate the database with default search engines."""
        debug_print("Populating default search engines...")
        for engine in self.DEFAULT_SEARCH_ENGINES:
            self.db.add_search_engine(
                name=engine["name"],
                url=engine["url"],
                keyword=engine["keyword"],
                favicon_url=engine["favicon_url"],
                suggestions_url=engine["suggestions_url"],
                is_default=engine["is_default"],
                is_builtin=engine["is_builtin"]
            )
        debug_print(f"Added {len(self.DEFAULT_SEARCH_ENGINES)} default search engines")
    
    def get_all_engines(self) -> List[Dict[str, Any]]:
        """Get all search engines as a list of dictionaries."""
        engines = self.db.get_search_engines()
        return [self._tuple_to_dict(engine) for engine in engines]
    
    def get_engine_by_id(self, engine_id: int) -> Optional[Dict[str, Any]]:
        """Get a search engine by ID."""
        engine = self.db.get_search_engine_by_id(engine_id)
        return self._tuple_to_dict(engine) if engine else None
    
    def get_engine_by_keyword(self, keyword: str) -> Optional[Dict[str, Any]]:
        """Get a search engine by keyword."""
        engine = self.db.get_search_engine_by_keyword(keyword)
        return self._tuple_to_dict(engine) if engine else None
    
    def get_default_engine(self) -> Optional[Dict[str, Any]]:
        """Get the default search engine."""
        engine = self.db.get_default_search_engine()
        return self._tuple_to_dict(engine) if engine else None
    
    def add_engine(self, name: str, url: str, keyword: str = None, favicon_url: str = None, 
                  suggestions_url: str = None, is_default: bool = False) -> bool:
        """Add a new search engine."""
        return self.db.add_search_engine(
            name=name, url=url, keyword=keyword, favicon_url=favicon_url,
            suggestions_url=suggestions_url, is_default=is_default, is_builtin=False
        )
    
    def update_engine(self, engine_id: int, name: str, url: str, keyword: str = None, 
                     favicon_url: str = None, suggestions_url: str = None, is_default: bool = False) -> bool:
        """Update an existing search engine."""
        return self.db.update_search_engine(
            engine_id=engine_id, name=name, url=url, keyword=keyword,
            favicon_url=favicon_url, suggestions_url=suggestions_url, is_default=is_default
        )
    
    def remove_engine(self, engine_id: int) -> bool:
        """Remove a search engine."""
        engine = self.get_engine_by_id(engine_id)
        if not engine:
            return False
        
        # Don't allow removal of the last engine
        if len(self.get_all_engines()) <= 1:
            debug_print("Cannot remove the last search engine")
            return False
        
        # If removing default engine, set another as default
        if engine.get("is_default"):
            all_engines = self.get_all_engines()
            for other_engine in all_engines:
                if other_engine["id"] != engine_id:
                    self.set_default_engine(other_engine["id"])
                    break
        
        self.db.remove_search_engine(engine_id)
        return True
    
    def set_default_engine(self, engine_id: int):
        """Set a search engine as default."""
        self.db.set_default_search_engine(engine_id)
    
    def search_with_engine(self, query: str, engine_id: int = None) -> str:
        """Generate search URL for a query using specified engine or default."""
        if engine_id:
            engine = self.get_engine_by_id(engine_id)
        else:
            engine = self.get_default_engine()
        
        if not engine:
            # Fallback to first available engine
            all_engines = self.get_all_engines()
            if all_engines:
                engine = all_engines[0]
            else:
                # Ultimate fallback to DuckDuckGo
                return f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
        
        # Update last used timestamp
        self.db.update_search_engine_last_used(engine["id"])
        
        # Replace %s with encoded query
        search_url = engine["url"].replace("%s", urllib.parse.quote(query))
        return search_url
    
    def search_with_keyword(self, keyword: str, query: str) -> Optional[str]:
        """Search using a keyword shortcut."""
        engine = self.get_engine_by_keyword(keyword)
        if engine:
            return self.search_with_engine(query, engine["id"])
        return None
    
    def parse_search_input(self, input_text: str) -> tuple[str, str]:
        """Parse input text for keyword search or regular search.
        
        Returns:
            tuple: (search_type, processed_input)
            search_type: 'keyword' if keyword search, 'regular' if normal search
            processed_input: the search URL or original input
        """
        input_text = input_text.strip()
        
        # Check for keyword search (format: "keyword search terms")
        if " " in input_text:
            potential_keyword = input_text.split(" ", 1)[0]
            search_terms = input_text.split(" ", 1)[1]
            
            search_url = self.search_with_keyword(potential_keyword, search_terms)
            if search_url:
                return ("keyword", search_url)
        
        # Regular search or URL
        return ("regular", input_text)
    
    def get_suggestions_url(self, engine_id: int = None) -> Optional[str]:
        """Get suggestions URL for specified engine or default."""
        if engine_id:
            engine = self.get_engine_by_id(engine_id)
        else:
            engine = self.get_default_engine()
        
        return engine.get("suggestions_url") if engine else None
    
    def export_engines(self) -> str:
        """Export all search engines to JSON format."""
        engines = self.get_all_engines()
        return json.dumps(engines, indent=2)
    
    def import_engines(self, json_data: str) -> bool:
        """Import search engines from JSON format."""
        try:
            engines = json.loads(json_data)
            if not isinstance(engines, list):
                return False
            
            for engine in engines:
                if not isinstance(engine, dict):
                    continue
                    
                # Skip if required fields are missing
                if not engine.get("name") or not engine.get("url"):
                    continue
                
                # Don't set as default during import to avoid conflicts
                self.add_engine(
                    name=engine.get("name"),
                    url=engine.get("url"),
                    keyword=engine.get("keyword"),
                    favicon_url=engine.get("favicon_url"),
                    suggestions_url=engine.get("suggestions_url"),
                    is_default=False  # User can set default manually
                )
            
            return True
        except json.JSONDecodeError:
            return False
    
    def _tuple_to_dict(self, engine_tuple: tuple) -> Dict[str, Any]:
        """Convert database tuple to dictionary."""
        if not engine_tuple:
            return {}
        
        return {
            "id": engine_tuple[0],
            "name": engine_tuple[1],
            "url": engine_tuple[2],
            "keyword": engine_tuple[3],
            "favicon_url": engine_tuple[4],
            "suggestions_url": engine_tuple[5],
            "is_default": bool(engine_tuple[6]),
            "is_builtin": bool(engine_tuple[7]),
            "position": engine_tuple[8],
            "created_date": engine_tuple[9],
            "last_used": engine_tuple[10]
        }