import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GObject

from .database import DatabaseManager
from .ui_loader import UILoader

class BookmarkManager(Gtk.Box):
    __gsignals__ = {
        "open-url-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }
    def __init__(self, db_manager: DatabaseManager, *args, **kwargs):
        builder = Gtk.Builder()
        builder.add_from_file(UILoader.get_ui_file_path('bookmark-manager.ui'))
        box = builder.get_object('bookmark_manager')
        super().__init__(orientation=box.get_orientation(), spacing=box.get_spacing(), *args, **kwargs)
        for child in box.get_children():
            self.append(child)

        self.db_manager = db_manager

        # Get references to UI widgets
        self.search_entry = builder.get_object('search_entry')
        self.bookmark_listbox = builder.get_object('bookmark_listbox')
        
        # Connect signals
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.bookmark_listbox.connect("row-activated", self._on_row_activated)
        self.bookmark_listbox.set_filter_func(self._filter_bookmarks) # For search

        self.load_bookmarks()

    def load_bookmarks(self):
        """Loads bookmark entries from the database and populates the listbox."""
        for child in self.bookmark_listbox.get_children():
            self.bookmark_listbox.remove(child)

        bookmark_data = self.db_manager.get_bookmarks()
        for url, title, added_date_str in bookmark_data:
            row = Adw.ActionRow.new()
            row.set_title(title)
            row.set_subtitle(url)
            row.set_extra_child(Gtk.Label.new(f"Added: {added_date_str[:10]}"))
            row.set_activatable(True)
            row.set_attribute("url", url)

            # Add a remove button for each bookmark
            remove_button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
            remove_button.set_tooltip_text("Remove bookmark")
            remove_button.connect("clicked", self._on_remove_bookmark_clicked, url)
            row.add_suffix(remove_button)

            self.bookmark_listbox.append(row)
        self.bookmark_listbox.invalidate_filter()

    def _on_row_activated(self, listbox, row):
        """Emits a signal when a bookmark entry is clicked."""
        url = row.get_attribute("url")
        if url:
            self.emit("open-url-requested", url)
            self.get_parent().pop_page() # Go back to the browser window

    def _on_remove_bookmark_clicked(self, button, url):
        """Removes a bookmark from the database and refreshes the view."""
        self.db_manager.remove_bookmark(url)
        self.load_bookmarks() # Refresh the list

    def _on_search_changed(self, entry):
        self.bookmark_listbox.invalidate_filter()

    def _filter_bookmarks(self, row):
        query = self.search_entry.get_text().strip().lower()
        if not query:
            return True
        
        title = row.get_title().lower()
        subtitle = row.get_subtitle().lower()
        
        return query in title or query in subtitle
