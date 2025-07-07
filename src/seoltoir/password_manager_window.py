import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject
import urllib.parse
from .debug import debug_print

class PasswordManagerWindow(Adw.PreferencesWindow):
    """Password manager window for viewing and managing saved passwords."""
    
    def __init__(self, application, password_manager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_application(application)
        self.set_title("Password Manager")
        self.set_default_size(800, 600)
        self.set_modal(True)
        
        self.password_manager = password_manager
        self.passwords = []
        self.search_entry = None
        
        self._setup_ui()
        self._load_passwords()

    def _setup_ui(self):
        """Set up the password manager UI."""
        # Main page
        main_page = Adw.PreferencesPage()
        main_page.set_title("Passwords")
        main_page.set_icon_name("dialog-password-symbolic")
        
        # Search group
        search_group = Adw.PreferencesGroup()
        search_group.set_title("Search")
        
        # Search entry
        search_row = Adw.ActionRow()
        search_row.set_title("Search passwords")
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search by site or username...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        search_row.add_suffix(self.search_entry)
        
        search_group.add(search_row)
        main_page.add(search_group)
        
        # Passwords group
        self.passwords_group = Adw.PreferencesGroup()
        self.passwords_group.set_title("Saved Passwords")
        self.passwords_group.set_description("Passwords are stored securely in your system keyring")
        main_page.add(self.passwords_group)
        
        # Actions group
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Actions")
        
        # Generate password button
        generate_row = Adw.ActionRow()
        generate_row.set_title("Generate Password")
        generate_row.set_subtitle("Create a strong, secure password")
        
        generate_button = Gtk.Button()
        generate_button.set_icon_name("document-new-symbolic")
        generate_button.set_valign(Gtk.Align.CENTER)
        generate_button.set_tooltip_text("Generate new password")
        generate_button.connect("clicked", self._on_generate_password_clicked)
        generate_row.add_suffix(generate_button)
        
        actions_group.add(generate_row)
        
        # Import/Export row
        import_export_row = Adw.ActionRow()
        import_export_row.set_title("Import & Export")
        import_export_row.set_subtitle("Import passwords from other browsers or export to CSV")
        
        import_button = Gtk.Button()
        import_button.set_label("Import...")
        import_button.set_valign(Gtk.Align.CENTER)
        import_button.connect("clicked", self._on_import_clicked)
        import_export_row.add_suffix(import_button)
        
        export_button = Gtk.Button()
        export_button.set_label("Export...")
        export_button.set_valign(Gtk.Align.CENTER)
        export_button.connect("clicked", self._on_export_clicked)
        import_export_row.add_suffix(export_button)
        
        actions_group.add(import_export_row)
        main_page.add(actions_group)
        
        # Add the main page
        self.add(main_page)

    def _load_passwords(self):
        """Load saved passwords and populate the list."""
        # Clear existing passwords
        self._clear_password_list()
        
        try:
            self.passwords = self.password_manager.get_all_passwords()
            debug_print(f"[PASSWORD-UI] Loaded {len(self.passwords)} passwords")
            
            if not self.passwords:
                self._show_empty_state()
                return
                
            # Group passwords by domain
            domains = {}
            for password in self.passwords:
                domain = password['domain']
                if domain not in domains:
                    domains[domain] = []
                domains[domain].append(password)
                
            # Add password rows for each domain
            for domain, domain_passwords in sorted(domains.items()):
                domain_group = Adw.PreferencesGroup()
                domain_group.set_title(domain)
                
                for password in domain_passwords:
                    row = self._create_password_row(password)
                    domain_group.add(row)
                    
                self.passwords_group.add(domain_group)
                
        except Exception as e:
            debug_print(f"[PASSWORD-UI] Error loading passwords: {e}")
            self._show_error_state()

    def _create_password_row(self, password):
        """Create a password row widget."""
        row = Adw.ActionRow()
        row.set_title(password['username'])
        
        # Create subtitle with last used info
        last_used = password.get('last_used', 'Never')
        if last_used and last_used != 'Never':
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(last_used.replace('Z', '+00:00'))
                last_used_str = dt.strftime("%b %d, %Y")
            except:
                last_used_str = "Recently"
        else:
            last_used_str = "Never used"
            
        row.set_subtitle(f"Last used: {last_used_str}")
        
        # Copy username button
        copy_user_button = Gtk.Button()
        copy_user_button.set_icon_name("edit-copy-symbolic")
        copy_user_button.set_tooltip_text("Copy username")
        copy_user_button.set_valign(Gtk.Align.CENTER)
        copy_user_button.connect("clicked", self._on_copy_username_clicked, password['username'])
        row.add_suffix(copy_user_button)
        
        # Copy password button
        copy_pass_button = Gtk.Button()
        copy_pass_button.set_icon_name("dialog-password-symbolic")
        copy_pass_button.set_tooltip_text("Copy password")
        copy_pass_button.set_valign(Gtk.Align.CENTER)
        copy_pass_button.connect("clicked", self._on_copy_password_clicked, password)
        row.add_suffix(copy_pass_button)
        
        # Edit button
        edit_button = Gtk.Button()
        edit_button.set_icon_name("document-edit-symbolic")
        edit_button.set_tooltip_text("Edit password")
        edit_button.set_valign(Gtk.Align.CENTER)
        edit_button.connect("clicked", self._on_edit_password_clicked, password)
        row.add_suffix(edit_button)
        
        # Delete button
        delete_button = Gtk.Button()
        delete_button.set_icon_name("edit-delete-symbolic")
        delete_button.set_tooltip_text("Delete password")
        delete_button.set_valign(Gtk.Align.CENTER)
        delete_button.connect("clicked", self._on_delete_password_clicked, password)
        row.add_suffix(delete_button)
        
        # Store password data for easy access
        row.password_data = password
        
        return row

    def _clear_password_list(self):
        """Clear the password list."""
        # Remove all groups from passwords_group
        child = self.passwords_group.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.passwords_group.remove(child)
            child = next_child

    def _show_empty_state(self):
        """Show empty state when no passwords are saved."""
        empty_row = Adw.ActionRow()
        empty_row.set_title("No passwords saved")
        empty_row.set_subtitle("Passwords will appear here when you save them from login forms")
        self.passwords_group.add(empty_row)

    def _show_error_state(self):
        """Show error state when passwords can't be loaded."""
        error_row = Adw.ActionRow()
        error_row.set_title("Error loading passwords")
        error_row.set_subtitle("There was a problem accessing your saved passwords")
        self.passwords_group.add(error_row)

    def _on_search_changed(self, search_entry):
        """Handle search text changes."""
        search_text = search_entry.get_text().lower()
        
        if not search_text:
            self._load_passwords()
            return
            
        # Filter passwords by search text
        filtered_passwords = []
        for password in self.passwords:
            if (search_text in password['domain'].lower() or 
                search_text in password['username'].lower() or
                search_text in password.get('title', '').lower()):
                filtered_passwords.append(password)
        
        # Clear and rebuild list with filtered passwords
        self._clear_password_list()
        
        if not filtered_passwords:
            no_results_row = Adw.ActionRow()
            no_results_row.set_title("No matching passwords")
            no_results_row.set_subtitle(f"No passwords found matching '{search_text}'")
            self.passwords_group.add(no_results_row)
            return
            
        # Add filtered password rows
        for password in filtered_passwords:
            row = self._create_password_row(password)
            self.passwords_group.add(row)

    def _on_copy_username_clicked(self, button, username):
        """Copy username to clipboard."""
        clipboard = self.get_clipboard()
        clipboard.set(username)
        
        # Show toast notification
        toast = Adw.Toast.new("Username copied to clipboard")
        toast.set_timeout(2)
        
        # Find the window's toast overlay (if available)
        if hasattr(self, 'add_toast'):
            self.add_toast(toast)

    def _on_copy_password_clicked(self, button, password_data):
        """Copy password to clipboard."""
        try:
            password = self.password_manager.get_password(password_data['url'], password_data['username'])
            if password:
                clipboard = self.get_clipboard()
                clipboard.set(password)
                
                # Show toast notification
                toast = Adw.Toast.new("Password copied to clipboard")
                toast.set_timeout(2)
                
                if hasattr(self, 'add_toast'):
                    self.add_toast(toast)
            else:
                debug_print(f"[PASSWORD-UI] Failed to retrieve password for copying")
                
        except Exception as e:
            debug_print(f"[PASSWORD-UI] Error copying password: {e}")

    def _on_edit_password_clicked(self, button, password_data):
        """Show password edit dialog."""
        self._show_password_edit_dialog(password_data)

    def _on_delete_password_clicked(self, button, password_data):
        """Show password delete confirmation."""
        dialog = Adw.AlertDialog(
            heading=f"Delete password for {password_data['domain']}?",
            body=f"This will permanently delete the saved password for {password_data['username']} on {password_data['domain']}. This action cannot be undone.",
            close_response="cancel"
        )
        
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete Password")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        
        def on_delete_response(dialog, response):
            if response == "delete":
                success = self.password_manager.delete_password(
                    password_data['url'], 
                    password_data['username']
                )
                if success:
                    debug_print(f"[PASSWORD-UI] Deleted password for {password_data['username']}@{password_data['domain']}")
                    self._load_passwords()  # Refresh the list
                else:
                    debug_print(f"[PASSWORD-UI] Failed to delete password")
        
        dialog.connect("response", on_delete_response)
        dialog.present(self)

    def _show_password_edit_dialog(self, password_data):
        """Show password edit dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading=f"Edit password for {password_data['domain']}"
        )
        
        # Create form content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        
        # Username entry
        username_entry = Gtk.Entry()
        username_entry.set_text(password_data['username'])
        username_entry.set_placeholder_text("Username")
        content_box.append(Gtk.Label(label="Username:", xalign=0))
        content_box.append(username_entry)
        
        # Password entry
        password_entry = Gtk.Entry()
        password_entry.set_visibility(False)
        password_entry.set_placeholder_text("Password")
        
        # Load current password
        current_password = self.password_manager.get_password(
            password_data['url'], 
            password_data['username']
        )
        if current_password:
            password_entry.set_text(current_password)
            
        content_box.append(Gtk.Label(label="Password:", xalign=0))
        
        # Password entry with show/hide button
        password_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        password_box.append(password_entry)
        
        show_button = Gtk.Button()
        show_button.set_icon_name("view-reveal-symbolic")
        show_button.set_tooltip_text("Show/hide password")
        
        def toggle_password_visibility(button):
            visible = password_entry.get_visibility()
            password_entry.set_visibility(not visible)
            icon_name = "view-conceal-symbolic" if not visible else "view-reveal-symbolic"
            button.set_icon_name(icon_name)
            
        show_button.connect("clicked", toggle_password_visibility)
        password_box.append(show_button)
        
        # Generate password button
        generate_button = Gtk.Button()
        generate_button.set_icon_name("document-new-symbolic")
        generate_button.set_tooltip_text("Generate new password")
        
        def generate_new_password(button):
            new_password = self.password_manager.generate_password()
            password_entry.set_text(new_password)
            
        generate_button.connect("clicked", generate_new_password)
        password_box.append(generate_button)
        
        content_box.append(password_box)
        
        dialog.set_extra_child(content_box)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("save", "Save Changes")
        dialog.set_default_response("save")
        
        def on_edit_response(dialog, response):
            if response == "save":
                new_username = username_entry.get_text()
                new_password = password_entry.get_text()
                
                if new_username and new_password:
                    # If username changed, delete old entry
                    if new_username != password_data['username']:
                        self.password_manager.delete_password(
                            password_data['url'], 
                            password_data['username']
                        )
                    
                    # Save updated password
                    success = self.password_manager.save_password(
                        password_data['url'],
                        new_username,
                        new_password,
                        password_data.get('title')
                    )
                    
                    if success:
                        debug_print(f"[PASSWORD-UI] Updated password for {new_username}@{password_data['domain']}")
                        self._load_passwords()  # Refresh the list
                    else:
                        debug_print(f"[PASSWORD-UI] Failed to update password")
        
        dialog.connect("response", on_edit_response)
        dialog.present()

    def _on_generate_password_clicked(self, button):
        """Show password generator dialog."""
        self._show_password_generator_dialog()

    def _show_password_generator_dialog(self):
        """Show password generator dialog."""
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Generate Password"
        )
        
        # Create generator content
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.set_margin_start(12)
        content_box.set_margin_end(12)
        
        # Generated password display
        password_entry = Gtk.Entry()
        password_entry.set_editable(False)
        content_box.append(Gtk.Label(label="Generated Password:", xalign=0))
        content_box.append(password_entry)
        
        # Length adjustment
        length_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        length_label = Gtk.Label(label="Length:")
        length_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 8, 32, 1)
        length_scale.set_value(16)
        length_scale.set_hexpand(True)
        length_box.append(length_label)
        length_box.append(length_scale)
        content_box.append(length_box)
        
        # Options checkboxes
        options_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        
        uppercase_check = Gtk.CheckButton(label="Uppercase letters (A-Z)")
        uppercase_check.set_active(True)
        
        lowercase_check = Gtk.CheckButton(label="Lowercase letters (a-z)")
        lowercase_check.set_active(True)
        
        numbers_check = Gtk.CheckButton(label="Numbers (0-9)")
        numbers_check.set_active(True)
        
        symbols_check = Gtk.CheckButton(label="Symbols (!@#$%^&*)")
        symbols_check.set_active(True)
        
        options_box.append(uppercase_check)
        options_box.append(lowercase_check)
        options_box.append(numbers_check)
        options_box.append(symbols_check)
        content_box.append(options_box)
        
        # Generate button
        generate_button = Gtk.Button(label="Generate New Password")
        generate_button.set_halign(Gtk.Align.CENTER)
        
        def generate_password():
            length = int(length_scale.get_value())
            password = self.password_manager.generate_password(
                length=length,
                use_uppercase=uppercase_check.get_active(),
                use_lowercase=lowercase_check.get_active(),
                use_numbers=numbers_check.get_active(),
                use_symbols=symbols_check.get_active()
            )
            password_entry.set_text(password)
            
        generate_button.connect("clicked", lambda b: generate_password())
        content_box.append(generate_button)
        
        # Generate initial password
        generate_password()
        
        dialog.set_extra_child(content_box)
        dialog.add_response("close", "Close")
        dialog.add_response("copy", "Copy to Clipboard")
        dialog.set_default_response("copy")
        
        def on_generator_response(dialog, response):
            if response == "copy":
                password = password_entry.get_text()
                if password:
                    clipboard = self.get_clipboard()
                    clipboard.set(password)
        
        dialog.connect("response", on_generator_response)
        dialog.present()

    def _on_import_clicked(self, button):
        """Handle import passwords."""
        from .password_import_export import ImportExportDialog
        
        import_dialog = ImportExportDialog(self, self.password_manager, mode='import')
        
        def on_import_completed(dialog, response):
            if response == "action":
                # Refresh the password list after import
                self._load_passwords()
        
        import_dialog.connect("response", on_import_completed)
        import_dialog.present()

    def _on_export_clicked(self, button):
        """Handle export passwords."""
        from .password_import_export import ImportExportDialog
        
        export_dialog = ImportExportDialog(self, self.password_manager, mode='export')
        export_dialog.present()