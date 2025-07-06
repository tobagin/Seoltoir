import json
import urllib.parse
from typing import List, Optional, Dict, Any
import requests
from gi.repository import GLib
import threading
from .debug import debug_print

class SearchSuggestionsClient:
    """Client for fetching search suggestions from search engines."""
    
    def __init__(self, timeout: int = 5):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def fetch_suggestions(self, query: str, suggestions_url: str, callback, user_data=None):
        """Fetch search suggestions asynchronously."""
        if not query.strip() or not suggestions_url:
            callback([], user_data)
            return
        
        # Start request in a separate thread
        thread = threading.Thread(
            target=self._fetch_suggestions_thread,
            args=(query, suggestions_url, callback, user_data)
        )
        thread.daemon = True
        thread.start()
    
    def _fetch_suggestions_thread(self, query: str, suggestions_url: str, callback, user_data):
        """Fetch suggestions in a background thread."""
        try:
            # Prepare the URL with the query
            encoded_query = urllib.parse.quote(query)
            url = suggestions_url.replace('%s', encoded_query)
            
            debug_print(f"[DEBUG] Fetching suggestions from: {url}")
            
            # Make the request
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse the response
            suggestions = self._parse_suggestions_response(response.text, url)
            
            # Call the callback in the main thread
            GLib.idle_add(callback, suggestions, user_data)
            
        except Exception as e:
            debug_print(f"[DEBUG] Error fetching suggestions: {e}")
            GLib.idle_add(callback, [], user_data)
    
    def _parse_suggestions_response(self, response_text: str, url: str) -> List[str]:
        """Parse search suggestions response based on the format."""
        try:
            # Try to parse as JSON first (most common format)
            data = json.loads(response_text)
            
            # Handle different response formats
            if isinstance(data, list):
                # Format: ["query", ["suggestion1", "suggestion2", ...]]
                if len(data) >= 2 and isinstance(data[1], list):
                    return data[1][:10]  # Limit to 10 suggestions
                # Format: ["suggestion1", "suggestion2", ...]
                elif all(isinstance(item, str) for item in data):
                    return data[:10]
            
            elif isinstance(data, dict):
                # Handle various dict formats
                if 'suggestions' in data:
                    suggestions = data['suggestions']
                    if isinstance(suggestions, list):
                        return [s.get('suggestion', '') if isinstance(s, dict) else str(s) for s in suggestions[:10]]
                
                elif 'results' in data:
                    results = data['results']
                    if isinstance(results, list):
                        return [r.get('text', '') if isinstance(r, dict) else str(r) for r in results[:10]]
                
                elif 'items' in data:
                    items = data['items']
                    if isinstance(items, list):
                        return [item.get('title', '') if isinstance(item, dict) else str(item) for item in items[:10]]
            
            debug_print(f"[DEBUG] Unrecognized suggestions format: {type(data)}")
            return []
            
        except json.JSONDecodeError:
            # Try to parse as other formats
            return self._parse_non_json_response(response_text, url)
    
    def _parse_non_json_response(self, response_text: str, url: str) -> List[str]:
        """Parse non-JSON response formats."""
        try:
            # Handle XML format (some engines use this)
            if response_text.strip().startswith('<'):
                return self._parse_xml_suggestions(response_text)
            
            # Handle plain text format (one suggestion per line)
            lines = response_text.strip().split('\n')
            if len(lines) > 1:
                return [line.strip() for line in lines if line.strip()][:10]
            
            # Handle CSV format
            if ',' in response_text:
                suggestions = [s.strip().strip('"') for s in response_text.split(',')]
                return suggestions[:10]
            
            debug_print(f"[DEBUG] Could not parse suggestions response format")
            return []
            
        except Exception as e:
            debug_print(f"[DEBUG] Error parsing non-JSON response: {e}")
            return []
    
    def _parse_xml_suggestions(self, xml_text: str) -> List[str]:
        """Parse XML suggestions format."""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(xml_text)
            
            suggestions = []
            
            # Look for common XML suggestion formats
            for suggestion in root.findall('.//suggestion'):
                text = suggestion.get('data') or suggestion.text
                if text:
                    suggestions.append(text)
            
            for item in root.findall('.//item'):
                text = item.get('text') or item.text
                if text:
                    suggestions.append(text)
            
            return suggestions[:10]
            
        except Exception as e:
            debug_print(f"[DEBUG] Error parsing XML suggestions: {e}")
            return []
    
    def get_suggestions_sync(self, query: str, suggestions_url: str) -> List[str]:
        """Get suggestions synchronously (for testing purposes)."""
        if not query.strip() or not suggestions_url:
            return []
        
        try:
            # Prepare the URL with the query
            encoded_query = urllib.parse.quote(query)
            url = suggestions_url.replace('%s', encoded_query)
            
            debug_print(f"[DEBUG] Fetching suggestions from: {url}")
            
            # Make the request
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse the response
            return self._parse_suggestions_response(response.text, url)
            
        except Exception as e:
            debug_print(f"[DEBUG] Error fetching suggestions: {e}")
            return []
    
    def test_suggestions_url(self, suggestions_url: str) -> bool:
        """Test if a suggestions URL is working."""
        try:
            test_query = "test"
            suggestions = self.get_suggestions_sync(test_query, suggestions_url)
            return isinstance(suggestions, list)
        except Exception:
            return False
    
    def get_popular_suggestions_formats(self) -> Dict[str, str]:
        """Get popular search engines' suggestion URL formats."""
        return {
            "Google": "https://suggestqueries.google.com/complete/search?client=firefox&q=%s",
            "Bing": "https://www.bing.com/osjson.aspx?query=%s",
            "DuckDuckGo": "https://duckduckgo.com/ac/?q=%s&type=list",
            "Yahoo": "https://search.yahoo.com/sugg/gossip/gossip-us-ura/?output=sd1&command=%s",
            "Startpage": None,  # Startpage doesn't provide suggestions API
            "Yandex": "https://suggest.yandex.com/suggest-ya.cgi?part=%s&lr=10393",
            "Baidu": "https://suggestion.baidu.com/su?wd=%s&cb=window.bdsug",
        }
    
    def validate_suggestions_url(self, url: str) -> bool:
        """Validate that a suggestions URL has the correct format."""
        if not url or not isinstance(url, str):
            return False
        
        # Check if URL contains the placeholder
        if '%s' not in url:
            return False
        
        # Check if URL starts with http/https
        if not url.startswith(('http://', 'https://')):
            return False
        
        return True