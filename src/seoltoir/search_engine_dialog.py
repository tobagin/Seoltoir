# seoltoir/seoltoir/search_engine_dialog.py

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from .ui_loader import UILoader

class SearchEngineDialog(Adw.Dialog):
    def __init__(self, application, search_engine_data: dict = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_application(application)
        self.set_modal(True)
        
        self.search_engine_data = search_engine_data # Existing data if editing
        
        # Load UI from file
        self.dialog, self.builder = UILoader.load_dialog('search-engine-dialog.ui', 'SearchEngineDialog', parent=self.get_root())
        
        # Get references to UI widgets
        self.name_entry = self.builder.get_object('name_entry')
        self.url_entry = self.builder.get_object('url_entry')
        self.window_title = self.builder.get_object('window_title')
        
        # Set up dialog responses
        if search_engine_data:
            self.window_title.set_title("Edit Search Engine")
            self.add_response("cancel", "Cancel")
            self.add_response("save", "Save")
            self.set_default_response("save")
        else:
            self.window_title.set_title("Add Search Engine")
            self.add_response("cancel", "Cancel")
            self.add_response("add", "Add")
            self.set_default_response("add")
        
        self.set_close_response("cancel")

        # Set up dialog content
        content_box = self.builder.get_object('content_box')
        self.set_child(content_box)

        # Populate if editing
        if search_engine_data:
            self.name_entry.set_text(search_engine_data.get("name", ""))
            self.url_entry.set_text(search_engine_data.get("url", ""))

        self.connect("response", self._on_response)

    def _on_response(self, dialog, response_id):
        if response_id in ["add", "save"]:
            name = self.name_entry.get_text().strip()
            url = self.url_entry.get_text().strip()
            
            if not name or not url:
                print("Name and URL cannot be empty.")
                # Show an error toast
                if self.get_application().get_window_by_id(1) and hasattr(self.get_application().get_window_by_id(1), 'toast_overlay'):
                    self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new("Name and URL cannot be empty!"))
                return # Keep dialog open

            # Emit a custom signal with the data, so the caller can handle saving to GSettings
            self.emit("search-engine-configured", name, url, self.search_engine_data is None) # True if adding, False if editing

        dialog.destroy()

# Define signal for SearchEngineDialog
GLib.GObject.type_register(SearchEngineDialog)
SearchEngineDialog.connect_signals({
    "search-engine-configured": (GLib.SignalFlags.RUN_FIRST, None, (str, str, bool,)), # name, url, is_new
})
