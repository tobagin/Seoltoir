# seoltoir/seoltoir/clear_data_dialog.py

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, Adw, Gio, GLib, WebKit

from .database import DatabaseManager # To clear history/bookmarks
from .ui_loader import UILoader
from .debug import debug_print
import os

class ClearBrowsingDataDialog(Adw.Dialog):
    def __init__(self, application, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.application = application
        self.set_default_size(400, 300)

        self.db_manager: DatabaseManager = application.db_manager
        self.web_context = WebKit.WebContext.get_default() # For cache/cookies

        # Load UI from file
        self.dialog, self.builder = UILoader.load_dialog('clear-data-dialog.ui', 'ClearBrowsingDataDialog', parent=self.get_root())
        
        # Get references to UI widgets
        self.time_range_dropdown = self.builder.get_object('time_range_dropdown')
        self.check_history = self.builder.get_object('check_history')
        self.check_cookies = self.builder.get_object('check_cookies')
        self.check_cache = self.builder.get_object('check_cache')
        self.check_downloads = self.builder.get_object('check_downloads')
        
        # Set up dialog responses
        self.add_response("cancel", "Cancel")
        self.add_response("clear", "Clear Data")
        self.set_default_response("clear")
        self.set_close_response("cancel")

        # Set up dialog content
        content_box = self.builder.get_object('content_box')
        self.set_child(content_box)

        # Set up time range dropdown
        time_range_model = Gtk.StringList.new(["All Time"])
        self.time_range_dropdown.set_model(time_range_model)
        self.time_range_dropdown.set_selected(0) # Default to All Time

        # Connect response handler
        self.connect("response", self._on_response)

    def _on_response(self, dialog, response_id):
        if response_id == "clear":
            print("Clearing data...")
            if self.check_history.get_active():
                self.db_manager.clear_history()
            if self.check_cookies.get_active():
                self._clear_cookies_and_site_data()
            if self.check_cache.get_active():
                self._clear_cache()
            if self.check_downloads.get_active():
                # In this simple model, download history is part of `DownloadManager`'s internal list
                # or just the files on disk. For now, we clear the list.
                self.application.download_manager._on_clear_completed_clicked(None) # Reuse existing clear logic
                print("Download history cleared (from UI).") # This only clears the UI list, not actual files
            print("Data clearing complete.")
            # Optionally show a toast notification
            self.application.get_window_by_id(1)._on_show_notification(
                None, "Selected browsing data cleared."
            )
        dialog.destroy()

    def _clear_cookies_and_site_data(self):
        # Clear cookies from all containers
        app = self.get_application()
        if hasattr(app, 'container_manager'):
            # Clear cookies from all containers
            for container_id in app.container_manager.container_contexts:
                context = app.container_manager.container_contexts[container_id]
                network_session = app.container_manager.container_network_sessions[container_id]
                cookie_manager = network_session.get_cookie_manager()
                cookie_manager.remove_all_cookies()
                debug_print(f"Cleared cookies from container: {container_id}")
        else:
            # Fallback to default context
        cookie_manager = self.web_context.get_cookie_manager()
        cookie_manager.remove_all_cookies()
            debug_print("Cleared cookies from default context")
        
        # Clear other site data from all containers
        app = self.get_application()
        if hasattr(app, 'container_manager'):
            for container_id in app.container_manager.container_contexts:
                context = app.container_manager.container_contexts[container_id]
                data_manager = context.get_website_data_manager()
                
                # Define the types of data to clear
                types_to_clear = WebKit.WebsiteDataTypes.DISK_CACHE | \
                                 WebKit.WebsiteDataTypes.MEMORY_CACHE | \
                                 WebKit.WebsiteDataTypes.OFFLINE_WEB_APPLICATION_CACHE | \
                                 WebKit.WebsiteDataTypes.LOCAL_STORAGE | \
                                 WebKit.WebsiteDataTypes.INDEXEDDB_DATABASES | \
                                 WebKit.WebsiteDataTypes.WEBSQL_DATABASES | \
                                 WebKit.WebsiteDataTypes.PLUGINS_DATA | \
                                 WebKit.WebsiteDataTypes.NETWORK_CACHE | \
                                 WebKit.WebsiteDataTypes.DEVICE_SPECIFIC_MEDIA_DEVICES_DATA | \
                                 WebKit.WebsiteDataTypes.FILE_SYSTEM_DATA | \
                                 WebKit.WebsiteDataTypes.WEBSQL_DATABASES
                
                start_time = 0  # Unix epoch for "All Time"
                data_manager.clear(types_to_clear, start_time, None, None)
                debug_print(f"Cleared site data from container: {container_id}")
        else:
            # Fallback to default context
        data_manager = self.web_context.get_website_data_manager()
        types_to_clear = WebKit.WebsiteDataTypes.DISK_CACHE | \
                         WebKit.WebsiteDataTypes.MEMORY_CACHE | \
                         WebKit.WebsiteDataTypes.OFFLINE_WEB_APPLICATION_CACHE | \
                         WebKit.WebsiteDataTypes.LOCAL_STORAGE | \
                         WebKit.WebsiteDataTypes.INDEXEDDB_DATABASES | \
                         WebKit.WebsiteDataTypes.WEBSQL_DATABASES | \
                         WebKit.WebsiteDataTypes.PLUGINS_DATA | \
                         WebKit.WebsiteDataTypes.NETWORK_CACHE | \
                         WebKit.WebsiteDataTypes.DEVICE_SPECIFIC_MEDIA_DEVICES_DATA | \
                         WebKit.WebsiteDataTypes.FILE_SYSTEM_DATA | \
                             WebKit.WebsiteDataTypes.WEBSQL_DATABASES
            
            start_time = 0
            data_manager.clear(types_to_clear, start_time, None, None)
            debug_print("Cleared site data from default context")
        
        debug_print("Cookies and site data cleared from all containers.")

    def _clear_cache(self):
        # Clear cache from all containers
        app = self.get_application()
        if hasattr(app, 'container_manager'):
            for container_id in app.container_manager.container_contexts:
                context = app.container_manager.container_contexts[container_id]
                data_manager = context.get_website_data_manager()
        
        types_to_clear = WebKit.WebsiteDataTypes.DISK_CACHE | WebKit.WebsiteDataTypes.MEMORY_CACHE
                data_manager.clear(types_to_clear, 0, None, None)
                debug_print(f"Cleared cache from container: {container_id}")
        else:
            # Fallback to default context
            data_manager = self.web_context.get_website_data_manager()
            types_to_clear = WebKit.WebsiteDataTypes.DISK_CACHE | WebKit.WebsiteDataTypes.MEMORY_CACHE
        data_manager.clear(types_to_clear, 0, None, None)
            debug_print("Cleared cache from default context")
        
        debug_print("Cache cleared from all containers.")
