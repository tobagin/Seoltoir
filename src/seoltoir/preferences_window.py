import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Soup", "3.0") # For checking DoT/DoH
from gi.repository import Gtk, Adw, Gio, GLib
import os
from .ui_loader import UILoader

class SeoltoirPreferencesWindow(Adw.PreferencesWindow):
    
    def __init__(self, application, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Load the UI file
        ui_path = UILoader.get_ui_file_path("preferences-window.ui")
        self.builder = Gtk.Builder()
        self.builder.add_from_file(ui_path)
        
        self.set_application(application)
        self.set_title("Seoltóir Preferences")
        self.set_default_size(600, 400)
        
        # Get all the widgets from the UI file and add them to this window
        self._get_ui_widgets()

        # Get GSettings instance for our app ID
        self.settings = Gio.Settings.new(application.get_application_id())
        
        # Get reference to SearchEngineManager
        self.search_engine_manager = application.search_engine_manager
        
        # Set up all the UI components
        self._setup_ui()
        
        # Connect all signals
        self._connect_signals()
    
    def _get_ui_widgets(self):
        """Get all widgets from the UI file."""
        # General page widgets
        self.homepage_row = self.builder.get_object("homepage_row")
        self.download_dir_row = self.builder.get_object("download_dir_row")
        self.download_dir_button = self.builder.get_object("download_dir_button")
        self.ask_download_location_row = self.builder.get_object("ask_download_location_row")
        self.default_search_engine_combo = self.builder.get_object("default_search_engine_combo")
        self.search_engine_management_group = self.builder.get_object("search_engine_management_group")
        self.add_search_engine_button = self.builder.get_object("add_search_engine_button")
        
        # Privacy page widgets
        self.ad_blocking_row = self.builder.get_object("ad_blocking_row")
        self.user_agent_row = self.builder.get_object("user_agent_row")
        self.canvas_spoofing_row = self.builder.get_object("canvas_spoofing_row")
        self.font_spoofing_row = self.builder.get_object("font_spoofing_row")
        self.hardware_spoofing_row = self.builder.get_object("hardware_spoofing_row")
        self.delete_cookies_row = self.builder.get_object("delete_cookies_row")
        self.webrtc_row = self.builder.get_object("webrtc_row")
        self.adblock_urls_row = self.builder.get_object("adblock_urls_row")
        self.doh_enable_row = self.builder.get_object("doh_enable_row")
        self.doh_provider_row = self.builder.get_object("doh_provider_row")
        self.dot_enable_row = self.builder.get_object("dot_enable_row")
        self.dot_provider_host_row = self.builder.get_object("dot_provider_host_row")
        self.dot_provider_port_row = self.builder.get_object("dot_provider_port_row")
        self.https_enable_row = self.builder.get_object("https_enable_row")
        self.referrer_policy_combo = self.builder.get_object("referrer_policy_combo")
        self.js_enable_row = self.builder.get_object("js_enable_row")
        
        # Appearance page widgets
        self.override_theme_row = self.builder.get_object("override_theme_row")
        self.theme_variant_combo = self.builder.get_object("theme_variant_combo")
        self.font_button = self.builder.get_object("font_button")
        
        # Add the pages to the window
        general_page = self.builder.get_object("general_page")
        privacy_page = self.builder.get_object("privacy_page")
        appearance_page = self.builder.get_object("appearance_page")
        
        # Add pages to this preferences window
        if general_page:
            self.add(general_page)
        if privacy_page:
            self.add(privacy_page)
        if appearance_page:
            self.add(appearance_page)
    
    def _setup_ui(self):
        """Set up all UI components with initial values and settings bindings."""
        # Bind simple settings
        self.settings.bind("homepage", self.homepage_row, "text", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("ask-download-location", self.ask_download_location_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-ad-blocking", self.ad_blocking_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("user-agent", self.user_agent_row, "text", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-canvas-spoofing", self.canvas_spoofing_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-font-spoofing", self.font_spoofing_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-hardware-concurrency-spoofing", self.hardware_spoofing_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("delete-cookies-on-close", self.delete_cookies_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-webrtc", self.webrtc_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-doh", self.doh_enable_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("doh-provider-url", self.doh_provider_row, "text", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-dot", self.dot_enable_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("dot-provider-host", self.dot_provider_host_row, "text", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("dot-provider-port", self.dot_provider_port_row, "value", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-https-everywhere", self.https_enable_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("enable-javascript", self.js_enable_row, "active", Gio.SettingsBindFlags.DEFAULT)
        self.settings.bind("override-system-theme", self.override_theme_row, "active", Gio.SettingsBindFlags.DEFAULT)
        
        # Set up download directory button
        self._setup_download_directory()
        
        # Set up adblock URLs entry
        self.adblock_urls_row.set_text(", ".join(self.settings.get_strv("adblock-filter-urls")))
        
        # Set up combo boxes
        self._setup_referrer_policy_combo()
        self._setup_theme_variant_combo()
        self._setup_search_engine_combo()
        
        # Ensure font size has a default value if not set BEFORE setting up font button
        if self.settings.get_int("default-font-size") <= 0:
            self.settings.set_int("default-font-size", 16)
        
        # Set up font button
        self._setup_font_button()
        
        # Populate search engine listbox
        self._populate_search_engine_listbox()
    
    def _setup_download_directory(self):
        """Set up the download directory button."""
        current_dir_uri = self.settings.get_string("download-directory")
        if current_dir_uri:
            current_path = GLib.filename_from_uri(current_dir_uri)[0]
            self.download_dir_button.set_label(os.path.basename(current_path) or current_path)
        else:
            # Set default XDG Downloads path if not set
            default_path = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
            if default_path:
                self.download_dir_button.set_label(os.path.basename(default_path))
                self.settings.set_string("download-directory", GLib.filename_to_uri(default_path, None))
            else:
                # Fallback to home directory if Downloads doesn't exist
                home_path = GLib.get_home_dir()
                self.download_dir_button.set_label("Home")
                self.settings.set_string("download-directory", GLib.filename_to_uri(home_path, None))
    
    def _setup_referrer_policy_combo(self):
        """Set up the referrer policy combo box."""
        referrer_policy_model = Gtk.StringList.new([
            "no-referrer", "no-referrer-when-downgrade", "origin", "origin-when-cross-origin",
            "same-origin", "strict-origin", "strict-origin-when-cross-origin", "unsafe-url"
        ])
        self.referrer_policy_combo.set_model(referrer_policy_model)
        
        # Set initial value
        current_referrer_policy = self.settings.get_string("referrer-policy")
        if current_referrer_policy:
            for i, item in enumerate(referrer_policy_model):
                if item.get_string() == current_referrer_policy:
                    self.referrer_policy_combo.set_selected(i)
                    break
    
    def _setup_theme_variant_combo(self):
        """Set up the theme variant combo box."""
        theme_variant_model = Gtk.StringList.new(["Auto", "Light", "Dark"])
        self.theme_variant_combo.set_model(theme_variant_model)
        
        # Set initial value from settings
        current_variant = self.settings.get_string("app-theme-variant")
        if current_variant == "auto":
            self.theme_variant_combo.set_selected(0)
        elif current_variant == "light":
            self.theme_variant_combo.set_selected(1)
        elif current_variant == "dark":
            self.theme_variant_combo.set_selected(2)
        else:  # Default
            self.theme_variant_combo.set_selected(0)  # Default to auto
    
    def _setup_search_engine_combo(self):
        """Set up the search engine combo box."""
        self._populate_search_engine_dropdown()
    
    def _setup_font_button(self):
        """Set up the font button with current font family and size."""
        from gi.repository import Pango
        
        # Configure font button display options
        self.font_button.set_use_font(True)  # Show font preview
        self.font_button.set_use_size(True)  # Show size in button
        
        current_font = self.settings.get_string("font-family")
        current_size = self.settings.get_int("default-font-size")
        
        print(f"Loading font settings: family='{current_font}', size={current_size}")
        
        # Create complete font description with both family and size
        if current_font and current_font.strip():
            font_string = f"{current_font} {current_size}"
        else:
            font_string = f"sans-serif {current_size if current_size > 0 else 16}"
            # Save default to settings if empty
            self.settings.set_string("font-family", "sans-serif")
        
        print(f"Setting font string: '{font_string}'")
        
        # Create font description from string
        font_desc = Pango.FontDescription.from_string(font_string)
        
        # Set the font description on the button
        self.font_button.set_font_desc(font_desc)
        
        print(f"Font button initialized with: {font_desc.to_string()}")
    
    def _connect_signals(self):
        """Connect all the signal handlers."""
        self.download_dir_button.connect("clicked", self._on_download_dir_button_clicked)
        self.adblock_urls_row.connect("changed", self._on_adblock_urls_changed)
        self.referrer_policy_combo.connect("notify::selected", self._on_referrer_policy_changed)
        self.theme_variant_combo.connect("notify::selected", self._on_app_theme_variant_changed)
        self.override_theme_row.connect("notify::active", self._on_override_system_theme_changed)
        self.default_search_engine_combo.connect("notify::selected", self._on_default_search_engine_selected)
        self.add_search_engine_button.connect("clicked", self._on_add_search_engine_clicked)
        self.font_button.connect("notify::font-desc", self._on_font_changed)
    
    def _on_adblock_urls_changed(self, entry):
        urls_str = entry.get_text()
        urls_list = [url.strip() for url in urls_str.split(',') if url.strip()]
        self.settings.set_strv("adblock-filter-urls", urls_list)

    def _on_referrer_policy_changed(self, combo_row, pspec):
        selected_index = combo_row.get_selected()
        if selected_index >= 0:
            model = combo_row.get_model()
            if model and selected_index < model.get_n_items():
                item = model.get_item(selected_index)
                policy = item.get_string()
                self.settings.set_string("referrer-policy", policy)
        else:
            self.settings.set_string("referrer-policy", "strict-origin-when-cross-origin")

    def _on_download_dir_button_clicked(self, button):
        """Handle download directory button click to open folder selection dialog."""
        dialog = Gtk.FileDialog.new()
        dialog.set_title("Select Download Directory")
        
        # Set initial directory if available
        current_dir_uri = self.settings.get_string("download-directory")
        if current_dir_uri:
            try:
                current_file = Gio.File.new_for_uri(current_dir_uri)
                dialog.set_initial_folder(current_file)
            except:
                pass  # Fallback to default
        
        dialog.select_folder(self, None, self._on_download_dir_selected)

    def _on_download_dir_selected(self, dialog, result):
        """Handle the result of folder selection."""
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                selected_uri = folder.get_uri()
                selected_path = folder.get_path()
                self.settings.set_string("download-directory", selected_uri)
                # Update button label
                self.download_dir_button.set_label(os.path.basename(selected_path) or selected_path)
                print(f"Default download directory set to: {selected_uri}")
        except Exception as e:
            print(f"Error selecting download directory: {e}")

    def _populate_search_engine_dropdown(self):
        engines = self.search_engine_manager.get_all_engines()
        names = [engine["name"] for engine in engines]
        
        model = Gtk.StringList.new(names)
        self.default_search_engine_combo.set_model(model)
        
        default_engine = self.search_engine_manager.get_default_engine()
        if default_engine and default_engine["name"] in names:
            self.default_search_engine_combo.set_selected(names.index(default_engine["name"]))
        elif names:
            self.default_search_engine_combo.set_selected(0) # Select first if not found

    def _populate_search_engine_listbox(self):
        # Clear existing search engine rows from the group
        # We need to remove rows that are search engine entries (not the combo or button)
        self._clear_search_engine_rows()

        engines = self.search_engine_manager.get_all_engines()
        if not engines:
            # Add a placeholder row if no engines
            placeholder_row = Adw.ActionRow()
            placeholder_row.set_title("No search engines configured.")
            placeholder_row.set_name("search_engine_placeholder")
            self.search_engine_management_group.add(placeholder_row)
            return

        # Add each search engine as an AdwEntryRow
        for i, engine in enumerate(engines):
            self._add_search_engine_row(engine, i)
    
    def _clear_search_engine_rows(self):
        """Remove all dynamically added search engine rows."""
        # Get all children and remove those that are search engine rows
        child = self.search_engine_management_group.get_first_child()
        rows_to_remove = []
        
        while child:
            # Check if this is a search engine row (has our naming convention)
            if hasattr(child, 'get_name') and child.get_name() and \
               (child.get_name().startswith("search_engine_") or child.get_name() == "search_engine_placeholder"):
                rows_to_remove.append(child)
            child = child.get_next_sibling()
        
        for row in rows_to_remove:
            self.search_engine_management_group.remove(row)
    
    def _add_search_engine_row(self, engine, index):
        """Add a search engine as an AdwEntryRow."""
        # Create the entry row
        entry_row = Adw.EntryRow()
        entry_row.set_name(f"search_engine_{engine['id']}")
        
        # Set title and text
        title = engine["name"]
        if engine.get("is_default"):
            title += " (Default)"
        if engine.get("keyword"):
            title += f" [{engine['keyword']}]"
        
        entry_row.set_title(title)
        entry_row.set_text(engine["url"])
        entry_row.set_editable(False)  # Make it read-only for display
        
        # Add edit button
        edit_button = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        edit_button.set_tooltip_text("Edit")
        edit_button.set_valign(Gtk.Align.CENTER)
        edit_button.connect("clicked", self._on_edit_search_engine_clicked, engine)
        entry_row.add_suffix(edit_button)

        # Add delete button for non-builtin engines
        engines = self.search_engine_manager.get_all_engines()
        if not engine.get("is_builtin", False) and len(engines) > 1:
            delete_button = Gtk.Button.new_from_icon_name("user-trash-symbolic")
            delete_button.set_tooltip_text("Delete")
            delete_button.set_valign(Gtk.Align.CENTER)
            delete_button.connect("clicked", self._on_delete_search_engine_clicked, engine)
            entry_row.add_suffix(delete_button)

        # Add the row to the group
        self.search_engine_management_group.add(entry_row)

    def _on_default_search_engine_selected(self, combo_row, pspec):
        selected_index = combo_row.get_selected()
        if selected_index >= 0:
            engines = self.search_engine_manager.get_all_engines()
            if selected_index < len(engines):
                engine = engines[selected_index]
                self.search_engine_manager.set_default_engine(engine["id"])

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

    def _on_search_engine_configured_from_dialog(self, dialog, engine_data, is_new):
        if is_new:
            success = self.search_engine_manager.add_engine(
                name=engine_data["name"],
                url=engine_data["url"],
                keyword=engine_data["keyword"],
                favicon_url=engine_data["favicon_url"],
                suggestions_url=engine_data["suggestions_url"],
                is_default=engine_data["is_default"]
            )
            if success:
                print(f"Added search engine: {engine_data['name']}")
                if hasattr(self.get_application(), 'get_window_by_id') and self.get_application().get_window_by_id(1) and hasattr(self.get_application().get_window_by_id(1), 'toast_overlay'):
                    self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Added search engine: {engine_data['name']}"))
            else:
                print(f"Failed to add search engine: {engine_data['name']}")
                if hasattr(self.get_application(), 'get_window_by_id') and self.get_application().get_window_by_id(1) and hasattr(self.get_application().get_window_by_id(1), 'toast_overlay'):
                    self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Failed to add search engine: {engine_data['name']}"))
        else:
            # For editing, we need the engine ID from the original data
            original_engine_id = dialog.search_engine_data["id"]
            success = self.search_engine_manager.update_engine(
                engine_id=original_engine_id,
                name=engine_data["name"],
                url=engine_data["url"],
                keyword=engine_data["keyword"],
                favicon_url=engine_data["favicon_url"],
                suggestions_url=engine_data["suggestions_url"],
                is_default=engine_data["is_default"]
            )
            if success:
                print(f"Updated search engine: {engine_data['name']}")
                if hasattr(self.get_application(), 'get_window_by_id') and self.get_application().get_window_by_id(1) and hasattr(self.get_application().get_window_by_id(1), 'toast_overlay'):
                    self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Updated search engine: {engine_data['name']}"))
            else:
                print(f"Failed to update search engine: {engine_data['name']}")
                if hasattr(self.get_application(), 'get_window_by_id') and self.get_application().get_window_by_id(1) and hasattr(self.get_application().get_window_by_id(1), 'toast_overlay'):
                    self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Failed to update search engine: {engine_data['name']}"))
        
        # Refresh the UI
        self._populate_search_engine_dropdown()
        self._populate_search_engine_listbox()

    def _on_delete_search_engine_clicked(self, button, engine_data):
        success = self.search_engine_manager.remove_engine(engine_data["id"])
        if success:
            print(f"Deleted search engine: {engine_data['name']}")
            if hasattr(self.get_application(), 'get_window_by_id') and self.get_application().get_window_by_id(1) and hasattr(self.get_application().get_window_by_id(1), 'toast_overlay'):
                self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Deleted search engine: {engine_data['name']}"))
            
            # Refresh the UI
            self._populate_search_engine_dropdown()
            self._populate_search_engine_listbox()
        else:
            print(f"Failed to delete search engine: {engine_data['name']}")
            if hasattr(self.get_application(), 'get_window_by_id') and self.get_application().get_window_by_id(1) and hasattr(self.get_application().get_window_by_id(1), 'toast_overlay'):
                self.get_application().get_window_by_id(1).toast_overlay.add_toast(Adw.Toast.new(f"Failed to delete search engine: {engine_data['name']}"))

    def _on_override_system_theme_changed(self, row, active):
        if active:
            theme_variant_str = self.settings.get_string("app-theme-variant")
            self.get_application().get_style_manager().set_color_scheme(
                Adw.ColorScheme.PREFER_DARK if theme_variant_str == "dark" else Adw.ColorScheme.DEFAULT
            )
        else:
            self.get_application().get_style_manager().set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _on_app_theme_variant_changed(self, combo_row, pspec):
        selected_index = combo_row.get_selected()
        if selected_index == 0:
            theme_variant_str = "auto"
        elif selected_index == 1:
            theme_variant_str = "light"
        elif selected_index == 2:
            theme_variant_str = "dark"
        else:
            theme_variant_str = "auto"  # Default
            
        # Save to settings
        self.settings.set_string("app-theme-variant", theme_variant_str)
        
        if self.settings.get_boolean("override-system-theme"):
            if theme_variant_str == "dark":
                self.get_application().get_style_manager().set_color_scheme(Adw.ColorScheme.PREFER_DARK)
            elif theme_variant_str == "light":
                self.get_application().get_style_manager().set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
            else:  # auto
                self.get_application().get_style_manager().set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _on_font_changed(self, font_button, pspec):
        """Handle font change from font dialog button."""
        font_desc = font_button.get_font_desc()
        if font_desc:
            font_family = font_desc.get_family()
            font_size = font_desc.get_size() // 1024  # Pango size is in 1024ths of a point
            
            if font_family:
                self.settings.set_string("font-family", font_family)
                print(f"Font family changed to: {font_family}")
            
            if font_size > 0:
                self.settings.set_int("default-font-size", font_size)
                print(f"Font size changed to: {font_size}")
            
            print(f"Complete font changed to: {font_desc.to_string()}")