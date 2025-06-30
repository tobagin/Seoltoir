# seoltoir/seoltoir/import_export_dialog.py

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from .ui_loader import UILoader
import json
import csv
import os
from datetime import datetime

class ImportExportDialog(Adw.PreferencesWindow):
    def __init__(self, application, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_application(application)
        self.set_default_size(600, 400)

        self.db_manager = application.db_manager
        self.settings = Gio.Settings.new(application.get_application_id())

        # Load UI from file
        self.window, self.builder = UILoader.load_template('import-export-dialog.ui', 'ImportExportDialog', application=application)
        
        # Get references to UI widgets
        self.export_bookmarks_button = self.builder.get_object('export_bookmarks_button')
        self.import_bookmarks_button = self.builder.get_object('import_bookmarks_button')
        self.export_history_button = self.builder.get_object('export_history_button')
        self.import_history_button = self.builder.get_object('import_history_button')
        self.export_settings_button = self.builder.get_object('export_settings_button')
        self.import_settings_button = self.builder.get_object('import_settings_button')
        
        # Set up the window content
        main_page = self.builder.get_object('main_page')
        self.add(main_page)

        # Connect button signals
        self.export_bookmarks_button.connect("clicked", self._on_export_bookmarks)
        self.import_bookmarks_button.connect("clicked", self._on_import_bookmarks)
        self.export_history_button.connect("clicked", self._on_export_history)
        self.import_history_button.connect("clicked", self._on_import_history)
        self.export_settings_button.connect("clicked", self._on_export_settings)
        self.import_settings_button.connect("clicked", self._on_import_settings)

    def _show_notification(self, message: str):
        if self.get_application().get_window_by_id(1) and hasattr(self.get_application().get_window_by_id(1), 'toast_overlay'):
            self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(message))

    # --- Bookmarks ---
    def _on_export_bookmarks(self, button):
        dialog = Gtk.FileChooserNative.new(
            "Export Bookmarks",
            self.get_root(),
            Gtk.FileChooserAction.SAVE,
            "_Save", "_Cancel"
        )
        dialog.set_current_name(f"seoltoir_bookmarks_{datetime.now().strftime('%Y%m%d')}.json")
        dialog.set_current_folder_uri(GLib.filename_to_uri(GLib.get_user_download_dir(), None))
        dialog.set_modal(True)
        dialog.connect("response", self._on_export_bookmarks_response)
        dialog.show()

    def _on_export_bookmarks_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            file_path = GLib.filename_from_uri(dialog.get_uri(), None)
            bookmarks = self.db_manager.get_bookmarks()
            export_data = [{"url": b[0], "title": b[1], "added_date": b[2]} for b in bookmarks]
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2)
                self._show_notification("Bookmarks exported successfully!")
                print(f"Bookmarks exported to: {file_path}")
            except Exception as e:
                self._show_notification(f"Error exporting bookmarks: {e}")
                print(f"Error exporting bookmarks: {e}")
        dialog.destroy()

    def _on_import_bookmarks(self, button):
        dialog = Gtk.FileChooserNative.new(
            "Import Bookmarks",
            self.get_root(),
            Gtk.FileChooserAction.OPEN,
            "_Open", "_Cancel"
        )
        dialog.set_modal(True)
        dialog.connect("response", self._on_import_bookmarks_response)
        dialog.show()

    def _on_import_bookmarks_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            file_path = GLib.filename_from_uri(dialog.get_uri(), None)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    import_data = json.load(f)
                
                imported_count = 0
                for item in import_data:
                    if "url" in item and "title" in item:
                        if self.db_manager.add_bookmark(item["url"], item["title"]):
                            imported_count += 1
                self._show_notification(f"Imported {imported_count} bookmarks.")
                print(f"Imported {imported_count} bookmarks from: {file_path}")
            except Exception as e:
                self._show_notification(f"Error importing bookmarks: {e}")
                print(f"Error importing bookmarks: {e}")
        dialog.destroy()

    # --- History ---
    def _on_export_history(self, button):
        dialog = Gtk.FileChooserNative.new(
            "Export History",
            self.get_root(),
            Gtk.FileChooserAction.SAVE,
            "_Save", "_Cancel"
        )
        dialog.set_current_name(f"seoltoir_history_{datetime.now().strftime('%Y%m%d')}.csv")
        dialog.set_current_folder_uri(GLib.filename_to_uri(GLib.get_user_download_dir(), None))
        dialog.set_modal(True)
        dialog.connect("response", self._on_export_history_response)
        dialog.show()

    def _on_export_history_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            file_path = GLib.filename_from_uri(dialog.get_uri(), None)
            history = self.db_manager.get_history(limit=None) # Get all history
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["URL", "Title", "Last Visit"]) # Header
                    for entry in history:
                        writer.writerow(entry)
                self._show_notification("History exported successfully!")
                print(f"History exported to: {file_path}")
            except Exception as e:
                self._show_notification(f"Error exporting history: {e}")
                print(f"Error exporting history: {e}")
        dialog.destroy()

    def _on_import_history(self, button):
        dialog = Gtk.FileChooserNative.new(
            "Import History",
            self.get_root(),
            Gtk.FileChooserAction.OPEN,
            "_Open", "_Cancel"
        )
        dialog.set_modal(True)
        dialog.connect("response", self._on_import_history_response)
        dialog.show()

    def _on_import_history_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            file_path = GLib.filename_from_uri(dialog.get_uri(), None)
            try:
                with open(file_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.reader(f)
                    header = next(reader, None) # Skip header
                    
                    imported_count = 0
                    for row in reader:
                        if len(row) >= 2: # Need at least URL and Title
                            url = row[0]
                            title = row[1]
                            self.db_manager.add_history_entry(url, title) # Add/update
                            imported_count += 1
                self._show_notification(f"Imported {imported_count} history entries.")
                print(f"Imported {imported_count} history entries from: {file_path}")
            except Exception as e:
                self._show_notification(f"Error importing history: {e}")
                print(f"Error importing history: {e}")
        dialog.destroy()

    # --- Settings ---
    def _on_export_settings(self, button):
        dialog = Gtk.FileChooserNative.new(
            "Export Settings",
            self.get_root(),
            Gtk.FileChooserAction.SAVE,
            "_Save", "_Cancel"
        )
        dialog.set_current_name(f"seoltoir_settings_{datetime.now().strftime('%Y%m%d')}.json")
        dialog.set_current_folder_uri(GLib.filename_to_uri(GLib.get_user_download_dir(), None))
        dialog.set_modal(True)
        dialog.connect("response", self._on_export_settings_response)
        dialog.show()

    def _on_export_settings_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            file_path = GLib.filename_from_uri(dialog.get_uri(), None)
            try:
                # Get all keys from the schema
                settings_data = {}
                schema_id = self.application.get_application_id()
                schema = Gio.SettingsSchemaSource.get_default().lookup(schema_id, True)
                if schema:
                    for key_name in schema.list_keys():
                        variant = self.settings.get_value(key_name)
                        settings_data[key_name] = variant.unpack()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(settings_data, f, indent=2)
                self._show_notification("Settings exported successfully!")
                print(f"Settings exported to: {file_path}")
            except Exception as e:
                self._show_notification(f"Error exporting settings: {e}")
                print(f"Error exporting settings: {e}")
        dialog.destroy()

    def _on_import_settings(self, button):
        dialog = Gtk.FileChooserNative.new(
            "Import Settings",
            self.get_root(),
            Gtk.FileChooserAction.OPEN,
            "_Open", "_Cancel"
        )
        dialog.set_modal(True)
        dialog.connect("response", self._on_import_settings_response)
        dialog.show()

    def _on_import_settings_response(self, dialog, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            file_path = GLib.filename_from_uri(dialog.get_uri(), None)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    import_data = json.load(f)
                
                imported_count = 0
                schema_id = self.application.get_application_id()
                schema = Gio.SettingsSchemaSource.get_default().lookup(schema_id, True)

                for key, value in import_data.items():
                    if schema and schema.has_key(key):
                        # Ensure value type matches schema
                        key_info = schema.get_key(key)
                        expected_gvariant_type = key_info.get_value_type()
                        try:
                            # Convert Python value to GVariant and set
                            gvariant_value = GLib.Variant.new_from_data(expected_gvariant_type, GLib.Variant(None, value).data)
                            self.settings.set_value(key, gvariant_value)
                            imported_count += 1
                        except GLib.Error as e:
                            print(f"Warning: Type mismatch for key '{key}'. Expected {expected_gvariant_type}, got {type(value)}. Error: {e}")
                    else:
                        print(f"Warning: Key '{key}' not found in schema. Skipping.")
                
                self._show_notification(f"Imported {imported_count} settings.")
                print(f"Imported {imported_count} settings from: {file_path}")
            except Exception as e:
                self._show_notification(f"Error importing settings: {e}")
                print(f"Error importing settings: {e}")
        dialog.destroy()
