import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Soup", "3.0") # For checking DoT/DoH
from gi.repository import Gtk, Adw, Gio, GLib

class SeoltoirPreferencesWindow(Adw.PreferencesWindow):
    def __init__(self, application, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_application(application)
        self.set_title("Seoltóir Preferences")
        self.set_default_size(600, 400)

        # Get GSettings instance for our app ID
        self.settings = Gio.Settings.new(application.get_application_id())

        # General Page
        general_page = Adw.PreferencesPage.new()
        general_page.set_title("General")
        general_page.set_icon_name("document-page-setup-symbolic")
        self.add(general_page)

        general_group = Adw.PreferencesGroup.new()
        general_group.set_title("Startup")
        general_page.add(general_group)

        # Homepage setting
        homepage_row = Adw.EntryRow.new()
        homepage_row.set_title("Homepage")
        homepage_row.set_property("placeholder-text", "e.g., https://www.duckduckgo.com")
        general_group.add(homepage_row)
        self.settings.bind("homepage", homepage_row, "text", Gio.SettingsBindFlags.DEFAULT)

        # --- Tier 7 / 9: Downloads Settings ---
        downloads_group = Adw.PreferencesGroup.new() # Already exists from Tier 7
        downloads_group.set_title("Downloads")
        general_page.add(downloads_group)

        # Default Download Directory
        self.download_dir_row = Adw.ActionRow.new()
        self.download_dir_row.set_title("Default Download Directory")
        downloads_group.add(self.download_dir_row)

        # FileChooserButton for selecting directory
        self.download_dir_chooser = Gtk.FileChooserButton.new(
            "Select Download Directory", Gtk.FileChooserAction.SELECT_FOLDER
        )
        self.download_dir_chooser.set_valign(Gtk.Align.CENTER)
        self.download_dir_row.add_suffix(self.download_dir_chooser)
        
        # Set initial value from GSettings
        current_dir_uri = self.settings.get_string("download-directory")
        if current_dir_uri:
            self.download_dir_chooser.set_uri(current_dir_uri)
        else:
            # Set default XDG Downloads path if not set
            self.download_dir_chooser.set_uri(GLib.filename_to_uri(GLib.get_user_download_dir(), None))

        self.download_dir_chooser.connect("file-set", self._on_download_dir_set)

        # Always Ask Where to Save Files
        ask_download_location_row = Adw.SwitchRow.new()
        ask_download_location_row.set_title("Always ask where to save files")
        downloads_group.add(ask_download_location_row)
        self.settings.bind("ask-download-location", ask_download_location_row, "active", Gio.SettingsBindFlags.DEFAULT)

        # Privacy & Security Page
        privacy_page = Adw.PreferencesPage.new()
        privacy_page.set_title("Privacy & Security")
        privacy_page.set_icon_name("dialog-password-symbolic")
        self.add(privacy_page)

        privacy_group = Adw.PreferencesGroup.new()
        privacy_group.set_title("Content Blocking")
        privacy_page.add(privacy_group)

        # Enable Ad Blocking switch
        ad_blocking_row = Adw.SwitchRow.new()
        ad_blocking_row.set_title("Enable Ad and Tracker Blocking")
        ad_blocking_row.set_subtitle("Blocks ads, tracking scripts, and malicious domains.")
        privacy_group.add(ad_blocking_row)
        self.settings.bind("enable-ad-blocking", ad_blocking_row, "active", Gio.SettingsBindFlags.DEFAULT)

        # User Agent String setting
        user_agent_group = Adw.PreferencesGroup.new()
        user_agent_group.set_title("Fingerprinting Resistance")
        privacy_page.add(user_agent_group)

        user_agent_row = Adw.EntryRow.new()
        user_agent_row.set_title("User Agent String")
        user_agent_row.set_subtitle("Leave empty for default. Set a generic one for better privacy.")
        user_agent_row.set_property("placeholder-text", "e.g., Mozilla/5.0 (X11; Linux x86_64) ...")
        user_agent_group.add(user_agent_row)
        self.settings.bind("user-agent", user_agent_row, "text", Gio.SettingsBindFlags.DEFAULT)

        # --- Tier 8: Granular Fingerprinting Toggles ---
        canvas_spoofing_row = Adw.SwitchRow.new()
        canvas_spoofing_row.set_title("Enable Canvas Fingerprinting Spoofing")
        canvas_spoofing_row.set_subtitle("Adds noise to canvas rendering to make fingerprinting harder.")
        user_agent_group.add(canvas_spoofing_row)
        self.settings.bind("enable-canvas-spoofing", canvas_spoofing_row, "active", Gio.SettingsBindFlags.DEFAULT)

        font_spoofing_row = Adw.SwitchRow.new()
        font_spoofing_row.set_title("Enable Font Enumeration Spoofing")
        font_spoofing_row.set_subtitle("Spoofs the list of fonts reported to websites.")
        user_agent_group.add(font_spoofing_row)
        self.settings.bind("enable-font-spoofing", font_spoofing_row, "active", Gio.SettingsBindFlags.DEFAULT)

        hardware_spoofing_row = Adw.SwitchRow.new()
        hardware_spoofing_row.set_title("Enable Hardware Concurrency Spoofing")
        hardware_spoofing_row.set_subtitle("Spoofs reported CPU core count and device memory.")
        user_agent_group.add(hardware_spoofing_row)
        self.settings.bind("enable-hardware-concurrency-spoofing", hardware_spoofing_row, "active", Gio.SettingsBindFlags.DEFAULT)


        # Cookie Management
        cookie_group = Adw.PreferencesGroup.new()
        cookie_group.set_title("Cookie Management")
        privacy_page.add(cookie_group)
        delete_cookies_row = Adw.SwitchRow.new()
        delete_cookies_row.set_title("Delete non-bookmarked cookies on close")
        delete_cookies_row.set_subtitle("Retains cookies only for bookmarked websites.")
        cookie_group.add(delete_cookies_row)
        self.settings.bind("delete-cookies-on-close", delete_cookies_row, "active", Gio.SettingsBindFlags.DEFAULT)

        # WebRTC setting
        webrtc_group = Adw.PreferencesGroup.new()
        webrtc_group.set_title("WebRTC")
        privacy_page.add(webrtc_group)
        webrtc_row = Adw.SwitchRow.new()
        webrtc_row.set_title("Enable WebRTC")
        webrtc_row.set_subtitle("Disabling can prevent IP leaks, but may break video/audio calls.")
        webrtc_group.add(webrtc_row)
        self.settings.bind("enable-webrtc", webrtc_row, "active", Gio.SettingsBindFlags.DEFAULT)

        # Adblock Filter Lists
        adblock_group = Adw.PreferencesGroup.new()
        adblock_group.set_title("Adblock Filter Lists")
        privacy_page.add(adblock_group)
        adblock_urls_row = Adw.EntryRow.new()
        adblock_urls_row.set_title("Filter List URLs")
        adblock_urls_row.set_subtitle("Comma-separated URLs (e.g., EasyList.txt)")
        adblock_urls_row.set_property("placeholder-text", "https://easylist.to/easylist/easylist.txt")
        adblock_group.add(adblock_urls_row)
        adblock_urls_row.set_text(", ".join(self.settings.get_strv("adblock-filter-urls")))
        adblock_urls_row.connect("changed", self._on_adblock_urls_changed)

        # --- Tier 9: DNS over TLS (DoT) ---
        doh_group = Adw.PreferencesGroup.new()
        doh_group.set_title("DNS over HTTPS")
        privacy_page.add(doh_group)
        doh_enable_row = Adw.SwitchRow.new()
        doh_enable_row.set_title("Enable DNS over HTTPS")
        doh_enable_row.set_subtitle("Encrypts DNS queries to prevent snooping. Mutually exclusive with DoT.")
        doh_group.add(doh_enable_row)
        self.settings.bind("enable-doh", doh_enable_row, "active", Gio.SettingsBindFlags.DEFAULT)
        doh_provider_row = Adw.EntryRow.new()
        doh_provider_row.set_title("DoH Provider URL")
        doh_provider_row.set_property("placeholder-text", "e.g., https://dns.google/dns-query")
        doh_group.add(doh_provider_row)
        self.settings.bind("doh-provider-url", doh_provider_row, "text", Gio.SettingsBindFlags.DEFAULT)

        dot_group = Adw.PreferencesGroup.new()
        dot_group.set_title("DNS over TLS")
        privacy_page.add(dot_group)
        dot_enable_row = Adw.SwitchRow.new()
        dot_enable_row.set_title("Enable DNS over TLS")
        dot_enable_row.set_subtitle("Encrypts DNS queries using TLS. Mutually exclusive with DoH.")
        dot_group.add(dot_enable_row)
        self.settings.bind("enable-dot", dot_enable_row, "active", Gio.SettingsBindFlags.DEFAULT)
        dot_provider_host_row = Adw.EntryRow.new()
        dot_provider_host_row.set_title("DoT Provider Host")
        dot_provider_host_row.set_property("placeholder-text", "e.g., dns.google")
        dot_group.add(dot_provider_host_row)
        self.settings.bind("dot-provider-host", dot_provider_host_row, "text", Gio.SettingsBindFlags.DEFAULT)
        dot_provider_port_row = Adw.SpinRow.new()
        dot_provider_port_row.set_title("DoT Provider Port")
        dot_provider_port_row.set_range(1, 65535)
        dot_provider_port_row.set_increments(1, 10)
        dot_group.add(dot_provider_port_row)
        self.settings.bind("dot-provider-port", dot_provider_port_row, "value", Gio.SettingsBindFlags.DEFAULT)

        # Tier 9: HTTPS Everywhere
        https_everywhere_group = Adw.PreferencesGroup.new()
        https_everywhere_group.set_title("HTTPS Everywhere")
        privacy_page.add(https_everywhere_group)
        https_enable_row = Adw.SwitchRow.new()
        https_enable_row.set_title("Enable HTTPS Everywhere Rules")
        https_enable_row.set_subtitle("Automatically upgrades HTTP to HTTPS where available based on a ruleset.")
        https_everywhere_group.add(https_enable_row)
        self.settings.bind("enable-https-everywhere", https_enable_row, "active", Gio.SettingsBindFlags.DEFAULT)
        # Rule URL will be a read-only display, update is manual or periodic in background
        # For now, no URL edit field.

        # Referrer Policy
        referrer_group = Adw.PreferencesGroup.new()
        referrer_group.set_title("Referrer Policy")
        privacy_page.add(referrer_group)
        referrer_policy_model = Gtk.StringList.new(["no-referrer", "no-referrer-when-downgrade", "origin", "origin-when-cross-origin", "same-origin", "strict-origin", "strict-origin-when-cross-origin", "unsafe-url"])
        self.referrer_policy_dropdown = Gtk.DropDown.new(referrer_policy_model, None)
        # Set initial value
        current_referrer_policy = self.settings.get_string("referrer-policy")
        if current_referrer_policy:
            for i, item in enumerate(referrer_policy_model):
                if item.get_string() == current_referrer_policy:
                    self.referrer_policy_dropdown.set_selected(i)
                    break
        self.referrer_policy_dropdown.connect("notify::selected-item", self._on_referrer_policy_changed)
        referrer_policy_row = Adw.ActionRow.new()
        referrer_policy_row.set_title("Referrer Policy")
        referrer_policy_row.add_suffix(self.referrer_policy_dropdown)
        referrer_group.add(referrer_policy_row)

        # JavaScript Control
        js_group = Adw.PreferencesGroup.new()
        js_group.set_title("JavaScript Control")
        privacy_page.add(js_group)
        js_enable_row = Adw.SwitchRow.new()
        js_enable_row.set_title("Enable JavaScript Globally")
        js_enable_row.set_subtitle("Disable JavaScript for all websites by default. Use per-site settings to override.")
        js_group.add(js_enable_row)
        self.settings.bind("enable-javascript", js_enable_row, "active", Gio.SettingsBindFlags.DEFAULT)

        # Per-site JavaScript exceptions will be managed in a separate site settings dialog.

        # Tier 9: Search Engine Management (Expanded from Tier 7)
        search_engine_management_group = Adw.PreferencesGroup.new()
        search_engine_management_group.set_title("Search Engine Management")
        general_page.add(search_engine_management_group)

        # Default Search Engine Dropdown
        self.default_search_engine_dropdown = Gtk.DropDown.new_from_strings([]) # Will be populated dynamically
        self.default_search_engine_dropdown.set_valign(Gtk.Align.CENTER)
        default_search_engine_row = Adw.ActionRow.new()
        default_search_engine_row.set_title("Default Search Engine")
        default_search_engine_row.add_suffix(self.default_search_engine_dropdown)
        search_engine_management_group.add(default_search_engine_row)
        self._populate_search_engine_dropdown()
        self.default_search_engine_dropdown.connect("notify::selected-item", self._on_default_search_engine_selected)

        # List of Search Engines
        search_engine_list_row = Adw.ActionRow.new()
        search_engine_list_row.set_title("Configured Search Engines")
        
        # A simple list box for showing search engines
        self.search_engine_listbox = Gtk.ListBox.new()
        self.search_engine_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        search_engine_list_row.set_child(self.search_engine_listbox)
        
        search_engine_management_group.add(search_engine_list_row)

        add_search_engine_button = Gtk.Button.new_with_label("Add New")
        add_search_engine_button.set_tooltip_text("Add new search engine")
        add_search_engine_button.add_css_class("suggested-action")
        add_search_engine_button.connect("clicked", self._on_add_search_engine_clicked)
        
        search_engine_management_group.add(add_search_engine_button)

        # Listen to changes in the GSettings array
        self.settings.connect("changed::search-engines", self._on_search_engines_changed)

        # Populate the list box initially
        self._populate_search_engine_listbox()

        # Tier 9: Appearance Settings
        appearance_page = Adw.PreferencesPage.new()
        appearance_page.set_title("Appearance")
        appearance_page.set_icon_name("preferences-desktop-theme-symbolic")
        self.add(appearance_page)

        theme_group = Adw.PreferencesGroup.new()
        theme_group.set_title("Theme")
        appearance_page.add(theme_group)

        override_theme_row = Adw.SwitchRow.new()
        override_theme_row.set_title("Override System Theme")
        theme_group.add(override_theme_row)
        self.settings.bind("override-system-theme", override_theme_row, "active", Gio.SettingsBindFlags.DEFAULT)
        override_theme_row.connect("notify::active", self._on_override_system_theme_changed)
        
        theme_variant_model = Gtk.StringList.new(["light", "dark"])
        self.theme_variant_dropdown = Gtk.DropDown.new(theme_variant_model, None)
        theme_variant_row = Adw.ActionRow.new()
        theme_variant_row.set_title("Theme Variant")
        theme_variant_row.add_suffix(self.theme_variant_dropdown)
        theme_group.add(theme_variant_row)
        self.settings.bind("app-theme-variant", self.theme_variant_dropdown, "selected-item", Gio.SettingsBindFlags.DEFAULT)
        self.theme_variant_dropdown.connect("notify::selected-item", self._on_app_theme_variant_changed)


        font_group = Adw.PreferencesGroup.new()
        font_group.set_title("Fonts")
        appearance_page.add(font_group)

        font_family_row = Adw.EntryRow.new()
        font_family_row.set_title("Font Family")
        font_family_row.set_property("placeholder-text", "e.g., sans-serif")
        font_group.add(font_family_row)
        self.settings.bind("font-family", font_family_row, "text", Gio.SettingsBindFlags.DEFAULT)

        font_size_row = Adw.SpinRow.new()
        font_size_row.set_title("Default Font Size")
        font_size_row.set_range(8, 32)
        font_size_row.set_increments(1, 2)
        font_group.add(font_size_row)
        self.settings.bind("default-font-size", font_size_row, "value", Gio.SettingsBindFlags.DEFAULT)

    def _on_adblock_urls_changed(self, entry):
        urls_str = entry.get_text()
        urls_list = [url.strip() for url in urls_str.split(',') if url.strip()]
        self.settings.set_strv("adblock-filter-urls", urls_list)

    def _on_referrer_policy_changed(self, dropdown, pspec):
        selected_item = dropdown.get_selected_item()
        if selected_item:
            policy = selected_item.get_string()
            self.settings.set_string("referrer-policy", policy)
        else:
            self.settings.set_string("referrer-policy", "strict-origin-when-cross-origin")

    # --- Tier 7: Download Settings Handlers ---
    def _on_download_dir_set(self, chooser):
        selected_uri = chooser.get_uri()
        self.settings.set_string("download-directory", selected_uri)
        print(f"Default download directory set to: {selected_uri}")

    # --- Tier 9: Search Engine Management Handlers ---
    def _populate_search_engine_dropdown(self):
        search_engines = self.settings.get_value("search-engines").unpack()
        names = [se["name"] for se in search_engines]
        
        model = Gtk.StringList.new(names)
        self.default_search_engine_dropdown.set_model(model)
        
        selected_name = self.settings.get_string("selected-search-engine-name")
        if selected_name in names:
            self.default_search_engine_dropdown.set_selected(names.index(selected_name))
        else:
            self.default_search_engine_dropdown.set_selected(0) # Select first if not found

    def _populate_search_engine_listbox(self):
        for child in self.search_engine_listbox.get_children():
            self.search_engine_listbox.remove(child)

        search_engines = self.settings.get_value("search-engines").unpack()
        if not search_engines:
            row = Adw.ActionRow.new()
            row.set_title("No search engines configured.")
            self.search_engine_listbox.append(row)
            return

        for se in search_engines:
            row = Adw.ActionRow.new()
            row.set_title(se["name"])
            row.set_subtitle(se["url"])
            
            edit_button = Gtk.Button.new_from_icon_name("document-edit-symbolic")
            edit_button.set_tooltip_text("Edit")
            edit_button.connect("clicked", self._on_edit_search_engine_clicked, se)
            row.add_suffix(edit_button)

            delete_button = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            delete_button.set_tooltip_text("Delete")
            delete_button.connect("clicked", self._on_delete_search_engine_clicked, se)
            row.add_suffix(delete_button)

            self.search_engine_listbox.append(row)

    def _on_default_search_engine_selected(self, dropdown, pspec):
        selected_item = dropdown.get_selected_item()
        if selected_item:
            self.settings.set_string("selected-search-engine-name", selected_item.get_string())

    def _on_search_engines_changed(self, settings, key):
        self._populate_search_engine_dropdown()
        self._populate_search_engine_listbox()

    def _on_add_search_engine_clicked(self, button):
        from .search_engine_dialog import SearchEngineDialog
        dialog = SearchEngineDialog(self.get_application())
        dialog.connect("search-engine-configured", self._on_search_engine_configured_from_dialog)
        dialog.present()

    def _on_edit_search_engine_clicked(self, button, engine_data):
        from .search_engine_dialog import SearchEngineDialog
        dialog = SearchEngineDialog(self.get_application(), search_engine_data=engine_data)
        dialog.connect("search-engine-configured", self._on_search_engine_configured_from_dialog)
        dialog.present()

    def _on_search_engine_configured_from_dialog(self, dialog, name, url, is_new):
        search_engines = self.settings.get_value("search-engines").unpack()
        
        if is_new:
            if any(se['name'] == name for se in search_engines):
                print(f"Search engine '{name}' already exists. Cannot add duplicate.")
                self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Search engine '{name}' already exists."))
                return
            new_engine = {"name": name, "url": url}
            search_engines.append(new_engine)
            print(f"Added search engine: {name}")
            self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Added search engine: {name}"))
        else:
            original_name = dialog.search_engine_data["name"]
            found = False
            for se in search_engines:
                if se['name'] == original_name:
                    se['name'] = name
                    se['url'] = url
                    found = True
                    break
            if found:
                print(f"Updated search engine: {name}")
                self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Updated search engine: {name}"))
            else:
                print(f"Error: Could not find search engine '{original_name}' to edit.")
                self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Error updating search engine."))
        
        self.settings.set_value("search-engines", GLib.Variant("a{sv}", search_engines))

    def _on_delete_search_engine_clicked(self, button, engine_data):
        search_engines = self.settings.get_value("search-engines").unpack()
        
        new_engines = [se for se in search_engines if se["name"] != engine_data["name"]]
        
        if self.settings.get_string("selected-search-engine-name") == engine_data["name"]:
            if new_engines:
                self.settings.set_string("selected-search-engine-name", new_engines[0]["name"])
            else:
                self.settings.set_string("selected-search-engine-name", "")
        self.settings.set_value("search-engines", GLib.Variant("a{sv}", new_engines))
        print(f"Deleted search engine: {engine_data['name']}")
        self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Deleted search engine: {engine_data['name']}"))

    # --- Tier 9: Appearance Settings Handlers ---
    def _on_override_system_theme_changed(self, row, active):
        if active:
            theme_variant_str = self.settings.get_string("app-theme-variant")
            self.get_application().get_style_manager().set_color_scheme(
                Adw.ColorScheme.PREFER_DARK if theme_variant_str == "dark" else Adw.ColorScheme.DEFAULT
            )
        else:
            self.get_application().get_style_manager().set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _on_app_theme_variant_changed(self, dropdown, pspec):
        if self.settings.get_boolean("override-system-theme"):
            selected_item = dropdown.get_selected_item()
            if selected_item:
                theme_variant_str = selected_item.get_string()
                self.get_application().get_style_manager().set_color_scheme(
                    Adw.ColorScheme.PREFER_DARK if theme_variant_str == "dark" else Adw.ColorScheme.DEFAULT
                )
