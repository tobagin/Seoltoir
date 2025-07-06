import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GObject

from .database import DatabaseManager
from .ui_loader import UILoader

class HistoryManager(Gtk.Box):
    __gsignals__ = {
        "open-url-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    def __init__(self, db_manager: DatabaseManager, *args, **kwargs):
        builder = Gtk.Builder()
        builder.add_from_file(UILoader.get_ui_file_path('history-manager.ui'))
        box = builder.get_object('history_manager')
        super().__init__(orientation=box.get_orientation(), spacing=box.get_spacing(), *args, **kwargs)
        child = box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            box.remove(child)
            self.append(child)
            child = next_child

        self.db_manager = db_manager

        # Get references to UI widgets
        self.clear_button = builder.get_object('clear_button')
        self.search_entry = builder.get_object('search_entry')
        self.history_listbox = builder.get_object('history_listbox')
        
        # Connect signals
        self.clear_button.connect("clicked", self._on_clear_history_clicked)
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.history_listbox.connect("row-activated", self._on_row_activated)
        self.history_listbox.set_filter_func(self._filter_history) # For search

        self.load_history()

    def load_history(self):
        """Loads history entries from the database and populates the listbox."""
        child = self.history_listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.history_listbox.remove(child)
            child = next_child

        history_data = self.db_manager.get_history()
        for url, title, last_visit_str in history_data:
            row = Adw.ActionRow.new()
            row.set_title(title or url)
            row.set_subtitle(url)
            # You might want to format last_visit_str here
            row.set_extra_child(Gtk.Label.new(f"Visited: {last_visit_str[:16]}")) # Truncate for display
            row.set_activatable(True) # Make row clickable
            row.set_attribute("url", url) # Store URL as an attribute for easy retrieval
            self.history_listbox.append(row)
        self.history_listbox.invalidate_filter() # Apply filter after loading

    def _on_row_activated(self, listbox, row):
        """Emits a signal when a history entry is clicked."""
        url = row.get_attribute("url")
        if url:
            self.emit("open-url-requested", url)
            self.get_parent().pop_page() # Go back to the browser window

    def _on_clear_history_clicked(self, button):
        """Clears all history entries and reloads the view."""
        self.db_manager.clear_history()
        self.load_history() # Refresh the list

    def _on_search_changed(self, entry):
        self.history_listbox.invalidate_filter()

    def _filter_history(self, row):
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        
        title = row.get_title().lower()
        subtitle = row.get_subtitle().lower()
        
        return query in title or query in subtitle
