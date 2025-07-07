#!/usr/bin/env python3
"""
Omnibox entry widget for Seoltoir browser.
Enhanced address bar with autocomplete, search suggestions, and security indicators.
"""

import gi
import re
import time
import urllib.parse
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GObject, GLib, Gdk, Pango

from .debug import debug_print
from .search_suggestions_client import SearchSuggestionsClient


class SuggestionType:
    """Types of suggestions in the omnibox."""
    URL = "url"
    BOOKMARK = "bookmark"
    HISTORY = "history"
    SEARCH = "search"


class Suggestion:
    """A single suggestion item."""
    def __init__(self, text: str, url: str, suggestion_type: SuggestionType, 
                 title: str = "", favicon_url: str = ""):
        self.text = text
        self.url = url
        self.type = suggestion_type
        self.title = title
        self.favicon_url = favicon_url


class OmniboxEntry(Gtk.Box):
    """Enhanced address bar with autocomplete and suggestions."""
    
    __gsignals__ = {
        "navigate-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "suggestion-selected": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),  # url, title
    }
    
    def __init__(self, db_manager, search_engine_manager, *args, **kwargs):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, *args, **kwargs)
        
        print("[OMNIBOX-INIT] Starting OmniboxEntry initialization", flush=True)
        
        self.db_manager = db_manager
        self.search_engine_manager = search_engine_manager
        self.suggestions_client = SearchSuggestionsClient()
        
        # Current state
        self.current_suggestions = []
        self.selected_suggestion_index = -1
        self.is_showing_suggestions = False
        self.original_text = ""
        self.security_status = "none"  # none, secure, insecure, warning
        self.load_progress = 0.0
        
        # Setup UI
        self._setup_ui()
        self._setup_signals()
        
        print("[OMNIBOX-INIT] OmniboxEntry initialization complete", flush=True)
        debug_print("[OMNIBOX] OmniboxEntry initialized")
    
    def _setup_ui(self):
        """Set up the UI components."""
        # Main container with overlay for progress bar
        self.overlay = Gtk.Overlay()
        self.append(self.overlay)
        
        # Security icon
        self.security_icon = Gtk.Image()
        self.security_icon.set_from_icon_name("security-medium-symbolic")
        self.security_icon.set_visible(False)
        self.security_icon.set_margin_start(8)
        self.overlay.add_overlay(self.security_icon)
        self.security_icon.set_halign(Gtk.Align.START)
        self.security_icon.set_valign(Gtk.Align.CENTER)
        
        # Progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_visible(False)
        self.progress_bar.add_css_class("osd")
        self.progress_bar.set_valign(Gtk.Align.END)
        self.progress_bar.set_hexpand(True)
        self.progress_bar.set_margin_bottom(2)
        self.progress_bar.set_margin_start(2)
        self.progress_bar.set_margin_end(2)
        self.overlay.add_overlay(self.progress_bar)
        
        # Main entry widget
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text("Enter URL or search")
        self.entry.set_hexpand(True)
        self.overlay.set_child(self.entry)
        
        # Suggestions popover
        self.suggestions_popover = Gtk.Popover()
        self.suggestions_popover.set_parent(self.entry)
        self.suggestions_popover.set_position(Gtk.PositionType.BOTTOM)
        self.suggestions_popover.set_autohide(False)  # We'll control this manually
        
        # Suggestions list
        self.suggestions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.suggestions_scrolled = Gtk.ScrolledWindow()
        self.suggestions_scrolled.set_max_content_height(400)  # Increased height
        self.suggestions_scrolled.set_min_content_width(500)   # Set minimum width
        self.suggestions_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.suggestions_scrolled.set_child(self.suggestions_box)
        self.suggestions_popover.set_child(self.suggestions_scrolled)
        
        # Make popover wider to match the entry width
        self.suggestions_popover.set_size_request(500, -1)
        
        # Style the entry to accommodate security icon
        self.entry.set_margin_start(32)  # Space for security icon
    
    def _setup_signals(self):
        """Set up signal connections."""
        # Entry signals
        self.entry.connect("changed", self._on_text_changed)
        self.entry.connect("activate", self._on_activate)
        
        # Key events for navigation
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_key_pressed)
        self.entry.add_controller(key_controller)
        
        # Focus events (GTK4 style)
        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("enter", self._on_focus_in)
        focus_controller.connect("leave", self._on_focus_out)
        self.entry.add_controller(focus_controller)
        
        debug_print("[OMNIBOX] Signal connections set up")
    
    def _on_text_changed(self, entry):
        """Handle text changes in the entry."""
        text = entry.get_text().strip()
        
        # Only show suggestions if the entry has focus
        if entry.has_focus():
            # Always fetch suggestions when focused, even for empty text
            GLib.timeout_add(300, self._fetch_suggestions, text)
        else:
            self._hide_suggestions()
    
    def _on_activate(self, entry):
        """Handle Enter key press."""
        if self.selected_suggestion_index >= 0 and self.current_suggestions:
            # Use selected suggestion
            suggestion = self.current_suggestions[self.selected_suggestion_index]
            self._select_suggestion(suggestion)
        else:
            # Use current text
            text = entry.get_text().strip()
            if text:
                url = self._process_input(text)
                self.emit("navigate-requested", url)
        
        self._hide_suggestions()
    
    def _on_focus_in(self, controller=None):
        """Handle focus in event."""
        print("[OMNIBOX-FOCUS] Focus IN event triggered", flush=True)
        debug_print("[OMNIBOX] Focus IN event triggered")
        
        # Force grab focus on the entry
        print(f"[OMNIBOX-FOCUS] Before grab_focus: Entry has focus: {self.entry.has_focus()}", flush=True)
        print(f"[OMNIBOX-FOCUS] Entry can focus: {self.entry.get_can_focus()}", flush=True)
        print(f"[OMNIBOX-FOCUS] Entry is sensitive: {self.entry.get_sensitive()}", flush=True)
        print(f"[OMNIBOX-FOCUS] Entry is visible: {self.entry.get_visible()}", flush=True)
        
        self.entry.grab_focus()
        print(f"[OMNIBOX-FOCUS] After grab_focus: Entry has focus: {self.entry.has_focus()}", flush=True)
        
        # Show full URL when focused
        if hasattr(self, '_formatted_url'):
            print(f"[OMNIBOX-FOCUS] Setting formatted URL: {self._formatted_url}", flush=True)
            debug_print(f"[OMNIBOX] Setting formatted URL: {self._formatted_url}")
            self.entry.set_text(self._formatted_url)
        
        # Try multiple methods to select text
        print(f"[OMNIBOX-FOCUS] Entry has focus: {self.entry.has_focus()}", flush=True)
        
        # Method 1: Direct selection
        try:
            self.entry.select_region(0, -1)
            print("[OMNIBOX-FOCUS] Direct text selection attempted", flush=True)
        except Exception as e:
            print(f"[OMNIBOX-FOCUS] Direct selection failed: {e}", flush=True)
        
        # Method 2: Delayed selection with multiple attempts
        GLib.timeout_add(10, self._select_all_text_retry, 0)
        GLib.timeout_add(50, self._select_all_text_retry, 1)
        GLib.timeout_add(100, self._select_all_text_retry, 2)
        
        # Show suggestions - always show for focused entry (including empty)
        text = self.entry.get_text().strip()
        print(f"[OMNIBOX-FOCUS] Fetching suggestions for text: '{text}'", flush=True)
        debug_print(f"[OMNIBOX] Fetching suggestions for text: '{text}'")
        GLib.timeout_add(100, self._fetch_suggestions, text)
    
    def _select_all_text(self):
        """Select all text in the entry (called via idle_add)."""
        print("[OMNIBOX-SELECT] _select_all_text called", flush=True)
        debug_print("[OMNIBOX] _select_all_text called")
        if self.entry.has_focus():
            print("[OMNIBOX-SELECT] Entry has focus, selecting all text", flush=True)
            debug_print("[OMNIBOX] Entry has focus, selecting all text")
            self.entry.select_region(0, -1)
        else:
            print("[OMNIBOX-SELECT] Entry does not have focus", flush=True)
            debug_print("[OMNIBOX] Entry does not have focus")
        return False  # Don't repeat
    
    def _select_all_text_retry(self, attempt):
        """Retry text selection with debugging."""
        print(f"[OMNIBOX-RETRY] Attempt {attempt}: Entry has focus: {self.entry.has_focus()}", flush=True)
        if self.entry.has_focus():
            try:
                self.entry.select_region(0, -1)
                print(f"[OMNIBOX-RETRY] Attempt {attempt}: Text selection successful", flush=True)
                return False  # Success, don't retry
            except Exception as e:
                print(f"[OMNIBOX-RETRY] Attempt {attempt}: Selection failed: {e}", flush=True)
        return False  # Don't repeat
    
    def _on_focus_out(self, controller=None):
        """Handle focus out event."""
        debug_print("[OMNIBOX] Focus OUT event triggered")
        # Format URL when not focused
        GLib.timeout_add(100, self._hide_suggestions)
        self._format_displayed_url()
    
    def _on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events for navigation."""
        if keyval == Gdk.KEY_Down:
            if self.is_showing_suggestions:
                self._move_selection(1)
                return True
        elif keyval == Gdk.KEY_Up:
            if self.is_showing_suggestions:
                self._move_selection(-1)
                return True
        elif keyval == Gdk.KEY_Escape:
            if self.is_showing_suggestions:
                self._hide_suggestions()
                self.entry.set_text(self.original_text)
                return True
        elif keyval == Gdk.KEY_Tab:
            if self.is_showing_suggestions and self.selected_suggestion_index >= 0:
                # Tab to complete with selected suggestion
                suggestion = self.current_suggestions[self.selected_suggestion_index]
                self.entry.set_text(suggestion.text)
                self.entry.set_position(-1)  # Move cursor to end
                return True
        
        return False
    
    def _move_selection(self, direction):
        """Move selection up or down in suggestions."""
        if not self.current_suggestions:
            return
        
        old_index = self.selected_suggestion_index
        
        if direction > 0:  # Down
            if self.selected_suggestion_index < len(self.current_suggestions) - 1:
                self.selected_suggestion_index += 1
            else:
                self.selected_suggestion_index = -1  # Back to original text
        else:  # Up
            if self.selected_suggestion_index > -1:
                self.selected_suggestion_index -= 1
            else:
                self.selected_suggestion_index = len(self.current_suggestions) - 1
        
        # Update UI
        self._update_suggestion_selection(old_index)
        
        # Update entry text
        if self.selected_suggestion_index >= 0:
            suggestion = self.current_suggestions[self.selected_suggestion_index]
            self.entry.set_text(suggestion.text)
        else:
            self.entry.set_text(self.original_text)
        
        self.entry.set_position(-1)  # Move cursor to end
    
    def _fetch_suggestions(self, query):
        """Fetch and display suggestions for the given query."""
        print(f"[OMNIBOX-SUGGEST] _fetch_suggestions called with query: '{query}'", flush=True)
        debug_print(f"[OMNIBOX] _fetch_suggestions called with query: '{query}'")
        
        # Allow empty queries, but check if text has changed for non-empty queries
        current_text = self.entry.get_text().strip()
        if query and query != current_text:
            print(f"[OMNIBOX-SUGGEST] Query changed from '{query}' to '{current_text}', aborting", flush=True)
            debug_print(f"[OMNIBOX] Query changed from '{query}' to '{current_text}', aborting")
            return False  # Text has changed, abort
        
        # Only fetch suggestions if the entry has focus
        if not self.entry.has_focus():
            print("[OMNIBOX-SUGGEST] Entry does not have focus, aborting suggestions", flush=True)
            debug_print("[OMNIBOX] Entry does not have focus, aborting suggestions")
            return False
        
        print("[OMNIBOX-SUGGEST] Entry has focus, proceeding with suggestions", flush=True)
        debug_print("[OMNIBOX] Entry has focus, proceeding with suggestions")
        self.original_text = query
        suggestions = []
        
        # Get history suggestions
        history_suggestions = self._get_history_suggestions(query)
        print(f"[OMNIBOX-SUGGEST] Got {len(history_suggestions)} history suggestions", flush=True)
        debug_print(f"[OMNIBOX] Got {len(history_suggestions)} history suggestions")
        suggestions.extend(history_suggestions)
        
        # Get bookmark suggestions  
        bookmark_suggestions = self._get_bookmark_suggestions(query)
        print(f"[OMNIBOX-SUGGEST] Got {len(bookmark_suggestions)} bookmark suggestions", flush=True)
        debug_print(f"[OMNIBOX] Got {len(bookmark_suggestions)} bookmark suggestions")
        suggestions.extend(bookmark_suggestions)
        
        # Add search suggestions (async) - only for non-empty, non-URL queries
        if query and not self._is_url(query):
            self._fetch_search_suggestions(query, suggestions)
        
        # Show current suggestions
        print(f"[OMNIBOX-SUGGEST] Total suggestions: {len(suggestions)}", flush=True)
        debug_print(f"[OMNIBOX] Total suggestions: {len(suggestions)}")
        self._show_suggestions(suggestions)
        
        return False  # Don't repeat timeout
    
    def _get_history_suggestions(self, query):
        """Get suggestions from browsing history."""
        debug_print(f"[OMNIBOX] _get_history_suggestions called with query: '{query}'")
        suggestions = []
        
        try:
            # Get more history entries to show comprehensive history
            history_entries = self.db_manager.get_history(limit=100)
            debug_print(f"[OMNIBOX] Retrieved {len(history_entries)} history entries from database")
            query_lower = query.lower()
            
            # If query is empty, show recent history
            if not query.strip():
                debug_print("[OMNIBOX] Query is empty, showing recent history")
                for url, title, _ in history_entries[:10]:  # Show top 10 recent
                    debug_print(f"[OMNIBOX] Adding recent history: {url}")
                    suggestions.append(Suggestion(
                        text=url,
                        url=url,
                        suggestion_type=SuggestionType.HISTORY,
                        title=title or url
                    ))
            else:
                debug_print(f"[OMNIBOX] Query is not empty, filtering by: '{query_lower}'")
                # Filter by query
                for url, title, _ in history_entries:
                    if (query_lower in url.lower() or 
                        (title and query_lower in title.lower())):
                        debug_print(f"[OMNIBOX] Adding filtered history: {url}")
                        suggestions.append(Suggestion(
                            text=url,
                            url=url,
                            suggestion_type=SuggestionType.HISTORY,
                            title=title or url
                        ))
                        
                        if len(suggestions) >= 8:  # Increased limit for better history
                            break
        except Exception as e:
            debug_print(f"[OMNIBOX] Error getting history suggestions: {e}")
            import traceback
            debug_print(f"[OMNIBOX] Traceback: {traceback.format_exc()}")
        
        debug_print(f"[OMNIBOX] Returning {len(suggestions)} history suggestions")
        return suggestions
    
    def _get_bookmark_suggestions(self, query):
        """Get suggestions from bookmarks."""
        suggestions = []
        
        try:
            bookmarks = self.db_manager.get_bookmarks()
            query_lower = query.lower()
            
            for url, title, _ in bookmarks:
                if (query_lower in url.lower() or 
                    (title and query_lower in title.lower())):
                    suggestions.append(Suggestion(
                        text=url,
                        url=url,
                        suggestion_type=SuggestionType.BOOKMARK,
                        title=title or url
                    ))
                    
                    if len(suggestions) >= 3:  # Limit bookmark suggestions
                        break
        except Exception as e:
            debug_print(f"[OMNIBOX] Error getting bookmark suggestions: {e}")
        
        return suggestions
    
    def _fetch_search_suggestions(self, query, current_suggestions):
        """Fetch search suggestions from search engine."""
        try:
            default_engine = self.search_engine_manager.get_default_engine()
            if default_engine and default_engine.get("suggestions_url"):
                suggestions_url = default_engine["suggestions_url"]
                self.suggestions_client.fetch_suggestions(
                    query, suggestions_url, 
                    self._on_search_suggestions_received,
                    (query, current_suggestions)
                )
        except Exception as e:
            debug_print(f"[OMNIBOX] Error fetching search suggestions: {e}")
    
    def _on_search_suggestions_received(self, search_suggestions, user_data):
        """Handle received search suggestions."""
        if not user_data:
            return
        
        query, current_suggestions = user_data
        
        # Check if query is still current
        if query != self.original_text:
            return
        
        # Add search suggestions
        for suggestion_text in search_suggestions[:5]:  # Limit to 5
            current_suggestions.append(Suggestion(
                text=suggestion_text,
                url=self._get_search_url(suggestion_text),
                suggestion_type=SuggestionType.SEARCH,
                title=f"Search for '{suggestion_text}'"
            ))
        
        # Update suggestions display
        self._show_suggestions(current_suggestions)
    
    def _show_suggestions(self, suggestions):
        """Display suggestions in the popover."""
        debug_print(f"[OMNIBOX] _show_suggestions called with {len(suggestions)} suggestions")
        self.current_suggestions = suggestions
        self.selected_suggestion_index = -1
        
        # Clear existing suggestions
        child = self.suggestions_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.suggestions_box.remove(child)
            child = next_child
        
        if not suggestions:
            debug_print("[OMNIBOX] No suggestions, hiding popover")
            self._hide_suggestions()
            return
        
        # Add suggestion rows
        for i, suggestion in enumerate(suggestions):
            debug_print(f"[OMNIBOX] Adding suggestion {i}: {suggestion.text}")
            row = self._create_suggestion_row(suggestion, i)
            self.suggestions_box.append(row)
        
        # Show popover
        if not self.is_showing_suggestions:
            debug_print("[OMNIBOX] Showing popover")
            self.suggestions_popover.popup()
            self.is_showing_suggestions = True
        else:
            debug_print("[OMNIBOX] Popover already showing")
    
    def _create_suggestion_row(self, suggestion, index):
        """Create a suggestion row widget."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_top(8)   # Increased margins
        row.set_margin_bottom(8)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_size_request(-1, 48)  # Set minimum row height
        
        # Icon based on suggestion type
        icon = Gtk.Image()
        icon.set_pixel_size(20)  # Make icons slightly larger
        if suggestion.type == SuggestionType.BOOKMARK:
            icon.set_from_icon_name("starred-symbolic")
        elif suggestion.type == SuggestionType.HISTORY:
            icon.set_from_icon_name("document-open-recent-symbolic")
        elif suggestion.type == SuggestionType.SEARCH:
            icon.set_from_icon_name("edit-find-symbolic")
        else:
            icon.set_from_icon_name("applications-internet-symbolic")
        
        row.append(icon)
        
        # Text content
        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        text_box.set_hexpand(True)
        
        # Main text
        main_label = Gtk.Label()
        main_label.set_halign(Gtk.Align.START)
        main_label.set_ellipsize(Pango.EllipsizeMode.END)
        main_label.set_size_request(-1, 20)  # Set label height
        # Escape text to prevent markup issues
        import html
        escaped_text = html.escape(suggestion.text)
        main_label.set_markup(f"<span size='medium'><b>{escaped_text}</b></span>")  # Make text bold and larger
        text_box.append(main_label)
        
        # Subtitle (title or URL)
        if suggestion.title and suggestion.title != suggestion.text:
            subtitle_label = Gtk.Label()
            subtitle_label.set_halign(Gtk.Align.START)
            subtitle_label.set_ellipsize(Pango.EllipsizeMode.END)
            subtitle_label.set_size_request(-1, 16)  # Set subtitle height
            subtitle_label.add_css_class("dim-label")
            # Use markup for better readability
            escaped_title = html.escape(suggestion.title)
            subtitle_label.set_markup(f"<span size='small' alpha='70%'>{escaped_title}</span>")
            text_box.append(subtitle_label)
        
        row.append(text_box)
        
        # Click handler
        gesture = Gtk.GestureClick()
        gesture.connect("pressed", self._on_suggestion_clicked, suggestion)
        row.add_controller(gesture)
        
        # Hover effect
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("enter", self._on_suggestion_hover_enter, row)
        motion_controller.connect("leave", self._on_suggestion_hover_leave, row)
        row.add_controller(motion_controller)
        
        # Store index for selection highlighting
        row.suggestion_index = index
        
        return row
    
    def _on_suggestion_hover_enter(self, controller, x, y, row):
        """Handle mouse hover enter on suggestion."""
        row.add_css_class("hover")
    
    def _on_suggestion_hover_leave(self, controller, row):
        """Handle mouse hover leave on suggestion."""
        row.remove_css_class("hover")
    
    def _on_suggestion_clicked(self, gesture, n_press, x, y, suggestion):
        """Handle suggestion click."""
        self._select_suggestion(suggestion)
    
    def _select_suggestion(self, suggestion):
        """Select and navigate to a suggestion."""
        self.entry.set_text(suggestion.text)
        self.emit("suggestion-selected", suggestion.url, suggestion.title)
        self.emit("navigate-requested", suggestion.url)
        self._hide_suggestions()
    
    def _hide_suggestions(self):
        """Hide the suggestions popover."""
        if self.is_showing_suggestions:
            self.suggestions_popover.popdown()
            self.is_showing_suggestions = False
        self.selected_suggestion_index = -1
    
    def _update_suggestion_selection(self, old_index):
        """Update visual selection in suggestions."""
        # Remove old selection
        if old_index >= 0:
            child = self.suggestions_box.get_first_child()
            for i in range(old_index):
                if child:
                    child = child.get_next_sibling()
            if child:
                child.remove_css_class("suggested-action")
                child.remove_css_class("accent")
        
        # Add new selection
        if self.selected_suggestion_index >= 0:
            child = self.suggestions_box.get_first_child()
            for i in range(self.selected_suggestion_index):
                if child:
                    child = child.get_next_sibling()
            if child:
                child.add_css_class("suggested-action")
                child.add_css_class("accent")  # Better highlighting
    
    def _is_url(self, text):
        """Check if text looks like a URL."""
        # Check for common URL patterns
        url_patterns = [
            r'^https?://',
            r'^ftp://',
            r'^file://',
            r'^\w+\.\w+',  # domain.tld
            r'localhost',
            r'^\d+\.\d+\.\d+\.\d+',  # IP address
        ]
        
        text_lower = text.lower()
        for pattern in url_patterns:
            if re.match(pattern, text_lower):
                return True
        
        # Check if it contains a dot and looks like a domain
        if '.' in text and ' ' not in text and not text.startswith('/'):
            parts = text.split('.')
            if len(parts) >= 2 and all(len(part) > 0 for part in parts):
                return True
        
        return False
    
    def _process_input(self, text):
        """Process user input and return appropriate URL."""
        if self._is_url(text):
            # It's a URL, add protocol if missing
            if not any(text.startswith(scheme) for scheme in ['http://', 'https://', 'file://', 'ftp://']):
                return f"https://{text}"
            return text
        else:
            # It's a search query
            return self._get_search_url(text)
    
    def _get_search_url(self, query):
        """Get search URL for a query using the default search engine."""
        try:
            default_engine = self.search_engine_manager.get_default_engine()
            if default_engine:
                return default_engine["url"].replace("%s", urllib.parse.quote(query))
        except Exception as e:
            debug_print(f"[OMNIBOX] Error getting search URL: {e}")
        
        # Fallback to DuckDuckGo
        return f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
    
    def _format_displayed_url(self):
        """Format the displayed URL when not focused."""
        text = self.entry.get_text()
        if not text:
            return
        
        # Store the full URL
        self._formatted_url = text
        
        # For display, we could hide https:// and www.
        display_text = text
        if display_text.startswith("https://"):
            display_text = display_text[8:]
        if display_text.startswith("www."):
            display_text = display_text[4:]
        
        # Only update if the entry doesn't have focus
        if not self.entry.has_focus():
            self.entry.set_text(display_text)
    
    # Public methods for external control
    
    def set_url(self, url):
        """Set the URL in the omnibox."""
        self.entry.set_text(url)
        self._formatted_url = url
        self._update_security_status(url)
        if not self.entry.has_focus():
            self._format_displayed_url()
    
    def get_text(self):
        """Get the current text in the omnibox."""
        return self.entry.get_text()
    
    def set_text(self, text):
        """Set the text in the omnibox."""
        self.entry.set_text(text)
    
    def grab_focus(self):
        """Focus the omnibox entry."""
        print("[OMNIBOX-PUBLIC] grab_focus() called", flush=True)
        print(f"[OMNIBOX-PUBLIC] Before grab_focus: Entry has focus: {self.entry.has_focus()}", flush=True)
        self.entry.grab_focus()
        print(f"[OMNIBOX-PUBLIC] After grab_focus: Entry has focus: {self.entry.has_focus()}", flush=True)
    
    def has_focus(self):
        """Check if the omnibox has focus."""
        return self.entry.has_focus()
    
    def select_all(self):
        """Select all text in the omnibox."""
        self.entry.select_region(0, -1)
    
    def set_progress(self, progress):
        """Set the load progress (0.0 to 1.0)."""
        self.load_progress = progress
        
        if progress > 0.0 and progress < 1.0:
            self.progress_bar.set_fraction(progress)
            self.progress_bar.set_visible(True)
        else:
            self.progress_bar.set_visible(False)
    
    def _update_security_status(self, url):
        """Update security status based on URL."""
        if url.startswith("https://"):
            self.security_status = "secure"
            self.security_icon.set_from_icon_name("security-high-symbolic")
            self.security_icon.set_visible(True)
            self.security_icon.set_tooltip_text("Secure connection (HTTPS)")
        elif url.startswith("http://"):
            self.security_status = "insecure"
            self.security_icon.set_from_icon_name("security-low-symbolic")
            self.security_icon.set_visible(True)
            self.security_icon.set_tooltip_text("Not secure (HTTP)")
        else:
            self.security_status = "none"
            self.security_icon.set_visible(False)
    
    def set_security_warning(self, has_warning, message=""):
        """Set security warning status."""
        if has_warning:
            self.security_status = "warning"
            self.security_icon.set_from_icon_name("dialog-warning-symbolic")
            self.security_icon.set_visible(True)
            self.security_icon.set_tooltip_text(message or "Security warning")
        else:
            self._update_security_status(self.entry.get_text())