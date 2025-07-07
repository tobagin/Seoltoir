#!/usr/bin/env python3
"""
Main entry point for the Seoltoir web browser application.
"""

import os
# Set GSK renderer to NGL for better performance
os.environ['GSK_RENDERER'] = 'ngl'

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Adw, GLib, Gio, WebKit, Pango
from pathlib import Path

import sys
import argparse
import json

_current_file_path = os.path.abspath(__file__)
_module_root_dir = os.path.dirname(os.path.dirname(_current_file_path)) # Go up from seoltoir/main.py to site-packages
if _module_root_dir not in sys.path:
    sys.path.insert(0, _module_root_dir)

# Set up text domain for internationalization (future prooFing)
APP_ID = "io.github.tobagin.seoltoir"

from .debug import debug_print, set_debug_mode
from .database import DatabaseManager
from .download_manager import DownloadManager
from .container_manager import ContainerManager
from .search_engine_manager import SearchEngineManager
from .adblock_parser import AdblockParser
from .https_everywhere_rules import HttpsEverywhereRules
from .ui_loader import UILoader

# Global debug flag

class SeoltoirApplication(Adw.Application):
    _instance = None
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.window = None

        db_dir = os.path.join(GLib.get_user_data_dir(), APP_ID)
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "browser_data.db")
        self.db_manager = DatabaseManager(db_path)

        settings_for_init = Gio.Settings.new(APP_ID)
        initial_download_dir_uri = settings_for_init.get_string("download-directory")
        
        if initial_download_dir_uri:
            downloads_base_path = GLib.filename_from_uri(initial_download_dir_uri)[0]
            # Fallback if not writable
            if not os.access(os.path.dirname(downloads_base_path), os.W_OK):
                downloads_base_path = str(Path.home() / "Downloads")
        else:
            downloads_base_path = str(Path.home() / "Downloads")
        
        os.makedirs(downloads_base_path, exist_ok=True)
        
        self.download_manager = DownloadManager(GLib.filename_to_uri(downloads_base_path, None))

        SeoltoirApplication._instance = self

        # Initialize search engine manager
        self.search_engine_manager = SearchEngineManager(self.db_manager)

        self.container_manager = ContainerManager(APP_ID)

        # Initialize performance manager
        from .performance_manager import PerformanceManager
        self.performance_manager = PerformanceManager(self)

        self.add_action(Gio.SimpleAction.new("show_history", None))
        self.lookup_action("show_history").connect("activate", self._on_show_history)
        self.add_action(Gio.SimpleAction.new("show_bookmarks", None))

    def do_activate(self):
        if not self.window:
            try:
                from .window import SeoltoirWindow
                self.window = SeoltoirWindow(application=self)
            except Exception as e:
                debug_print("Exception during window import or creation:", e)
                import traceback; traceback.print_exc()
                raise
    
        self.window.present()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gio.Settings.new(APP_ID)

        self.add_action(Gio.SimpleAction.new("show_preferences", None))
        self.lookup_action("show_preferences").connect("activate", self._on_show_preferences)

        # Add missing actions for menu
        self.add_action(Gio.SimpleAction.new("quit", None))
        self.lookup_action("quit").connect("activate", self._on_quit)
        self.add_action(Gio.SimpleAction.new("about", None))
        self.lookup_action("about").connect("activate", self._on_about)
        
        # Set up keyboard shortcuts for media controls (using safe function keys)
        self.set_accels_for_action("win.media_play_pause", ["F9"])
        self.set_accels_for_action("win.media_mute_toggle", ["F10"])
        self.set_accels_for_action("win.media_volume_up", ["<Shift>F9"])
        self.set_accels_for_action("win.media_volume_down", ["<Shift>F10"])
        self.set_accels_for_action("win.media_fullscreen_toggle", ["F11"])
        
        # Set up keyboard shortcuts for find functionality
        self.set_accels_for_action("win.find_in_page", ["<Ctrl>f"])
        self.set_accels_for_action("win.find_next", ["F3"])
        self.set_accels_for_action("win.find_prev", ["<Shift>F3"])
        
        # Set up keyboard shortcut for reader mode
        self.set_accels_for_action("win.toggle_reading_mode", ["<Alt>r"])

        settings = Gio.Settings.new(APP_ID)
        self._apply_theme_settings(settings)
        settings.connect("changed::override-system-theme", self._apply_theme_settings)
        settings.connect("changed::app-theme-variant", self._apply_theme_settings)

        self.add_action(Gio.SimpleAction.new("clear_browsing_data", None))
        self.lookup_action("clear_browsing_data").connect("activate", self._on_clear_browsing_data)
        self.add_action(Gio.SimpleAction.new("focus_window", None))
        self.lookup_action("focus_window").connect("activate", self._on_focus_window)
        self.add_action(Gio.SimpleAction.new("show_passwords", None))
        self.lookup_action("show_passwords").connect("activate", self._on_show_passwords)
        self.add_action(Gio.SimpleAction.new("show_performance_monitor", None))
        self.lookup_action("show_performance_monitor").connect("activate", self._on_show_performance_monitor)
        self.connect("shutdown", self.do_shutdown)
        self.lookup_action("show_bookmarks").connect("activate", self._on_show_bookmarks)

    def do_open(self, files, hint):
        if not self.window:
            from .window import SeoltoirWindow
            self.window = SeoltoirWindow(application=self)
        self.window.present()
        for file in files:
            debug_print(f"Opened file: {file.get_path()}")
            self.window.open_new_tab_with_url(f"file://{file.get_path()}")
            pass

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()
        args = command_line.get_arguments()

        if len(args) > 1:
            url_to_open = args[1]
            if not self.window:
                from .window import SeoltoirWindow
                self.window = SeoltoirWindow(application=self)
            self.window.present()
            self.window.open_new_tab_with_url(url_to_open)
            return 0

        return Gtk.Application.do_command_line(self, command_line)

    def _on_show_preferences(self, action, parameter):
        from .preferences_window import SeoltoirPreferencesWindow
        prefs_window = SeoltoirPreferencesWindow(application=self)
        if self.window:
            prefs_window.set_transient_for(self.window)
            prefs_window.set_modal(True)
        prefs_window.present()

    def _on_show_history(self, action, parameter):
        from .history_manager import HistoryManager
        hist_window = Gtk.Window.new()
        hist_window.set_title("History")
        hist_window.set_default_size(800, 600)
        hist_window.set_child(HistoryManager(self.db_manager))
        hist_window.present()

    def _on_show_bookmarks(self, action, parameter):
        from .bookmark_manager import BookmarkManager
        dialog = Adw.MessageDialog(
            transient_for=self.window,
            modal=True,
            heading="Bookmarks"
        )
        dialog.set_extra_child(BookmarkManager(self.db_manager))
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def _apply_theme_settings(self, settings, *args):
        style_manager = Adw.StyleManager.get_default()
        if settings.get_boolean("override-system-theme"):
            theme_variant = settings.get_string("app-theme-variant")
            style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK if theme_variant == "dark" else Adw.ColorScheme.DEFAULT)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.DEFAULT)

    def _on_clear_browsing_data(self, action, parameter):
        alert = Adw.AlertDialog(
            heading="Clear Browsing Data",
            body="Are you sure you want to clear all browsing data? This will remove history, cookies, cache, and site data for all profiles.",
            close_response="cancel"
        )
        alert.add_response("cancel", "Cancel")
        alert.add_response("clear", "Clear All")
        alert.set_default_response("clear")

        def on_response(dialog, response):
            from gi.repository import WebKit
            if response == "clear":
                # Clear history
                self.db_manager.clear_history()
                # Clear cookies and site data
                app = self
                if hasattr(app, 'container_manager'):
                    for container_id in app.container_manager.container_network_sessions:
                        network_session = app.container_manager.container_network_sessions[container_id]
                        data_manager = network_session.get_website_data_manager()
                        types_to_clear = WebKit.WebsiteDataTypes.ALL
                        data_manager.clear(types_to_clear, 0, None, None)
                else:
                    # Fallback to default context
                    web_context = WebKit.WebContext.get_default()
                    data_manager = web_context.website_data_manager
                    types_to_clear = WebKit.WebsiteDataTypes.ALL
                    data_manager.clear(types_to_clear, 0, None, None)
                # Show notification or toast here if desired

        alert.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.connect("response", on_response)
        alert.present(self.window)

    def _on_quit(self, action, parameter):
        self.quit()

    def _on_focus_window(self, action, parameter):
        """Focus the main browser window."""
        if self.window:
            self.window.present()

    def _on_show_passwords(self, action, parameter):
        """Show the password manager window."""
        # Get password manager from the current browser view
        if self.window and hasattr(self.window, 'tab_view'):
            current_page = self.window.tab_view.get_selected_page()
            if current_page:
                browser_view = current_page.get_child()
                if hasattr(browser_view, 'password_manager') and browser_view.password_manager:
                    from .password_manager_window import PasswordManagerWindow
                    password_window = PasswordManagerWindow(self, browser_view.password_manager)
                    password_window.set_transient_for(self.window)
                    password_window.present()
                    return
        
        # Fallback: create password manager if not available
        try:
            from .password_manager import PasswordManager
            from .password_manager_window import PasswordManagerWindow
            password_manager = PasswordManager(self.db_manager)
            password_window = PasswordManagerWindow(self, password_manager)
            password_window.set_transient_for(self.window)
            password_window.present()
        except Exception as e:
            debug_print(f"[PASSWORD] Error opening password manager: {e}")
            # Show error dialog
            from gi.repository import Adw
            dialog = Adw.AlertDialog(
                heading="Password Manager Error",
                body="Could not open password manager. Please ensure your system keyring is available.",
                close_response="ok"
            )
            dialog.add_response("ok", "OK")
            if self.window:
                dialog.present(self.window)

    def _on_show_performance_monitor(self, action, parameter):
        """Show the performance monitor window."""
        try:
            from .performance_monitor import PerformanceMonitorWindow
            monitor_window = PerformanceMonitorWindow(self)
            monitor_window.set_transient_for(self.window)
            monitor_window.present()
        except Exception as e:
            debug_print(f"[PERF] Error opening performance monitor: {e}")
            # Show error dialog
            from gi.repository import Adw
            dialog = Adw.AlertDialog(
                heading="Performance Monitor Error",
                body="Could not open performance monitor. Please check system requirements.",
                close_response="ok"
            )
            dialog.add_response("ok", "OK")
            if self.window:
                dialog.present(self.window)

    def _on_about(self, action, parameter):
        about_dialog = Adw.AboutWindow()
        about_dialog.set_application_name("Seoltoir")
        about_dialog.set_version("0.1.0")
        about_dialog.set_developer_name("Thiago Fernandes")
        about_dialog.set_license_type(Gtk.License.GPL_3_0)
        about_dialog.set_website("https://github.com/tobagin/seoltoir")
        about_dialog.set_issue_url("https://github.com/tobagin/seoltoir/issues")
        about_dialog.set_support_url("https://github.com/tobagin/seoltoir/discussions")
        about_dialog.set_application_icon("io.github.tobagin.seoltoir")
        about_dialog.set_copyright("© 2025 Thiago Fernandes")
        about_dialog.set_comments(
            "Seoltóir is a modern, privacy-focused web browser built with GTK4 and WebKitGTK. "
            "It features integrated ad and tracker blocking, advanced cookie management, "
            "container tabs for site isolation, and a clean, adaptive interface."
        )
        about_dialog.set_developers(["Thiago Fernandes"])
        about_dialog.set_documenters(["Thiago Fernandes"])
        about_dialog.set_translator_credits("Translations welcome! See GitHub for details.")
        about_dialog.set_transient_for(self.window)
        about_dialog.set_modal(True)
        about_dialog.present()

    def _get_selected_search_engine_url(self, search_query: str) -> str:
        """Get search URL for query, supporting keyword-based search shortcuts."""
        # Parse search input for keyword shortcuts
        search_type, processed_input = self.search_engine_manager.parse_search_input(search_query)
        
        if search_type == "keyword":
            # Keyword search found, return the processed URL
            return processed_input
        else:
            # Regular search using default engine
            return self.search_engine_manager.search_with_engine(search_query)

    def _get_current_session_data(self) -> list[dict]:
        session_data = []
        if self.window:
            for i in range(self.window.tab_view.get_n_pages()):
                page = self.window.tab_view.get_nth_page(i)
                browser_view = page.get_child()
                
                # Try to serialize session state, but handle if method doesn't exist
                serialized_state = ""
                try:
                    if hasattr(browser_view.webview, 'serialize_session_state'):
                        serialized_state_gbytes = browser_view.webview.serialize_session_state()
                        serialized_state = serialized_state_gbytes.get_data().decode('latin1') if serialized_state_gbytes else ""
                except AttributeError:
                    # Session serialization not available in this WebKit version
                    pass
                
                session_data.append({
                    "url": browser_view.get_uri(),
                    "title": browser_view.get_title(),
                    "is_private": browser_view.is_private,
                    "serialized_state": serialized_state
                })
        return session_data

    def do_shutdown(self, *args):
        settings = Gio.Settings.new(APP_ID)
        if settings.get_boolean("delete-cookies-on-close"):
            debug_print("Deleting non-bookmarked cookies...")
            bookmarked_urls = [bm[0] for bm in self.db_manager.get_bookmarks()]
            
            # Get non-bookmarked domains
            non_bookmarked_domains = self.db_manager.get_all_non_bookmarked_domains()
            
            # Delete cookies from all containers
            if hasattr(self, 'container_manager'):
                for container_id in self.container_manager.container_network_sessions:
                    network_session = self.container_manager.container_network_sessions[container_id]
                    cookie_manager = network_session.get_cookie_manager()
                    
                    for domain in non_bookmarked_domains:
                        cookie_manager.delete_cookies_for_domain(domain)
                        debug_print(f"Deleted cookies for non-bookmarked domain: {domain} from container: {container_id}")
            else:
                # Fallback to default network session
                cookie_manager = WebKit.NetworkSession.get_default().get_cookie_manager()
            for domain in non_bookmarked_domains:
                cookie_manager.delete_cookies_for_domain(domain)
                debug_print(f"Deleted cookies for non-bookmarked domain: {domain}")
        
        session_data = self._get_current_session_data()
        self.db_manager.save_session(session_data)

        # Clean up performance manager
        if hasattr(self, 'performance_manager'):
            self.performance_manager.cleanup()

        Gtk.Application.do_shutdown(self)


def main():
    """Main entry point for the application."""
    
    # Check for debug flag before GTK processes arguments
    debug_mode = "--debug" in sys.argv
    if debug_mode:
        # Remove --debug from sys.argv so GTK doesn't see it
        sys.argv.remove("--debug")
    
    # Set debug mode
    set_debug_mode(debug_mode)
    
    GLib.set_prgname(APP_ID)

    app = SeoltoirApplication()
    debug_print("[DEBUG] Application created")
    
    exit_status = app.run(sys.argv)
    
    
    return exit_status

if __name__ == "__main__":
    sys.exit(main())