import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, Adw, Gio, GLib, WebKit

import urllib.parse # For parsing URLs

from .ui_loader import UILoader
from .debug import debug_print

class SiteSettingsDialog(Adw.PreferencesWindow):
    def __init__(self, application, current_uri: str, web_context=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_application(application)
        self.set_title("Site Settings")
        self.set_default_size(600, 500)

        self.current_uri = current_uri
        self.current_domain = self._get_domain_from_uri(current_uri)
        self.settings = Gio.Settings.new(application.get_application_id())
        # Use the provided web_context or fall back to default
        self.web_context = web_context or WebKit.WebContext.get_default()
        self.network_session = self.web_context.get_network_session() if hasattr(self.web_context, 'get_network_session') else WebKit.NetworkSession.get_default()
        self.website_data_manager = self.network_session.get_website_data_manager()
        self.cookie_manager = self.network_session.get_cookie_manager()

        # Load UI from file
        ui_path = UILoader.get_ui_file_path('site-settings-dialog.ui')
        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_path)
        
        # Get references to UI widgets
        self.js_row = self.builder.get_object('js_row')
        self.notifications_row = self.builder.get_object('notifications_row')
        self.cookie_listbox = self.builder.get_object('cookie_listbox')
        self.delete_all_cookies_button = self.builder.get_object('delete_all_cookies_button')
        self.other_storage_listbox = self.builder.get_object('other_storage_listbox')
        self.delete_all_other_storage_button = self.builder.get_object('delete_all_other_storage_button')
        
        # Set up the window content
        permissions_page = self.builder.get_object('permissions_page')
        cookies_page = self.builder.get_object('cookies_page')
        self.add(permissions_page)
        self.add(cookies_page)
        
        # Set up JavaScript combo row
        js_model = Gtk.StringList.new(["Allow", "Block"])
        self.js_row.set_model(js_model)
        self.js_row.set_selected(0) # Default to Allow
        
        # Set up Notifications combo row
        notifications_model = Gtk.StringList.new(["Default", "Allow", "Block"])
        self.notifications_row.set_model(notifications_model)
        self.notifications_row.set_selected(0) # Default to Default
        
        # Connect button signals
        self.delete_all_cookies_button.connect("clicked", self._on_delete_all_cookies_clicked)
        self.delete_all_other_storage_button.connect("clicked", self._on_delete_all_other_storage_clicked)

        if self.current_domain:
            self.set_title(f"Site Settings - {self.current_domain}")
        else:
            self.set_title("Site Settings")

        self._load_notification_policy()
        self._load_js_policy()
        self.load_cookies() # Load cookies for the current site
        self.load_other_site_data()
        
        # Connect signals
        self.notifications_row.connect("notify::selected", self._on_notification_policy_changed)

    def _get_domain_from_uri(self, uri: str) -> str:
        try:
            parsed = urllib.parse.urlparse(uri)
            # Remove www. for consistency in domain matching
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except ValueError:
            return ""

    def _load_js_policy(self):
        # Get global JS setting
        global_js_enabled = self.settings.get_boolean("enable-javascript")
        
        # Get per-site exceptions
        js_exceptions = self.settings.get_strv("javascript-exceptions")
        
        current_site_policy = "Default (Global)" # Default if no specific rule
        if self.current_domain:
            for exception in js_exceptions:
                parts = exception.split(":", 1)
                if len(parts) == 2 and parts[0] == self.current_domain:
                    if parts[1] == "allow":
                        current_site_policy = "Allow"
                    elif parts[1] == "block":
                        current_site_policy = "Block"
                    break
        
        # Set dropdown selection
        model_strings = [self.js_row.get_model().get_string(i) for i in range(self.js_row.get_model().get_n_items())]
        try:
            selected_index = model_strings.index(current_site_policy)
            self.js_row.set_selected(selected_index)
        except ValueError:
            self.js_row.set_selected(0) # Fallback to Default

        # Update subtitle to indicate effective policy
        if current_site_policy == "Default (Global)":
            effective_policy = "enabled" if global_js_enabled else "disabled"
            self.js_row.set_subtitle(f"Currently: {effective_policy} (based on global setting)")
        else:
            self.js_row.set_subtitle(f"Currently: {current_site_policy.lower()}")

    def _on_js_policy_changed(self, dropdown, pspec):
        selected_item = dropdown.get_selected_item()
        if not selected_item or not self.current_domain:
            return

        policy_str = selected_item.get_string()
        
        js_exceptions = self.settings.get_strv("javascript-exceptions")
        
        # Remove existing rule for this domain
        new_exceptions = [
            e for e in js_exceptions if not e.startswith(f"{self.current_domain}:")
        ]
        
        # Add new rule if not "Default"
        if policy_str == "Allow":
            new_exceptions.append(f"{self.current_domain}:allow")
        elif policy_str == "Block":
            new_exceptions.append(f"{self.current_domain}:block")
        
        self.settings.set_strv("javascript-exceptions", new_exceptions)
        self._load_js_policy() # Refresh subtitle

    def load_cookies(self):
        """Loads cookies for the current domain and populates the listbox."""
        child = self.cookie_listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.cookie_listbox.remove(child)
            child = next_child

        if not self.current_domain:
            return

        # WebKit.CookieManager.get_cookies (uri, cancellable, callback)
        self.cookie_manager.get_cookies(
            self.current_uri, # Use current URI to get relevant cookies
            None,
            self._on_get_cookies_ready
        )
        print(f"Requesting cookies for {self.current_uri}")

    def _on_get_cookies_ready(self, source_object, res):
        try:
            cookies = self.cookie_manager.get_cookies_finish(res)
            print(f"Received {len(cookies) if cookies else 0} cookies for {self.current_domain}")
            
            if not cookies:
                no_cookies_row = Adw.ActionRow.new()
                no_cookies_row.set_title("No cookies found for this site.")
                self.cookie_listbox.append(no_cookies_row)
                return

            for cookie in cookies:
                try:
                    cookie_domain = cookie.get_domain()
                    print(f"Processing cookie: {cookie.get_name()} for domain: {cookie_domain}")
                    
                    # Filter to only show cookies for the current domain for clarity
                    if cookie_domain.endswith(self.current_domain) or cookie_domain == self.current_domain:
                        row = Adw.ActionRow.new()
                        row.set_title(cookie.get_name())
                        
                        # Build subtitle safely
                        cookie_value = cookie.get_value()
                        cookie_path = cookie.get_path()
                        expires = cookie.get_expires()
                        expires_str = "Session"
                        print(f"Cookie {cookie.get_name()} expires value: {expires}, type: {type(expires)}")
                        if expires is not None:
                            try:
                                # expires is already a GLib.DateTime object
                                expires_str = expires.format("%Y-%m-%d %H:%M:%S")
                            except Exception as date_error:
                                print(f"Date parsing error for cookie {cookie.get_name()}: {date_error}")
                                expires_str = "Unknown"
                        
                        row.set_subtitle(f"Value: {cookie_value[:50]}{'...' if len(cookie_value) > 50 else ''} | Path: {cookie_path} | Expires: {expires_str}")
                        
                        delete_button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
                        delete_button.set_tooltip_text("Delete this cookie")
                        delete_button.set_valign(Gtk.Align.CENTER)
                        delete_button.connect("clicked", self._on_delete_single_cookie_clicked, cookie)
                        row.add_suffix(delete_button)
                        
                        self.cookie_listbox.append(row)
                        print(f"Added cookie {cookie.get_name()} to UI")
                except Exception as cookie_error:
                    print(f"Error processing individual cookie: {cookie_error}")
                    continue
        except Exception as e:
            debug_print(f"Error getting cookies: {e}")
            error_row = Adw.ActionRow.new()
            error_row.set_title("Error loading cookies.")
            self.cookie_listbox.append(error_row)

    def _on_delete_single_cookie_clicked(self, button, cookie):
        self.cookie_manager.delete_cookie(cookie)
        self.load_cookies() # Reload the list
        debug_print(f"Deleted cookie: {cookie.get_name()} from {cookie.get_domain()}")
        self.get_application().get_window_by_id(1)._on_show_notification(
            None, f"Cookie deleted for {self.current_domain}"
        )

    def _on_delete_all_cookies_clicked(self, button):
        if not self.current_domain:
            return
        
        # In WebKit6, we need to get cookies first and then delete them individually
        self.cookie_manager.get_cookies(
            self.current_uri,
            None,
            self._on_get_cookies_for_deletion
        )

    def _on_get_cookies_for_deletion(self, source_object, res):
        try:
            cookies = self.cookie_manager.get_cookies_finish(res)
            
            if not cookies:
                self.get_application().get_window_by_id(1)._on_show_notification(
                    None, f"No cookies found for {self.current_domain}"
                )
                return
            
            # Delete each cookie individually
            for cookie in cookies:
                if cookie.get_domain().endswith(self.current_domain) or cookie.get_domain() == self.current_domain:
                    self.cookie_manager.delete_cookie(cookie)
            
            self.load_cookies() # Reload the list
            debug_print(f"Deleted all cookies for domain: {self.current_domain}")
            self.get_application().get_window_by_id(1)._on_show_notification(
                None, f"All cookies deleted for {self.current_domain}"
            )
        except Exception as e:
            debug_print(f"Error deleting cookies: {e}")
            self.get_application().get_window_by_id(1)._on_show_notification(
                None, f"Error deleting cookies for {self.current_domain}"
            )

    # --- Tier 8: Other Site Storage Management ---
    def load_other_site_data(self):
        """
        Loads and displays information about other site storage types for the current domain.
        WebKit's API for granular per-origin data sizes is complex.
        For now, we just list the types and provide a clear button.
        """
        child = self.other_storage_listbox.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.other_storage_listbox.remove(child)
            child = next_child

        if not self.current_domain:
            return

        # WebKit.WebsiteDataManager.get_data_for_origins (types, origins, cancellable, callback)
        # We need the WebKit.SecurityOrigin for the current domain.
        # This is a bit indirect. Let's create a dummy origin for the current domain.
        # This will only get data for this specific origin.
        # To get data for all subdomains, you'd need more complex logic.
        
        current_origin_uri = f"https://{self.current_domain}" # Assume HTTPS for origin
        origin = WebKit.SecurityOrigin.new_for_uri(current_origin_uri)

        if not origin:
            no_data_row = Adw.ActionRow.new()
            no_data_row.set_title("Could not determine site origin.")
            self.other_storage_listbox.append(no_data_row)
            return

        # Query all relevant data types for this origin
        types_to_query = WebKit.WebsiteDataTypes.LOCAL_STORAGE | \
                         WebKit.WebsiteDataTypes.INDEXEDDB_DATABASES | \
                         WebKit.WebsiteDataTypes.OFFLINE_APPLICATION_CACHE | \
                         WebKit.WebsiteDataTypes.DEVICE_ID_HASH_SALT | \
                         WebKit.WebsiteDataTypes.HSTS_CACHE
        
        # It's an async call
        self.website_data_manager.fetch(
            types_to_query,
            None,
            self._on_get_other_site_data_ready
        )
        print(f"Requesting other site data for origin: {origin.to_string()}")

    def _on_get_other_site_data_ready(self, source_object, res):
        try:
            # fetch_finish returns a GLib.List of WebKit.WebsiteData objects
            data_list = self.website_data_manager.fetch_finish(res)
            
            if not data_list:
                no_data_row = Adw.ActionRow.new()
                no_data_row.set_title("No other site data found.")
                self.other_storage_listbox.append(no_data_row)
                return

            # Consolidate data types for display
            found_types = set()
            total_size_bytes = 0

            for data_item in data_list:
                # data_item is WebKit.WebsiteData, has get_types() and get_size()
                types = data_item.get_types()
                total_size_bytes += data_item.get_size(types)

                # Convert WebKit.WebsiteDataTypes flags to human-readable strings
                if types & WebKit.WebsiteDataTypes.LOCAL_STORAGE: found_types.add("Local Storage")
                if types & WebKit.WebsiteDataTypes.INDEXEDDB_DATABASES: found_types.add("IndexedDB")
                if types & WebKit.WebsiteDataTypes.OFFLINE_APPLICATION_CACHE: found_types.add("App Cache")
                if types & WebKit.WebsiteDataTypes.DEVICE_ID_HASH_SALT: found_types.add("Device ID Hash")
                if types & WebKit.WebsiteDataTypes.HSTS_CACHE: found_types.add("HSTS Cache")

            if found_types:
                types_str = ", ".join(sorted(list(found_types)))
                size_str = self._format_bytes(total_size_bytes)
                
                row = Adw.ActionRow.new()
                row.set_title(f"Found: {types_str}")
                row.set_subtitle(f"Total Size: {size_str}")
                self.other_storage_listbox.append(row)
            else:
                no_data_row = Adw.ActionRow.new()
                no_data_row.set_title("No other site data found.")
                self.other_storage_listbox.append(no_data_row)


        except Exception as e:
            print(f"Error getting other site data: {e}")
            error_row = Adw.ActionRow.new()
            error_row.set_title("Error loading other site data.")
            self.other_storage_listbox.append(error_row)

    def _on_delete_all_other_storage_clicked(self, button):
        if not self.current_domain:
            return

        origin_to_clear_uri = f"https://{self.current_domain}" # Assume HTTPS for clearing
        origin = WebKit.SecurityOrigin.new_for_uri(origin_to_clear_uri)
        
        if not origin:
            self.get_application().get_window_by_id(1)._on_show_notification(
                None, f"Error: Could not determine origin for {self.current_domain}"
            )
            return

        types_to_clear = WebKit.WebsiteDataTypes.ALL & ~WebKit.WebsiteDataTypes.COOKIES # Clear all except cookies
        
        # Clear only for this specific origin
        self.website_data_manager.clear_for_origins(
            types_to_clear,
            Gtk.StringList.new([origin.to_string()]),
            0, # Since (all time)
            None, # Cancellable
            lambda source, res: self._on_clear_other_site_data_finish(source, res, self.current_domain)
        )
        print(f"Clearing other site data for domain: {self.current_domain}")
        self.get_application().get_window_by_id(1)._on_show_notification(
            None, f"Clearing other data for {self.current_domain}"
        )

    def _on_clear_other_site_data_finish(self, source, res, domain):
        try:
            self.website_data_manager.clear_finish(res)
            print(f"Other site data cleared for domain: {domain}")
            self.load_other_site_data() # Reload the list
            self.get_application().get_window_by_id(1)._on_show_notification(
                None, f"Other data cleared for {domain}"
            )
        except Exception as e:
            print(f"Error clearing other site data for {domain}: {e}")
            self.get_application().get_window_by_id(1)._on_show_notification(
                None, f"Error clearing other data for {domain}"
            )

    def _format_bytes(self, size_bytes):
        """Helper to format byte size into human-readable string."""
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB", "TB")
        i = 0
        while size_bytes >= 1024 and i < len(size_name) - 1:
            size_bytes /= 1024
            i += 1
        return f"{size_bytes:.2f} {size_name[i]}"

    def _load_notification_policy(self):
        """Load notification permission policy for the current domain."""
        if not self.current_domain:
            return
        
        # Get notification permission from database
        app = self.get_application()
        if not app or not hasattr(app, 'db_manager'):
            return
        
        permission = app.db_manager.get_notification_permission(self.current_domain)
        
        # Set dropdown selection
        model_strings = [self.notifications_row.get_model().get_string(i) for i in range(self.notifications_row.get_model().get_n_items())]
        try:
            if permission == "allow":
                selected_index = model_strings.index("Allow")
            elif permission == "deny":
                selected_index = model_strings.index("Block")
            else:  # "default"
                selected_index = model_strings.index("Default")
            
            self.notifications_row.set_selected(selected_index)
        except (ValueError, IndexError):
            self.notifications_row.set_selected(0) # Fallback to Default

    def _on_notification_policy_changed(self, dropdown, pspec):
        """Handle notification permission policy change."""
        if not self.current_domain:
            return
        
        app = self.get_application()
        if not app or not hasattr(app, 'db_manager'):
            return
        
        selected_index = dropdown.get_selected()
        model = dropdown.get_model()
        if selected_index < model.get_n_items():
            policy_str = model.get_string(selected_index)
            
            # Map UI strings to database values
            if policy_str == "Allow":
                permission = "allow"
            elif policy_str == "Block":
                permission = "deny"
            else:  # "Default"
                permission = "default"
            
            # Update database
            if permission == "default":
                app.db_manager.remove_notification_permission(self.current_domain)
            else:
                app.db_manager.set_notification_permission(self.current_domain, permission)
            
            debug_print(f"[DEBUG] Notification permission for {self.current_domain} set to {permission}")
            
            # Show confirmation
            if hasattr(app, 'window') and app.window:
                # Emit notification via window's show notification method
                try:
                    app.window._on_show_notification(None, f"Notification permission updated for {self.current_domain}")
                except:
                    pass
