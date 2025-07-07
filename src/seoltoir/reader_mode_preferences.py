import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
from .ui_loader import UILoader
from .debug import debug_print


@Gtk.Template(filename=UILoader.get_ui_file_path('reader-mode-preferences.ui'))
class ReaderModePreferencesPopover(Gtk.Popover):
    __gtype_name__ = 'ReaderModePreferencesPopover'

    # Template children
    theme_light_button = Gtk.Template.Child()
    theme_dark_button = Gtk.Template.Child()
    theme_sepia_button = Gtk.Template.Child()
    font_size_scale = Gtk.Template.Child()
    font_size_adjustment = Gtk.Template.Child()
    font_family_dropdown = Gtk.Template.Child()
    font_family_list = Gtk.Template.Child()
    line_height_scale = Gtk.Template.Child()
    line_height_adjustment = Gtk.Template.Child()
    column_width_scale = Gtk.Template.Child()
    column_width_adjustment = Gtk.Template.Child()
    auto_enable_check = Gtk.Template.Child()
    show_reading_time_check = Gtk.Template.Child()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Get settings
        app = Gio.Application.get_default()
        self.settings = Gio.Settings.new(app.get_application_id())
        
        # Initialize UI with current settings
        self._load_settings()
        
        # Connect signals
        self._connect_signals()

    def _load_settings(self):
        """Load current settings into UI controls"""
        debug_print("[READER_PREFS] Loading settings into UI")
        
        # Theme
        theme = self.settings.get_string("reader-mode-theme")
        if theme == "light":
            self.theme_light_button.set_active(True)
        elif theme == "dark":
            self.theme_dark_button.set_active(True)
        elif theme == "sepia":
            self.theme_sepia_button.set_active(True)
        
        # Font size
        font_size = self.settings.get_int("reader-mode-font-size")
        self.font_size_adjustment.set_value(font_size)
        
        # Font family
        font_family = self.settings.get_string("reader-mode-font-family")
        font_families = [
            "Georgia, serif",
            "Times New Roman, serif", 
            "Arial, sans-serif",
            "Helvetica, sans-serif",
            "Verdana, sans-serif",
            "Courier New, monospace"
        ]
        try:
            index = font_families.index(font_family)
            self.font_family_dropdown.set_selected(index)
        except ValueError:
            self.font_family_dropdown.set_selected(0)  # Default to Georgia
        
        # Line height
        line_height = self.settings.get_double("reader-mode-line-height")
        self.line_height_adjustment.set_value(line_height)
        
        # Column width
        column_width = self.settings.get_int("reader-mode-column-width")
        self.column_width_adjustment.set_value(column_width)
        
        # Options
        auto_enable = self.settings.get_boolean("reader-mode-auto-enable")
        self.auto_enable_check.set_active(auto_enable)
        
        show_reading_time = self.settings.get_boolean("reader-mode-show-estimated-time")
        self.show_reading_time_check.set_active(show_reading_time)

    def _connect_signals(self):
        """Connect UI signals to handlers"""
        debug_print("[READER_PREFS] Connecting signals")
        
        # Theme buttons
        self.theme_light_button.connect("toggled", self._on_theme_changed, "light")
        self.theme_dark_button.connect("toggled", self._on_theme_changed, "dark")
        self.theme_sepia_button.connect("toggled", self._on_theme_changed, "sepia")
        
        # Scales
        self.font_size_scale.connect("value-changed", self._on_font_size_changed)
        self.line_height_scale.connect("value-changed", self._on_line_height_changed)
        self.column_width_scale.connect("value-changed", self._on_column_width_changed)
        
        # Dropdown
        self.font_family_dropdown.connect("notify::selected", self._on_font_family_changed)
        
        # Checkboxes
        self.auto_enable_check.connect("toggled", self._on_auto_enable_changed)
        self.show_reading_time_check.connect("toggled", self._on_show_reading_time_changed)

    def _on_theme_changed(self, button, theme):
        """Handle theme button toggle"""
        if button.get_active():
            debug_print(f"[READER_PREFS] Theme changed to: {theme}")
            self.settings.set_string("reader-mode-theme", theme)

    def _on_font_size_changed(self, scale):
        """Handle font size scale change"""
        value = int(scale.get_value())
        debug_print(f"[READER_PREFS] Font size changed to: {value}")
        self.settings.set_int("reader-mode-font-size", value)

    def _on_line_height_changed(self, scale):
        """Handle line height scale change"""
        value = scale.get_value()
        debug_print(f"[READER_PREFS] Line height changed to: {value}")
        self.settings.set_double("reader-mode-line-height", value)

    def _on_column_width_changed(self, scale):
        """Handle column width scale change"""
        value = int(scale.get_value())
        debug_print(f"[READER_PREFS] Column width changed to: {value}")
        self.settings.set_int("reader-mode-column-width", value)

    def _on_font_family_changed(self, dropdown, pspec):
        """Handle font family dropdown change"""
        selected = dropdown.get_selected()
        font_families = [
            "Georgia, serif",
            "Times New Roman, serif", 
            "Arial, sans-serif",
            "Helvetica, sans-serif",
            "Verdana, sans-serif",
            "Courier New, monospace"
        ]
        
        if selected < len(font_families):
            font_family = font_families[selected]
            debug_print(f"[READER_PREFS] Font family changed to: {font_family}")
            self.settings.set_string("reader-mode-font-family", font_family)

    def _on_auto_enable_changed(self, check):
        """Handle auto-enable checkbox change"""
        value = check.get_active()
        debug_print(f"[READER_PREFS] Auto-enable changed to: {value}")
        self.settings.set_boolean("reader-mode-auto-enable", value)

    def _on_show_reading_time_changed(self, check):
        """Handle show reading time checkbox change"""
        value = check.get_active()
        debug_print(f"[READER_PREFS] Show reading time changed to: {value}")
        self.settings.set_boolean("reader-mode-show-estimated-time", value)