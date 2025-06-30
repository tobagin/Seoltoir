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
        self.website_data_manager = self.web_context.get_website_data_manager
        self.cookie_manager = self.website_data_manager.get_cookie_manager()

        # Load UI from file
        self.window, self.builder = UILoader.load_template('site-settings-dialog.ui', 'SiteSettingsDialog', application=application)
        
        # Get references to UI widgets
        self.js_dropdown = self.builder.get_object('js_dropdown')
        self.cookie_listbox = self.builder.get_object('cookie_listbox')
        self.delete_all_cookies_button = self.builder.get_object('delete_all_cookies_button')
        self.other_storage_listbox = self.builder.get_object('other_storage_listbox')
        self.delete_all_other_storage_button = self.builder.get_object('delete_all_other_storage_button')
        
        # Set up the window content
        permissions_page = self.builder.get_object('permissions_page')
        cookies_page = self.builder.get_object('cookies_page')
        self.add(permissions_page)
        self.add(cookies_page)
        
        # Set up JavaScript dropdown
        js_model = Gtk.StringList.new(["Allow", "Block"])
        self.js_dropdown.set_model(js_model)
        self.js_dropdown.set_selected(0) # Default to Allow
        
        # Connect button signals
        self.delete_all_cookies_button.connect("clicked", self._on_delete_all_cookies_clicked)
        self.delete_all_other_storage_button.connect("clicked", self._on_delete_all_other_storage_clicked)

        if self.current_domain:
            self.set_subtitle(f"Settings for {self.current_domain}")
        else:
            self.set_subtitle("No site selected")

        self.load_cookies() # Load cookies for the current site
        self.load_other_site_data()

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
        model_strings = [self.js_dropdown.get_model().get_string(i) for i in range(self.js_dropdown.get_model().get_n_items())]
        try:
            selected_index = model_strings.index(current_site_policy)
            self.js_dropdown.set_selected(selected_index)
        except ValueError:
            self.js_dropdown.set_selected(0) # Fallback to Default

        # Update subtitle to indicate effective policy
        if current_site_policy == "Default (Global)":
            effective_policy = "enabled" if global_js_enabled else "disabled"
            self.js_dropdown.set_subtitle(f"Currently: {effective_policy} (based on global setting)")
        else:
            self.js_dropdown.set_subtitle(f"Currently: {current_site_policy.lower()}")

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
        for child in self.cookie_listbox.get_children():
            self.cookie_listbox.remove(child)

        if not self.current_domain:
            return

        # WebKit.CookieManager.get_cookies (context, uri, priority, cancellable, callback)
        self.cookie_manager.get_cookies(
            WebKit.WebContext.get_default(), # Use default web context for fetching cookies
            self.current_uri, # Use current URI to get relevant cookies
            GLib.PRIORITY_DEFAULT,
            None,
            self._on_get_cookies_ready
        )
        # print(f"Requesting cookies for {self.current_uri}")

    def _on_get_cookies_ready(self, source_object, res):
        try:
            cookies = self.cookie_manager.get_cookies_finish(res)
            # print(f"Received {len(cookies)} cookies for {self.current_domain}")
            
            if not cookies:
                no_cookies_row = Adw.ActionRow.new()
                no_cookies_row.set_title("No cookies found for this site.")
                self.cookie_listbox.append(no_cookies_row)
                return

            for cookie in cookies:
                # Filter to only show cookies for the current domain for clarity
                # WebKit's get_cookies is more specific to the URI provided, so this filter might be redundant
                # but good for safety.
                # A cookie's domain might be .example.com, so use endswith
                if cookie.get_domain().endswith(self.current_domain) or cookie.get_domain() == self.current_domain:
                    row = Adw.ActionRow.new()
                    row.set_title(cookie.get_name())
                    row.set_subtitle(f"Value: {cookie.get_value()} | Path: {cookie.get_path()} | Expires: {GLib.DateTime.new_from_unix(cookie.get_expires()).format("%Y-%m-%d %H:%M:%S") if cookie.get_expires() else 'Session'}")
                    
                    delete_button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
                    delete_button.set_tooltip_text("Delete this cookie")
                    delete_button.connect("clicked", self._on_delete_single_cookie_clicked, cookie)
                    row.add_suffix(delete_button)
                    
                    self.cookie_listbox.append(row)
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
        
        self.cookie_manager.delete_cookies_for_domain(self.current_domain)
        self.load_cookies() # Reload the list
        debug_print(f"Deleted all cookies for domain: {self.current_domain}")
        self.get_application().get_window_by_id(1)._on_show_notification(
            None, f"All cookies deleted for {self.current_domain}"
        )

    # --- Tier 8: Other Site Storage Management ---
    def load_other_site_data(self):
        """
        Loads and displays information about other site storage types for the current domain.
        WebKit's API for granular per-origin data sizes is complex.
        For now, we just list the types and provide a clear button.
        """
        for child in self.other_storage_listbox.get_children():
            self.other_storage_listbox.remove(child)

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
                         WebKit.WebsiteDataTypes.WEBSQL_DATABASES | \
                         WebKit.WebsiteDataTypes.OFFLINE_WEB_APPLICATION_CACHE | \
                         WebKit.WebsiteDataTypes.FILE_SYSTEM_DATA | \
                         WebKit.WebsiteDataTypes.PLUGINS_DATA | \
                         WebKit.WebsiteDataTypes.WEB_RTC_DATA
        
        # It's an async call
        self.website_data_manager.get_data_for_origins(
            types_to_query,
            Gtk.StringList.new([origin.to_string()]), # Needs a list of string origins
            None,
            self._on_get_other_site_data_ready
        )
        print(f"Requesting other site data for origin: {origin.to_string()}")

    def _on_get_other_site_data_ready(self, source_object, res):
        try:
            # get_data_for_origins_finish returns a GLib.List of WebKit.WebsiteData objects
            data_list = self.website_data_manager.get_data_for_origins_finish(res)
            
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
                if data_item.get_origin().get_host() == self.current_domain or \
                   data_item.get_origin().get_host().endswith(f".{self.current_domain}"):
                    
                    types = data_item.get_types()
                    total_size_bytes += data_item.get_size()

                    # Convert WebKit.WebsiteDataTypes flags to human-readable strings
                    if types & WebKit.WebsiteDataTypes.LOCAL_STORAGE: found_types.add("Local Storage")
                    if types & WebKit.WebsiteDataTypes.INDEXEDDB_DATABASES: found_types.add("IndexedDB")
                    if types & WebKit.WebsiteDataTypes.WEBSQL_DATABASES: found_types.add("WebSQL")
                    if types & WebKit.WebsiteDataTypes.OFFLINE_WEB_APPLICATION_CACHE: found_types.add("App Cache")
                    if types & WebKit.WebsiteDataTypes.FILE_SYSTEM_DATA: found_types.add("File System")
                    if types & WebKit.WebsiteDataTypes.PLUGINS_DATA: found_types.add("Plugins Data")
                    if types & WebKit.WebsiteDataTypes.WEB_RTC_DATA: found_types.add("WebRTC Data")

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
