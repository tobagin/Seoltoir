import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
import csv
import json
import sqlite3
import os
import base64
from pathlib import Path
from datetime import datetime
from .debug import debug_print

class PasswordImportExport:
    """Handle password import and export functionality."""
    
    def __init__(self, password_manager):
        self.password_manager = password_manager
        
    def export_to_csv(self, file_path: str) -> bool:
        """Export passwords to CSV format."""
        try:
            passwords = self.password_manager.get_all_passwords()
            
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['url', 'username', 'password', 'title', 'created', 'last_used']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for password_data in passwords:
                    # Get the actual password from keyring
                    password = self.password_manager.get_password(
                        password_data['url'], 
                        password_data['username']
                    )
                    
                    writer.writerow({
                        'url': password_data['url'],
                        'username': password_data['username'],
                        'password': password or '',
                        'title': password_data.get('title', ''),
                        'created': password_data.get('created', ''),
                        'last_used': password_data.get('last_used', '')
                    })
            
            debug_print(f"[IMPORT-EXPORT] Exported {len(passwords)} passwords to CSV: {file_path}")
            return True
            
        except Exception as e:
            debug_print(f"[IMPORT-EXPORT] Error exporting to CSV: {e}")
            return False

    def import_from_csv(self, file_path: str) -> tuple[int, int]:
        """Import passwords from CSV format. Returns (imported_count, error_count)."""
        imported_count = 0
        error_count = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                # Try to detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                for row in reader:
                    try:
                        # Extract data with various possible field names
                        url = (row.get('url') or row.get('URL') or 
                               row.get('website') or row.get('site') or '').strip()
                        username = (row.get('username') or row.get('Username') or 
                                  row.get('user') or row.get('email') or 
                                  row.get('login') or '').strip()
                        password = (row.get('password') or row.get('Password') or '').strip()
                        title = (row.get('title') or row.get('Title') or 
                               row.get('name') or '').strip()
                        
                        if url and username and password:
                            # Ensure URL has a scheme
                            if not url.startswith(('http://', 'https://')):
                                url = 'https://' + url
                                
                            success = self.password_manager.save_password(
                                url, username, password, title
                            )
                            if success:
                                imported_count += 1
                            else:
                                error_count += 1
                        else:
                            error_count += 1
                            debug_print(f"[IMPORT-EXPORT] Skipping incomplete row: {row}")
                            
                    except Exception as e:
                        error_count += 1
                        debug_print(f"[IMPORT-EXPORT] Error importing row: {e}")
                        
            debug_print(f"[IMPORT-EXPORT] Import complete: {imported_count} imported, {error_count} errors")
            return imported_count, error_count
            
        except Exception as e:
            debug_print(f"[IMPORT-EXPORT] Error reading CSV file: {e}")
            return 0, 1

    def export_to_json(self, file_path: str) -> bool:
        """Export passwords to JSON format."""
        try:
            passwords = self.password_manager.get_all_passwords()
            export_data = {
                'export_info': {
                    'app': 'Seoltoir Browser',
                    'version': '1.0',
                    'date': datetime.now().isoformat(),
                    'count': len(passwords)
                },
                'passwords': []
            }
            
            for password_data in passwords:
                # Get the actual password from keyring
                password = self.password_manager.get_password(
                    password_data['url'], 
                    password_data['username']
                )
                
                export_data['passwords'].append({
                    'url': password_data['url'],
                    'username': password_data['username'],
                    'password': password or '',
                    'title': password_data.get('title', ''),
                    'domain': password_data['domain'],
                    'created': password_data.get('created', ''),
                    'last_used': password_data.get('last_used', '')
                })
            
            with open(file_path, 'w', encoding='utf-8') as jsonfile:
                json.dump(export_data, jsonfile, indent=2, ensure_ascii=False)
            
            debug_print(f"[IMPORT-EXPORT] Exported {len(passwords)} passwords to JSON: {file_path}")
            return True
            
        except Exception as e:
            debug_print(f"[IMPORT-EXPORT] Error exporting to JSON: {e}")
            return False

    def import_from_json(self, file_path: str) -> tuple[int, int]:
        """Import passwords from JSON format."""
        imported_count = 0
        error_count = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
                
            passwords = data.get('passwords', [])
            if not passwords:
                # Try direct list format
                if isinstance(data, list):
                    passwords = data
                    
            for password_data in passwords:
                try:
                    url = password_data.get('url', '').strip()
                    username = password_data.get('username', '').strip()
                    password = password_data.get('password', '').strip()
                    title = password_data.get('title', '').strip()
                    
                    if url and username and password:
                        # Ensure URL has a scheme
                        if not url.startswith(('http://', 'https://')):
                            url = 'https://' + url
                            
                        success = self.password_manager.save_password(
                            url, username, password, title
                        )
                        if success:
                            imported_count += 1
                        else:
                            error_count += 1
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    debug_print(f"[IMPORT-EXPORT] Error importing JSON entry: {e}")
                    
            debug_print(f"[IMPORT-EXPORT] JSON import complete: {imported_count} imported, {error_count} errors")
            return imported_count, error_count
            
        except Exception as e:
            debug_print(f"[IMPORT-EXPORT] Error reading JSON file: {e}")
            return 0, 1

    def import_from_chrome(self, file_path: str) -> tuple[int, int]:
        """Import passwords from Chrome login data SQLite database."""
        imported_count = 0
        error_count = 0
        
        try:
            # Connect to Chrome's login data database
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()
            
            # Query Chrome's logins table
            cursor.execute("""
                SELECT origin_url, username_value, password_value, display_name
                FROM logins
                WHERE blacklisted_by_user = 0
            """)
            
            for row in cursor.fetchall():
                try:
                    url, username, encrypted_password, title = row
                    
                    if url and username:
                        # Note: Chrome passwords are encrypted and would need decryption
                        # For now, we'll skip the actual password and just show structure
                        debug_print(f"[IMPORT-EXPORT] Found Chrome entry: {username}@{url}")
                        # In a real implementation, you'd decrypt the password here
                        error_count += 1  # Count as error since we can't decrypt
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    debug_print(f"[IMPORT-EXPORT] Error processing Chrome entry: {e}")
            
            conn.close()
            debug_print(f"[IMPORT-EXPORT] Chrome import scan complete: {imported_count} imported, {error_count} errors")
            return imported_count, error_count
            
        except Exception as e:
            debug_print(f"[IMPORT-EXPORT] Error reading Chrome database: {e}")
            return 0, 1

    def import_from_firefox(self, file_path: str) -> tuple[int, int]:
        """Import passwords from Firefox logins.json file."""
        imported_count = 0
        error_count = 0
        
        try:
            with open(file_path, 'r', encoding='utf-8') as jsonfile:
                data = json.load(jsonfile)
                
            logins = data.get('logins', [])
            
            for login in logins:
                try:
                    url = login.get('hostname', '').strip()
                    username = login.get('encryptedUsername', '').strip()
                    password = login.get('encryptedPassword', '').strip()
                    
                    if url and username:
                        # Note: Firefox passwords are encrypted and would need decryption
                        # For now, we'll just show the structure
                        debug_print(f"[IMPORT-EXPORT] Found Firefox entry: {username}@{url}")
                        # In a real implementation, you'd decrypt the password here
                        error_count += 1  # Count as error since we can't decrypt
                    else:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    debug_print(f"[IMPORT-EXPORT] Error processing Firefox entry: {e}")
            
            debug_print(f"[IMPORT-EXPORT] Firefox import scan complete: {imported_count} imported, {error_count} errors")
            return imported_count, error_count
            
        except Exception as e:
            debug_print(f"[IMPORT-EXPORT] Error reading Firefox logins file: {e}")
            return 0, 1

    def get_chrome_profile_paths(self) -> list:
        """Get possible Chrome profile paths."""
        home = Path.home()
        possible_paths = [
            home / ".config" / "google-chrome" / "Default" / "Login Data",
            home / ".config" / "chromium" / "Default" / "Login Data",
            home / "snap" / "chromium" / "common" / "chromium" / "Default" / "Login Data",
        ]
        
        existing_paths = []
        for path in possible_paths:
            if path.exists():
                existing_paths.append(str(path))
                
        return existing_paths

    def get_firefox_profile_paths(self) -> list:
        """Get possible Firefox profile paths."""
        home = Path.home()
        firefox_dir = home / ".mozilla" / "firefox"
        
        existing_paths = []
        if firefox_dir.exists():
            for profile_dir in firefox_dir.iterdir():
                if profile_dir.is_dir() and not profile_dir.name.startswith('.'):
                    logins_file = profile_dir / "logins.json"
                    if logins_file.exists():
                        existing_paths.append(str(logins_file))
                        
        return existing_paths

class ImportExportDialog(Adw.MessageDialog):
    """Dialog for importing and exporting passwords."""
    
    def __init__(self, parent, password_manager, mode='import'):
        super().__init__(
            transient_for=parent,
            modal=True,
            heading=f"{'Import' if mode == 'import' else 'Export'} Passwords"
        )
        
        self.password_manager = password_manager
        self.import_export = PasswordImportExport(password_manager)
        self.mode = mode
        
        self._setup_ui()

    def _setup_ui(self):
        """Set up the import/export dialog UI."""
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        
        if self.mode == 'import':
            self._setup_import_ui(content_box)
        else:
            self._setup_export_ui(content_box)
            
        self.set_extra_child(content_box)
        
        self.add_response("cancel", "Cancel")
        self.add_response("action", "Import" if self.mode == "import" else "Export")
        self.set_default_response("action")
        
        self.connect("response", self._on_response)

    def _setup_import_ui(self, container):
        """Set up import-specific UI."""
        # Import format selection
        format_group = Adw.PreferencesGroup()
        format_group.set_title("Import Format")
        
        self.format_combo = Adw.ComboRow()
        self.format_combo.set_title("Format")
        self.format_combo.set_subtitle("Choose the format of your password file")
        
        format_model = Gtk.StringList.new([
            "CSV (Comma Separated Values)",
            "JSON (Seoltoir format)",
            "Chrome (Login Data)",
            "Firefox (logins.json)"
        ])
        self.format_combo.set_model(format_model)
        self.format_combo.set_selected(0)
        
        format_group.add(self.format_combo)
        container.append(format_group)
        
        # File selection
        file_group = Adw.PreferencesGroup()
        file_group.set_title("Select File")
        
        file_row = Adw.ActionRow()
        file_row.set_title("Import File")
        file_row.set_subtitle("Choose the file to import passwords from")
        
        self.file_button = Gtk.Button(label="Choose File...")
        self.file_button.set_valign(Gtk.Align.CENTER)
        self.file_button.connect("clicked", self._on_choose_file_clicked)
        file_row.add_suffix(self.file_button)
        
        file_group.add(file_row)
        container.append(file_group)
        
        # File info
        self.file_info_label = Gtk.Label()
        self.file_info_label.set_wrap(True)
        self.file_info_label.set_xalign(0)
        container.append(self.file_info_label)
        
        self.selected_file = None

    def _setup_export_ui(self, container):
        """Set up export-specific UI."""
        # Export format selection
        format_group = Adw.PreferencesGroup()
        format_group.set_title("Export Format")
        
        self.format_combo = Adw.ComboRow()
        self.format_combo.set_title("Format")
        self.format_combo.set_subtitle("Choose the export format")
        
        format_model = Gtk.StringList.new([
            "CSV (Comma Separated Values)",
            "JSON (Seoltoir format)"
        ])
        self.format_combo.set_model(format_model)
        self.format_combo.set_selected(0)
        
        format_group.add(self.format_combo)
        container.append(format_group)
        
        # Password count info
        password_count = len(self.password_manager.get_all_passwords())
        info_label = Gtk.Label()
        info_label.set_markup(f"<b>{password_count}</b> passwords will be exported")
        info_label.set_margin_top(12)
        container.append(info_label)
        
        # Warning
        warning_label = Gtk.Label()
        warning_label.set_markup("<b>⚠️ Security Warning:</b> Exported passwords will be stored in plain text. Keep the export file secure and delete it when no longer needed.")
        warning_label.set_wrap(True)
        warning_label.set_xalign(0)
        warning_label.set_margin_top(12)
        warning_label.add_css_class("warning")
        container.append(warning_label)

    def _on_choose_file_clicked(self, button):
        """Handle file selection for import."""
        file_dialog = Gtk.FileChooserNative.new(
            "Choose Import File",
            self,
            Gtk.FileChooserAction.OPEN,
            "_Open",
            "_Cancel"
        )
        
        # Add file filters based on selected format
        selected_format = self.format_combo.get_selected()
        
        if selected_format == 0:  # CSV
            filter_csv = Gtk.FileFilter()
            filter_csv.set_name("CSV Files")
            filter_csv.add_mime_type("text/csv")
            filter_csv.add_pattern("*.csv")
            file_dialog.add_filter(filter_csv)
        elif selected_format == 1:  # JSON
            filter_json = Gtk.FileFilter()
            filter_json.set_name("JSON Files")
            filter_json.add_mime_type("application/json")
            filter_json.add_pattern("*.json")
            file_dialog.add_filter(filter_json)
        elif selected_format == 2:  # Chrome
            filter_db = Gtk.FileFilter()
            filter_db.set_name("Chrome Login Data")
            filter_db.add_pattern("Login Data*")
            file_dialog.add_filter(filter_db)
        elif selected_format == 3:  # Firefox
            filter_json = Gtk.FileFilter()
            filter_json.set_name("Firefox Logins")
            filter_json.add_pattern("logins.json")
            file_dialog.add_filter(filter_json)
        
        # Add all files filter
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        file_dialog.add_filter(filter_all)
        
        def on_file_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                self.selected_file = dialog.get_file().get_path()
                self.file_info_label.set_text(f"Selected: {os.path.basename(self.selected_file)}")
                self.file_button.set_label(os.path.basename(self.selected_file))
        
        file_dialog.connect("response", on_file_response)
        file_dialog.show()

    def _on_response(self, dialog, response):
        """Handle dialog response."""
        if response == "action":
            if self.mode == "import":
                self._perform_import()
            else:
                self._perform_export()

    def _perform_import(self):
        """Perform the password import."""
        if not self.selected_file:
            self._show_error("Please select a file to import.")
            return
            
        selected_format = self.format_combo.get_selected()
        
        try:
            if selected_format == 0:  # CSV
                imported, errors = self.import_export.import_from_csv(self.selected_file)
            elif selected_format == 1:  # JSON
                imported, errors = self.import_export.import_from_json(self.selected_file)
            elif selected_format == 2:  # Chrome
                imported, errors = self.import_export.import_from_chrome(self.selected_file)
            elif selected_format == 3:  # Firefox
                imported, errors = self.import_export.import_from_firefox(self.selected_file)
            else:
                self._show_error("Unsupported import format.")
                return
                
            # Show results
            if imported > 0:
                message = f"Successfully imported {imported} passwords."
                if errors > 0:
                    message += f" {errors} entries had errors and were skipped."
                self._show_success(message)
            elif errors > 0:
                self._show_error(f"Import failed. {errors} entries had errors.")
            else:
                self._show_error("No passwords were imported.")
                
        except Exception as e:
            self._show_error(f"Import failed: {str(e)}")

    def _perform_export(self):
        """Perform the password export."""
        file_dialog = Gtk.FileChooserNative.new(
            "Export Passwords",
            self,
            Gtk.FileChooserAction.SAVE,
            "_Save",
            "_Cancel"
        )
        
        selected_format = self.format_combo.get_selected()
        
        if selected_format == 0:  # CSV
            file_dialog.set_current_name("seoltoir_passwords.csv")
            filter_csv = Gtk.FileFilter()
            filter_csv.set_name("CSV Files")
            filter_csv.add_pattern("*.csv")
            file_dialog.add_filter(filter_csv)
        else:  # JSON
            file_dialog.set_current_name("seoltoir_passwords.json")
            filter_json = Gtk.FileFilter()
            filter_json.set_name("JSON Files")
            filter_json.add_pattern("*.json")
            file_dialog.add_filter(filter_json)
        
        def on_export_response(dialog, response):
            if response == Gtk.ResponseType.ACCEPT:
                export_path = dialog.get_file().get_path()
                
                try:
                    if selected_format == 0:  # CSV
                        success = self.import_export.export_to_csv(export_path)
                    else:  # JSON
                        success = self.import_export.export_to_json(export_path)
                        
                    if success:
                        self._show_success(f"Passwords exported to {os.path.basename(export_path)}")
                    else:
                        self._show_error("Export failed.")
                        
                except Exception as e:
                    self._show_error(f"Export failed: {str(e)}")
        
        file_dialog.connect("response", on_export_response)
        file_dialog.show()

    def _show_success(self, message):
        """Show success message."""
        success_dialog = Adw.AlertDialog(
            heading="Success",
            body=message,
            close_response="ok"
        )
        success_dialog.add_response("ok", "OK")
        success_dialog.present(self.get_transient_for())

    def _show_error(self, message):
        """Show error message."""
        error_dialog = Adw.AlertDialog(
            heading="Error",
            body=message,
            close_response="ok"
        )
        error_dialog.add_response("ok", "OK")
        error_dialog.present(self.get_transient_for())