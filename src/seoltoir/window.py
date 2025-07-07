import gi
import os
import time
import urllib.parse
import cairo
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, Adw, WebKit, Gio, GLib, Pango, Gdk
from .debug import debug_print

from .browser_view import SeoltoirBrowserView
from .site_settings_dialog import SiteSettingsDialog
from .download_manager import DownloadManager
from .container_manager import ContainerManager # New import
from .import_export_dialog import ImportExportDialog
from .clear_data_dialog import ClearBrowsingDataDialog
from .database import DatabaseManager
from .preferences_window import SeoltoirPreferencesWindow
from .history_manager import HistoryManager
from .bookmark_manager import BookmarkManager
from .ui_loader import UILoader
from .omnibox_entry import OmniboxEntry
from .reader_mode_preferences import ReaderModePreferencesPopover


class SeoltoirWindow(Adw.ApplicationWindow):
    def __init__(self, application: Adw.Application, *args, **kwargs):
        super().__init__(application=application, *args, **kwargs)

        # Load UI from file
        builder = Gtk.Builder()
        builder.add_from_file(UILoader.get_ui_file_path('main-content.ui'))
        
        # Connect the headerbar menu button to the main menu model
        menu_button = builder.get_object('menu_button')
        menu_builder = Gtk.Builder()
        menu_builder.add_from_file(UILoader.get_ui_file_path('menu.ui'))
        menubar = menu_builder.get_object('menubar')
        menu_button.set_menu_model(menubar)
        
        # Get references to UI widgets
        self.back_button = builder.get_object('back_button')
        self.forward_button = builder.get_object('forward_button')
        self.reload_button = builder.get_object('reload_button')
        self.address_bar_container = builder.get_object('address_bar_container')
        self.privacy_indicator = builder.get_object('privacy_indicator')
        self.tab_view = builder.get_object('tab_view')
        self.tab_bar = builder.get_object('tab_bar')
        self.new_tab_button = builder.get_object('new_tab_button')
        self.find_bar = builder.get_object('find_bar')
        self.find_entry = builder.get_object('find_entry')
        self.find_match_counter = builder.get_object('find_match_counter')
        self.find_prev_button = builder.get_object('find_prev_button')
        self.find_next_button = builder.get_object('find_next_button')
        self.find_case_sensitive_button = builder.get_object('find_case_sensitive_button')
        self.find_whole_word_button = builder.get_object('find_whole_word_button')
        self.close_find_button = builder.get_object('close_find_button')
        self.toast_overlay = builder.get_object('toast_overlay')
        self.main_box = builder.get_object('main_box')
        self.zoom_indicator = builder.get_object('zoom_indicator')
        
        # Get headerbar buttons
        self.bookmark_button = builder.get_object('bookmark_button')
        self.downloads_button = builder.get_object('downloads_button')
        self.reader_mode_button = builder.get_object('reader_mode_button')
        self.reader_mode_preferences_button = builder.get_object('reader_mode_preferences_button')
        
        # Set up the window content - use the toast_overlay as our content
        self.set_content(self.toast_overlay)
        
        # Connect signals for navigation buttons to current tab
        self.back_button.connect("clicked", self._on_back_button_clicked)
        self.forward_button.connect("clicked", self._on_forward_button_clicked)
        self.reload_button.connect("clicked", self._on_reload_button_clicked)

        # Connect tab_view signals to update address bar and button sensitivity
        self.tab_view.connect("page-attached", self._on_page_attached)
        self.tab_view.connect("page-detached", self._on_page_closed)
        self.tab_view.connect("notify::selected-page", self._on_selected_page_changed)
        self.tab_view.connect("notify::n-pages", self._on_n_pages_changed)

        # Database Manager from the Application
        self.db_manager = application.db_manager
        
        # Create and add omnibox entry (after db_manager is available)
        self.address_bar = OmniboxEntry(self.db_manager, application.search_engine_manager)
        self.address_bar_container.append(self.address_bar)
        
        # Connect omnibox signals
        self.address_bar.connect("navigate-requested", self._on_navigate_requested)
        self.address_bar.connect("suggestion-selected", self._on_suggestion_selected)
        
        # Connect other UI signals
        self.new_tab_button.connect("clicked", self._on_new_tab_clicked)
        self.find_entry.connect("search-changed", self._on_find_entry_changed)
        self.find_entry.connect("activate", self._on_find_entry_activated)
        self.find_next_button.connect("clicked", self._on_find_next_clicked)
        self.find_prev_button.connect("clicked", self._on_find_prev_clicked)
        self.find_case_sensitive_button.connect("toggled", self._on_find_options_changed)
        self.find_whole_word_button.connect("toggled", self._on_find_options_changed)
        self.close_find_button.connect("clicked", self._on_find_in_page)
        
        # Connect headerbar button signals
        self.bookmark_button.connect("clicked", self._on_bookmark_button_clicked)
        self.downloads_button.connect("clicked", self._on_downloads_button_clicked)
        self.reader_mode_button.connect("toggled", self._on_reader_mode_button_toggled)
        
        # Set up reader mode preferences popover
        self.reader_mode_preferences_popover = ReaderModePreferencesPopover()
        self.reader_mode_preferences_button.set_popover(self.reader_mode_preferences_popover)
        
        # Set up keyboard handling for find bar
        self.find_key_controller = Gtk.EventControllerKey()
        self.find_key_controller.connect("key-pressed", self._on_find_key_pressed)
        self.find_bar.add_controller(self.find_key_controller)

        # Initial Tab - use GSettings for homepage
        settings = Gio.Settings.new(self.get_application().get_application_id())
        initial_homepage = settings.get_string("homepage")
        self.open_new_tab_with_url(initial_homepage)
        
        # Mark startup as complete after a short delay to allow UI to settle
        GLib.timeout_add_seconds(1, self._mark_startup_complete)
        
        # Set up memory usage indicator timer
        self.memory_indicator_timer_id = None
        self._start_memory_indicator_updates()
        
        # Connect to settings changes for memory indicators
        settings.connect("changed::show-memory-usage-indicators", self._on_memory_indicators_setting_changed)

        # Window actions
        self.add_action(Gio.SimpleAction.new("new_tab", None))
        self.lookup_action("new_tab").connect("activate", self._on_new_tab_action_activated)
        self.add_action(Gio.SimpleAction.new("new_private_tab", None))
        self.lookup_action("new_private_tab").connect("activate", self._on_new_private_tab_action_activated)
        self.add_action(Gio.SimpleAction.new("show_site_settings", None))
        self.lookup_action("show_site_settings").connect("activate", self._on_show_site_settings)
        self.add_action(Gio.SimpleAction.new("toggle_reading_mode", None))
        self.lookup_action("toggle_reading_mode").connect("activate", self._on_toggle_reading_mode)
        self.add_action(Gio.SimpleAction.new("new_container_tab", None))
        self.lookup_action("new_container_tab").connect("activate", self._on_new_container_tab)
        self.add_action(Gio.SimpleAction.new("find_in_page", None))
        self.lookup_action("find_in_page").connect("activate", self._on_find_in_page)
        self.add_action(Gio.SimpleAction.new("find_next", None))
        self.lookup_action("find_next").connect("activate", self._on_find_next_action)
        self.add_action(Gio.SimpleAction.new("find_prev", None))
        self.lookup_action("find_prev").connect("activate", self._on_find_prev_action)
        self.add_action(Gio.SimpleAction.new("print_current_page", None))
        self.lookup_action("print_current_page").connect("activate", self._on_print_current_page)
        self.add_action(Gio.SimpleAction.new("print_selection", None))
        self.lookup_action("print_selection").connect("activate", self._on_print_selection)
        self.add_action(Gio.SimpleAction.new("print_to_pdf", None))
        self.lookup_action("print_to_pdf").connect("activate", self._on_print_to_pdf)
        self.add_action(Gio.SimpleAction.new("page_setup", None))
        self.lookup_action("page_setup").connect("activate", self._on_page_setup)
        self.add_action(Gio.SimpleAction.new("show_import_export_dialog", None))
        self.lookup_action("show_import_export_dialog").connect("activate", self._on_show_import_export_dialog)
        
        self.add_action(Gio.SimpleAction.new("show_downloads", None))
        self.lookup_action("show_downloads").connect("activate", self._on_show_downloads)
        self.add_action(Gio.SimpleAction.new("bookmark_current_page", None))
        self.lookup_action("bookmark_current_page").connect("activate", self._on_bookmark_current_page)
        
        # Zoom actions
        self.add_action(Gio.SimpleAction.new("zoom_in", None))
        self.lookup_action("zoom_in").connect("activate", self._on_zoom_in)
        self.add_action(Gio.SimpleAction.new("zoom_out", None))
        self.lookup_action("zoom_out").connect("activate", self._on_zoom_out)
        self.add_action(Gio.SimpleAction.new("zoom_reset", None))
        self.lookup_action("zoom_reset").connect("activate", self._on_zoom_reset)

        # Developer tools actions
        self.add_action(Gio.SimpleAction.new("toggle_developer_tools", None))
        self.lookup_action("toggle_developer_tools").connect("activate", self._on_toggle_developer_tools)
        self.add_action(Gio.SimpleAction.new("show_javascript_console", None))
        self.lookup_action("show_javascript_console").connect("activate", self._on_show_javascript_console)
        self.add_action(Gio.SimpleAction.new("view_page_source", None))
        self.lookup_action("view_page_source").connect("activate", self._on_view_page_source)
        self.add_action(Gio.SimpleAction.new("toggle_responsive_design", None))
        self.lookup_action("toggle_responsive_design").connect("activate", self._on_toggle_responsive_design)

        # Media control actions
        self.add_action(Gio.SimpleAction.new("media_play_pause", None))
        self.lookup_action("media_play_pause").connect("activate", self._on_media_play_pause)
        self.add_action(Gio.SimpleAction.new("media_mute_toggle", None))
        self.lookup_action("media_mute_toggle").connect("activate", self._on_media_mute_toggle)
        self.add_action(Gio.SimpleAction.new("media_volume_up", None))
        self.lookup_action("media_volume_up").connect("activate", self._on_media_volume_up)
        self.add_action(Gio.SimpleAction.new("media_volume_down", None))
        self.lookup_action("media_volume_down").connect("activate", self._on_media_volume_down)
        self.add_action(Gio.SimpleAction.new("media_fullscreen_toggle", None))
        self.lookup_action("media_fullscreen_toggle").connect("activate", self._on_media_fullscreen_toggle)

        # --- Tier 6: Tab Context Menu Actions ---
        self.add_action(Gio.SimpleAction.new("close_current_tab", None))
        self.lookup_action("close_current_tab").connect("activate", self._on_close_current_tab)
        self.add_action(Gio.SimpleAction.new("close_other_tabs", None))
        self.lookup_action("close_other_tabs").connect("activate", self._on_close_other_tabs)
        self.add_action(Gio.SimpleAction.new("duplicate_current_tab", None))
        self.lookup_action("duplicate_current_tab").connect("activate", self._on_duplicate_current_tab)
        self.add_action(Gio.SimpleAction.new("new_private_tab_from_context", None))
        self.lookup_action("new_private_tab_from_context").connect("activate", self._on_new_private_tab_action_activated) # Reuse action

        # Note: focus handling is now done internally by OmniboxEntry

        self.new_tab_button_header = builder.get_object('new_tab_button_header')
        self.new_private_tab_button_header = builder.get_object('new_private_tab_button_header')
        self.new_tab_button_header.connect("clicked", self._on_new_tab_clicked)
        self.new_private_tab_button_header.connect("clicked", self._on_new_private_tab_clicked)

    def _on_navigate_requested(self, omnibox, url):
        """Handle navigation request from omnibox."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.load_url(url)
    
    def _on_suggestion_selected(self, omnibox, url, title):
        """Handle suggestion selection from omnibox."""
        # Same as navigate_requested for now, but could be extended
        # to handle suggestion-specific logic
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.load_url(url)

    def _on_new_tab_action_activated(self, action, parameter):
        self._on_new_tab_clicked(None)

    def _on_new_tab_clicked(self, button):
        settings = Gio.Settings.new(self.get_application().get_application_id())
        homepage = settings.get_string("homepage")
        self.open_new_tab_with_url(homepage, is_private=False)

    def _on_new_private_tab_action_activated(self, action, parameter):
        settings = Gio.Settings.new(self.get_application().get_application_id())
        homepage = settings.get_string("homepage")
        self.open_new_tab_with_url(homepage, is_private=True, container_id="private")
    
    def _on_new_private_tab_clicked(self, button):
        settings = Gio.Settings.new(self.get_application().get_application_id())
        homepage = settings.get_string("homepage")
        self.open_new_tab_with_url(homepage, is_private=True, container_id="private")

    def _on_new_container_tab(self, action, parameter):
        # For simplicity, prompt for container name. A full UI for containers would be better.
        dialog = Adw.MessageDialog.new(self.get_root(), "New Container Tab", "Enter a name for the new container:")
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("create", "Create")
        dialog.set_default_response("create")
        dialog.set_close_response("cancel")

        name_entry = Gtk.Entry.new()
        name_entry.set_placeholder_text("e.g., Shopping, Work, Social")
        content_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 12)
        content_box.set_margin_top(12)
        content_box.set_margin_bottom(12)
        content_box.append(name_entry)
        dialog.set_extra_child(content_box)
        dialog.connect("response", self._on_new_container_tab_response, name_entry)
        dialog.present()

    def open_new_tab_with_url(self, url: str, web_view: WebKit.WebView = None, is_private: bool = False, serialized_state: str = None, container_id: str = "default"):
        # If is_private is True, always use container_id='private'
        if is_private:
            container_id = "private"
        # Create a new browser view or use the provided one (for new windows)
        if web_view:
            # For WebViews created by WebKit itself (e.g., target=_blank), they initially
            # share the parent's context. We need to decide if they should inherit container
            # or be treated as default. For simplicity, they will inherit parent's container.
            parent_view = self.tab_view.get_selected_page().get_child() if self.tab_view.get_selected_page() else None
            browser_view = SeoltoirBrowserView.new_from_webkit_view(web_view, self.db_manager, parent_view.container_id if parent_view else "default")
        else:
            browser_view = SeoltoirBrowserView(self.db_manager, is_private=is_private, container_id=container_id)
            
        # Tier 6: Restore WebKit Session State
        if serialized_state:
            try:
                browser_view.webview.restore_session_state(GLib.Bytes.new(serialized_state.encode('latin1')))
            except Exception as e:
                debug_print(f"Error restoring session state for {url}: {e}")

        # Connect signals
        browser_view.connect("uri-changed", self._on_browser_uri_changed)
        browser_view.connect("title-changed", self._on_browser_title_changed)
        browser_view.connect("favicon-changed", self._on_browser_favicon_changed)
        browser_view.connect("load-changed", self._on_browser_load_changed)
        browser_view.connect("can-go-back-changed", self._on_browser_can_go_back_changed)
        browser_view.connect("can-go-forward-changed", self._on_browser_can_go_forward_changed)
        browser_view.connect("new-window-requested", self._on_new_window_requested)
        #browser_view.connect("create-download", self.get_application().download_manager.add_download)
        
        # Connect view-specific signals for UI updates (not global)
        browser_view.connect("blocked-count-changed", self._on_blocked_count_changed)
        browser_view.connect("show-notification", self._on_show_notification)
        browser_view.connect("zoom-level-changed", self._on_zoom_level_changed)
        browser_view.connect("find-matches-found", self._on_find_matches_found)
        browser_view.connect("load-changed", self._on_browser_load_progress_changed)
        browser_view.connect("reader-mode-changed", self._on_reader_mode_changed)

        if is_private:
            page_title = "Private Tab"
            page_icon = "dialog-password-symbolic"  # More commonly available
        else:
            page_title = "Loading..."
            page_icon = "applications-internet"  # More commonly available

        page = self.tab_view.append(browser_view)
        page.set_title(page_title)
        try:
            icon = Gio.ThemedIcon.new(page_icon)
            debug_print(f"[DEBUG] Setting initial tab icon: {page_icon} -> {icon}")
            page.set_icon(icon)
        except Exception as e:
            debug_print(f"[DEBUG] Error creating initial tab icon for {page_icon}: {e}")
            # Try fallback icon
            try:
                fallback_icon = Gio.ThemedIcon.new("web-browser-symbolic")
                page.set_icon(fallback_icon)
                debug_print(f"[DEBUG] Set fallback icon successfully")
            except Exception as e2:
                debug_print(f"[DEBUG] Error setting fallback icon: {e2}")

        # Load the URL if no web_view was provided
        if not web_view:
            # Set the initial URL in the address bar
            self.address_bar.set_url(url)
            
            # Check if we should defer loading for startup optimization
            app = self.get_application()
            is_initial_tab = self.tab_view.get_n_pages() == 1  # First tab
            
            if (hasattr(app, 'performance_manager') and 
                hasattr(browser_view, 'tab_id') and
                app.performance_manager.should_defer_tab_loading(is_initial_tab)):
                
                # Defer loading and show placeholder
                app.performance_manager.defer_tab_loading(browser_view.tab_id, url, browser_view)
                placeholder_html = app.performance_manager.create_lazy_loading_placeholder(url, "Loading...")
                browser_view.webview.load_html(placeholder_html, None)
            else:
                # Load normally
                browser_view.load_url(url)
        
        self.tab_view.set_selected_page(page)
        
        # Register tab with performance manager
        app = self.get_application()
        if hasattr(app, 'performance_manager'):
            # Generate unique tab ID
            tab_id = f"tab_{int(time.time() * 1000)}_{id(browser_view)}"
            # Store tab ID in browser view for later reference
            browser_view.tab_id = tab_id
            # Register with performance manager (mark as active since it's the new selected tab)
            app.performance_manager.register_tab(tab_id, browser_view, is_active=True)
        
        # Update address bar immediately for the initial page
        if not web_view:
            GLib.idle_add(self._update_address_bar_for_page, page)

    def _on_back_button_clicked(self, button):
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.webview.go_back()

    def _on_forward_button_clicked(self, button):
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.webview.go_forward()

    def _on_reload_button_clicked(self, button):
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.webview.reload()

    def _on_browser_uri_changed(self, browser_view, uri):
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            self.address_bar.set_url(uri)

    def _get_page_for_child(self, child):
        # Helper to find the page for a given child in tab_view
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            if page.get_child() == child:
                return page
        return None

    def _on_browser_title_changed(self, browser_view, title):
        page = self._get_page_for_child(browser_view)
        if page:
            # Show a fallback title if the page title is empty
            if not title or title.strip() == "":
                uri = browser_view.get_uri()
                if uri:
                    # Extract domain from URI for fallback title
                    try:
                        parsed = urllib.parse.urlparse(uri)
                        title = parsed.netloc or "Loading..."
                    except:
                        title = "Loading..."
                else:
                    title = "New Tab"
            # For private tabs, prepend a shield emoji
            if getattr(browser_view, 'is_private', False):
                title = f"🛡️ {title}"
            page.set_title(title)

    def _on_browser_favicon_changed(self, browser_view, favicon):
        debug_print(f"[DEBUG] === _on_browser_favicon_changed CALLED ===")
        debug_print(f"[DEBUG] browser_view: {browser_view}")
        debug_print(f"[DEBUG] favicon: {favicon} (type: {type(favicon)})")
        
        page = self._get_page_for_child(browser_view)
        debug_print(f"[DEBUG] _get_page_for_child returned: {page}")
        
        if page:
            debug_print(f"[DEBUG] Found page for browser_view: {page}")
            debug_print(f"[DEBUG] Page title: {page.get_title()}")
            
            if favicon:
                debug_print(f"[DEBUG] Setting tab icon to favicon: {favicon}")
                try:
                    page.set_icon(favicon)
                    debug_print(f"[DEBUG] Successfully set favicon to page")
                    
                    # Verify the icon was set
                    current_icon = page.get_icon()
                    debug_print(f"[DEBUG] Current page icon after setting: {current_icon}")
                    
                except Exception as e:
                    debug_print(f"[DEBUG] Error setting favicon: {e}")
                    import traceback
                    debug_print(f"[DEBUG] Traceback: {traceback.format_exc()}")
            else:
                debug_print(f"[DEBUG] Favicon is None, keeping current icon")
        else:
            debug_print(f"[DEBUG] No page found for browser_view")
            # Let's debug why we can't find the page
            debug_print(f"[DEBUG] Total pages in tab_view: {self.tab_view.get_n_pages()}")
            for i in range(self.tab_view.get_n_pages()):
                p = self.tab_view.get_nth_page(i)
                child = p.get_child()
                debug_print(f"[DEBUG] Page {i}: {p}, child: {child}, matches: {child == browser_view}")

    def _get_default_icon(self):
        """Get the default icon for tabs."""
        # Try to get the default icon from the application
        try:
            # Use a simple default icon - you can replace this with your app's icon
            return Gio.ThemedIcon.new("applications-internet")
        except:
            try:
                # Fallback to a generic icon
                return Gio.ThemedIcon.new("text-html")
            except:
                # Ultimate fallback - return None to prevent setting invalid icon
                return None

    def _on_browser_load_changed(self, browser_view, load_event):
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            self.back_button.set_sensitive(browser_view.webview.can_go_back())
            self.forward_button.set_sensitive(browser_view.webview.can_go_forward())
    
    def _on_browser_load_progress_changed(self, browser_view, load_event):
        """Handle load progress changes for omnibox progress bar."""
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            # Get load progress from WebKit
            if hasattr(browser_view.webview, 'get_estimated_load_progress'):
                progress = browser_view.webview.get_estimated_load_progress()
                self.address_bar.set_progress(progress)

    def _on_browser_can_go_back_changed(self, browser_view, can_go_back):
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            self.back_button.set_sensitive(can_go_back)

    def _on_browser_can_go_forward_changed(self, browser_view, can_go_forward):
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            self.forward_button.set_sensitive(can_go_forward)

    def _on_page_attached(self, tab_view, page, position):
        browser_view = page.get_child()
        browser_view.connect("uri-changed", self._on_browser_uri_changed)
        browser_view.connect("title-changed", self._on_browser_title_changed)
        browser_view.connect("favicon-changed", self._on_browser_favicon_changed)
        browser_view.connect("load-changed", self._on_browser_load_changed)
        browser_view.connect("can-go-back-changed", self._on_browser_can_go_back_changed)
        browser_view.connect("can-go-forward-changed", self._on_browser_can_go_forward_changed)
        browser_view.connect("new-window-requested", self._on_new_window_requested)
        browser_view.connect("blocked-count-changed", self._on_blocked_count_changed)
        browser_view.connect("show-notification", self._on_show_notification)
        browser_view.connect("zoom-level-changed", self._on_zoom_level_changed)
        browser_view.connect("find-matches-found", self._on_find_matches_found)

    def _on_selected_page_changed(self, tab_view, param):
        # Update performance manager about tab changes
        app = self.get_application()
        if hasattr(app, 'performance_manager'):
            # Mark all tabs as inactive first
            for i in range(tab_view.get_n_pages()):
                other_page = tab_view.get_nth_page(i)
                other_browser_view = other_page.get_child()
                if hasattr(other_browser_view, 'tab_id'):
                    app.performance_manager.set_tab_active(other_browser_view.tab_id, False)
        
        page = tab_view.get_selected_page()
        if page:
            browser_view = page.get_child()
            
            # Mark current tab as active and load if deferred
            if hasattr(app, 'performance_manager') and hasattr(browser_view, 'tab_id'):
                app.performance_manager.set_tab_active(browser_view.tab_id, True)
                # Load deferred tab if it's waiting
                app.performance_manager.load_deferred_tab(browser_view.tab_id)
            
            uri = browser_view.get_uri()
            # Always update address bar, even if URI is None initially
            self.address_bar.set_url(uri if uri else "")
            self.back_button.set_sensitive(browser_view.webview.can_go_back())
            self.forward_button.set_sensitive(browser_view.webview.can_go_forward())
            self.privacy_indicator.set_text(f"{browser_view.blocked_count_for_page} blocked") # Update indicator
            # Update zoom indicator
            self._update_zoom_indicator(browser_view.get_zoom_level())
            # Update reader mode button state
            self._update_reader_mode_button_state()
        else:
            self.get_application().quit()

    def _on_page_closed(self, tab_view, page):
        # Unregister tab from performance manager
        browser_view = page.get_child()
        app = self.get_application()
        if hasattr(app, 'performance_manager') and hasattr(browser_view, 'tab_id'):
            app.performance_manager.unregister_tab(browser_view.tab_id)
        
        if self.tab_view.get_n_pages() == 0:
            self.get_application().quit()

    def _on_bookmark_current_page(self, action, parameter):
        current_page = self.tab_view.get_selected_page()
        if not current_page:
            return

        browser_view = current_page.get_child()
        url = browser_view.get_uri()
        title = browser_view.get_title()

        if url and title:
            if self.db_manager.add_bookmark(url, title):
                debug_print(f"Bookmarked: {title} ({url})")
                self.toast_overlay.add_toast(Adw.Toast.new(f"Bookmarked: {title}"))
            else:
                debug_print(f"Bookmark already exists for: {title}")
                self.toast_overlay.add_toast(Adw.Toast.new(f"Already bookmarked: {title}"))

    def _on_create_download(self, web_context, webkit_download):
        settings = Gio.Settings.new(self.get_application().get_application_id())
        ask_location = settings.get_boolean("ask-download-location")
        default_download_dir_uri = settings.get_string("download-directory")

        if ask_location:
            dialog = Gtk.FileChooserNative.new(
                "Save File",
                self,
                Gtk.FileChooserAction.SAVE,
                "_Save",
                "_Cancel"
            )
            dialog.set_current_name(os.path.basename(GLib.uri_unescape_string(webkit_download.get_uri(), None)))
            if default_download_dir_uri:
                dialog.set_current_folder_uri(default_download_dir_uri)

            dialog.connect("response", self._on_download_dialog_response, webkit_download)
            dialog.show()
            
            return True

        debug_print(f"Download requested for: {webkit_download.get_uri()}")
        self.get_application().download_manager.add_download(webkit_download)
        download_path = GLib.filename_from_uri(default_download_dir_uri, None) if default_download_dir_uri else GLib.get_user_download_dir()
        os.makedirs(download_path, exist_ok=True)
        webkit_download.set_destination(os.path.join(download_path, os.path.basename(GLib.uri_unescape_string(webkit_download.get_uri(), None))))
        return True

    def _on_download_dialog_response(self, dialog, response_id, webkit_download):
        if response_id == Gtk.ResponseType.ACCEPT:
            selected_uri = dialog.get_uri()
            if selected_uri:
                self.get_application().download_manager.add_download(webkit_download)
                webkit_download.set_destination(GLib.filename_from_uri(selected_uri, None))
                debug_print(f"Download will be saved to: {GLib.filename_from_uri(selected_uri, None)}")
            else:
                debug_print("No file selected for download, cancelling.")
                webkit_download.cancel()
        else:
            debug_print("Download cancelled by user via dialog.")
            webkit_download.cancel()
        dialog.destroy()

    def _on_show_downloads(self, action, parameter):
        dialog = Adw.MessageDialog(
            transient_for=self,
            modal=True,
            heading="Downloads"
        )
        dialog.set_extra_child(self.get_application().download_manager)
        dialog.add_response("close", "Close")
        dialog.set_default_response("close")
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def _on_blocked_count_changed(self, browser_view, count):
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            self.privacy_indicator.set_text(f"{count} blocked")

    def _on_show_site_settings(self, action, parameter):
        current_page = self.tab_view.get_selected_page()
        if not current_page:
            return
        browser_view = current_page.get_child()
        current_uri = browser_view.get_uri()
        if current_uri:
            # Get the WebContext from the browser view's webview
            web_context = browser_view.webview.get_context()
            site_settings_dialog = SiteSettingsDialog(self.get_application(), current_uri, web_context)
            site_settings_dialog.set_transient_for(self)
            site_settings_dialog.set_modal(True)
            site_settings_dialog.present()

    def _on_new_container_tab_response(self, dialog, response_id, name_entry):
        if response_id == "create":
            container_name = name_entry.get_text().strip()
            if container_name:
                container_id = self.get_application().container_manager.create_new_custom_container(container_name)
                settings = Gio.Settings.new(self.get_application().get_application_id())
                homepage = settings.get_string("homepage")
                self.open_new_tab_with_url(homepage, container_id=container_id)
                self._on_show_notification(None, f"New container tab '{container_name}' opened.")
            else:
                self._on_show_notification(None, "Container name cannot be empty.")
                dialog.present() # Keep dialog open
                return # Don't destroy dialog yet
        dialog.destroy()


    def _on_print_current_page(self, action, parameter):
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.print_page()

    def _on_print_selection(self, action, parameter):
        """Print only selected text."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.print_page(print_selection_only=True)

    def _on_print_to_pdf(self, action, parameter):
        """Export current page to PDF."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            from .browser_view import SeoltoirPrintManager
            print_manager = SeoltoirPrintManager(browser_view.webview, self)
            print_manager.print_to_pdf()

    def _on_page_setup(self, action, parameter):
        """Show page setup dialog."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            from .browser_view import SeoltoirPrintManager
            print_manager = SeoltoirPrintManager(browser_view.webview, self)
            print_manager.show_page_setup_dialog()


    def _get_find_options(self, backwards=False):
        """Get the current find options based on toggle button states."""
        options = WebKit.FindOptions.WRAP_AROUND
        
        if not self.find_case_sensitive_button.get_active():
            options |= WebKit.FindOptions.CASE_INSENSITIVE
        
        if self.find_whole_word_button.get_active():
            # Note: WebKit doesn't have a built-in whole word option, 
            # this would need to be implemented separately
            pass
        
        if backwards:
            options |= WebKit.FindOptions.BACKWARDS
        
        return options
    
    def _on_find_in_page(self, action, parameter):
        if self.find_bar.get_visible():
            self.find_bar.set_visible(False)
            current_page = self.tab_view.get_selected_page()
            if current_page:
                browser_view = current_page.get_child()
                browser_view.clear_find_results()
        else:
            self.find_bar.set_visible(True)
            self.find_entry.grab_focus()

    def _on_find_entry_changed(self, entry):
        text = entry.get_text()
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if text:
                find_options = self._get_find_options()
                browser_view.find_text(text, find_options, 1000)
                self._show_notification(f"Searching for '{text}'...")
            else:
                browser_view.clear_find_results()
                self.find_match_counter.set_text("0 of 0")
                self._show_notification("Search cleared.")

    def _on_find_entry_activated(self, entry):
        # When Enter is pressed in the find entry, find the next occurrence
        text = entry.get_text()
        current_page = self.tab_view.get_selected_page()
        if current_page and text:
            browser_view = current_page.get_child()
            find_options = self._get_find_options()
            browser_view.find_text(text, find_options, 1000)


    def _on_find_next_clicked(self, button):
        text = self.find_entry.get_text()
        current_page = self.tab_view.get_selected_page()
        if current_page and text:
            browser_view = current_page.get_child()
            find_options = self._get_find_options()
            browser_view.find_text(text, find_options, 1000)


    def _on_find_prev_clicked(self, button):
        text = self.find_entry.get_text()
        current_page = self.tab_view.get_selected_page()
        if current_page and text:
            browser_view = current_page.get_child()
            find_options = self._get_find_options(backwards=True)
            browser_view.find_text(text, find_options, 1000)
    
    def _on_find_options_changed(self, button):
        """Called when case sensitivity or whole word options change."""
        text = self.find_entry.get_text()
        current_page = self.tab_view.get_selected_page()
        if current_page and text:
            browser_view = current_page.get_child()
            find_options = self._get_find_options()
            browser_view.find_text(text, find_options, 1000)
    
    def _on_find_next_action(self, action, parameter):
        """Handle find next action triggered by keyboard shortcut."""
        self._on_find_next_clicked(None)
    
    def _on_find_prev_action(self, action, parameter):
        """Handle find previous action triggered by keyboard shortcut."""
        self._on_find_prev_clicked(None)
    
    def _on_find_key_pressed(self, controller, keyval, keycode, state):
        """Handle key presses in the find bar."""
        if keyval == Gdk.KEY_Escape:
            self._on_find_in_page(None, None)
            return True
        return False
    
    def _on_find_matches_found(self, browser_view, match_count):
        """Handle find matches found signal from browser view."""
        if match_count == 0:
            self.find_match_counter.set_text("0 of 0")
        elif match_count == -1:
            # Search performed but count unknown
            self.find_match_counter.set_text("Searching...")
        else:
            # If we had proper match count, we'd show it here
            self.find_match_counter.set_text(f"Found {match_count}")


    def _on_show_import_export_dialog(self, action, parameter):
        dialog = ImportExportDialog(self.get_application())
        dialog.present()

    def _on_show_notification(self, browser_view, message):
        toast = Adw.Toast.new(message)
        self.toast_overlay.add_toast(toast)

    def _on_bookmark_button_clicked(self, button):
        """Handle bookmark button click in headerbar."""
        self._on_bookmark_current_page(None, None)

    def _on_downloads_button_clicked(self, button):
        """Handle downloads button click in headerbar."""
        self._on_show_downloads(None, None)

    def _on_reader_mode_button_toggled(self, button):
        """Handle reader mode button toggle in headerbar."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'toggle_reader_mode'):
                # Only toggle if button state doesn't match current state
                if button.get_active() != browser_view.is_reading_mode_active:
                    browser_view.toggle_reader_mode()
            else:
                self._on_show_notification(None, "Reader mode is not available for this page.")
                button.set_active(False)  # Reset button state
        else:
            self._on_show_notification(None, "No page selected.")
            button.set_active(False)  # Reset button state

    def _on_reader_mode_changed(self, browser_view, is_active):
        """Handle reader mode state change from browser view"""
        debug_print(f"[READER_MODE] Reader mode changed: {is_active}")
        # Update button state if this is the current tab
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            self.reader_mode_button.set_active(is_active)

    # --- Tier 6: Tab Context Menu Handlers ---
    def _on_tab_right_clicked(self, gesture, n_press, x, y, page):
        """Handles right-click on a tab to show context menu."""
        self.tab_view.set_selected_page(page)
        
        menu = Gio.Menu.new()
        menu.append("Close Tab", "win.close_current_tab")
        menu.append("Close Other Tabs", "win.close_other_tabs")
        menu.append("Duplicate Tab", "win.duplicate_current_tab")
        menu.append("New Private Tab", "win.new_private_tab") # This action is already global

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_relative_to(gesture.get_widget())
        popover.set_constrain_to(None)
        popover.popup()

    def _on_close_current_tab(self, action, parameter):
        current_page = self.tab_view.get_selected_page()
        if current_page:
            self.tab_view.close_page(current_page)

    def _on_close_other_tabs(self, action, parameter):
        current_page = self.tab_view.get_selected_page()
        if not current_page: return

        pages_to_close = []
        for i in range(self.tab_view.get_n_pages()):
            page = self.tab_view.get_nth_page(i)
            if page != current_page:
                pages_to_close.append(page)
        
        for page in pages_to_close:
            self.tab_view.close_page(page)

    def _on_duplicate_current_tab(self, action, parameter):
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            self.open_new_tab_with_url(browser_view.get_uri(), is_private=browser_view.is_private, container_id=browser_view.container_id)

    def _on_toggle_reading_mode(self, action, parameter):
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            debug_print(f"[READER_MODE] Browser view type: {type(browser_view)}")
            debug_print(f"[READER_MODE] Browser view methods: {[method for method in dir(browser_view) if 'reader' in method.lower()]}")
            debug_print(f"[READER_MODE] Has toggle_reader_mode: {hasattr(browser_view, 'toggle_reader_mode')}")
            
            # Force method check
            if hasattr(browser_view, 'toggle_reader_mode'):
                debug_print("[READER_MODE] Calling toggle_reader_mode")
                browser_view.toggle_reader_mode()
                # Update button state after toggle
                GLib.timeout_add(100, self._update_reader_mode_button_state)
            else:
                debug_print("[READER_MODE] toggle_reader_mode method not found via hasattr")
                # Try direct method call as fallback
                try:
                    debug_print("[READER_MODE] Attempting direct method call")
                    browser_view.toggle_reader_mode()
                    debug_print("[READER_MODE] Direct method call succeeded!")
                    GLib.timeout_add(100, self._update_reader_mode_button_state)
                except AttributeError as e:
                    debug_print(f"[READER_MODE] Direct method call failed: {e}")
                    self._on_show_notification(None, "Reading mode method not available")
                except Exception as e:
                    debug_print(f"[READER_MODE] Unexpected error: {e}")
                    self._on_show_notification(None, f"Reader mode error: {e}")
        else:
            debug_print("[READER_MODE] No current page selected")
            self._on_show_notification(None, "No page selected.")
    
    def _update_reader_mode_button_state(self):
        """Update the reader mode button state and availability."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'is_reading_mode_active'):
                # Update button active state
                self.reader_mode_button.set_active(browser_view.is_reading_mode_active)
                # Enable buttons if reader mode is available
                self.reader_mode_button.set_sensitive(True)
                self.reader_mode_preferences_button.set_sensitive(True)
            else:
                self.reader_mode_button.set_active(False)
                self.reader_mode_button.set_sensitive(False)
                self.reader_mode_preferences_button.set_sensitive(False)
        else:
            self.reader_mode_button.set_active(False)
            self.reader_mode_button.set_sensitive(False)
            self.reader_mode_preferences_button.set_sensitive(False)
        return False  # Don't repeat timeout

    def _on_new_window_requested(self, browser_view, webview):
        """Handle requests to open a new window (e.g., target=_blank)."""
        # Open the new WebKit.WebView in a new tab
        self.open_new_tab_with_url(webview.get_uri() or "about:blank", web_view=webview)

    def _on_close_page(self, tab_bar, page):
        self.tab_view.remove(page)

    def _on_n_pages_changed(self, tab_view, param):
        if self.tab_view.get_n_pages() == 0:
            self.get_application().quit()

    def _update_address_bar_for_page(self, page):
        browser_view = page.get_child()
        uri = browser_view.get_uri()
        if uri:
            self.address_bar.set_url(uri)

    # Note: Address bar focus handling is now done internally by OmniboxEntry

    def _on_zoom_in(self, action, parameter):
        """Handle zoom in action."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.zoom_in()

    def _on_zoom_out(self, action, parameter):
        """Handle zoom out action."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.zoom_out()

    def _on_zoom_reset(self, action, parameter):
        """Handle zoom reset action."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            browser_view.zoom_reset()

    def _on_zoom_level_changed(self, browser_view, zoom_level):
        """Handle zoom level changes from browser view."""
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            self._update_zoom_indicator(zoom_level)

    def _update_zoom_indicator(self, zoom_level):
        """Update the zoom indicator in the header bar."""
        zoom_percentage = int(zoom_level * 100)
        self.zoom_indicator.set_text(f"{zoom_percentage}%")
        
        # Show indicator only when zoom is not 100%
        if zoom_percentage != 100:
            self.zoom_indicator.set_visible(True)
        else:
            self.zoom_indicator.set_visible(False)

    # Developer Tools Action Handlers
    def _on_toggle_developer_tools(self, action, parameter):
        """Handle toggle developer tools action."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'toggle_developer_tools'):
                browser_view.toggle_developer_tools()

    def _on_show_javascript_console(self, action, parameter):
        """Handle show JavaScript console action."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'show_javascript_console'):
                browser_view.show_javascript_console()

    def _on_view_page_source(self, action, parameter):
        """Handle view page source action."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'view_page_source'):
                browser_view.view_page_source()

    def _on_toggle_responsive_design(self, action, parameter):
        """Handle toggle responsive design action."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'toggle_responsive_design_mode'):
                browser_view.toggle_responsive_design_mode()

    def _on_media_play_pause(self, action, parameter):
        """Handle media play/pause shortcut."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'webview'):
                # Only activate if address bar is not focused and there are media elements
                script = """
                (function() {
                    // Don't interfere if user is typing in input fields
                    const activeElement = document.activeElement;
                    if (activeElement && (activeElement.tagName === 'INPUT' || 
                                         activeElement.tagName === 'TEXTAREA' || 
                                         activeElement.isContentEditable)) {
                        return false;
                    }
                    
                    const videos = document.querySelectorAll('video, audio');
                    if (videos.length === 0) return false;
                    
                    for (let media of videos) {
                        if (!media.paused || media.readyState >= 2) {
                            if (media.paused) {
                                media.play();
                            } else {
                                media.pause();
                            }
                            return true;
                        }
                    }
                    return false;
                })();
                """
                browser_view.webview.evaluate_javascript(script, -1, None, None, None)

    def _on_media_mute_toggle(self, action, parameter):
        """Handle media mute toggle shortcut."""
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'webview'):
                # Only activate if not typing and there are media elements
                script = """
                (function() {
                    // Don't interfere if user is typing in input fields
                    const activeElement = document.activeElement;
                    if (activeElement && (activeElement.tagName === 'INPUT' || 
                                         activeElement.tagName === 'TEXTAREA' || 
                                         activeElement.isContentEditable)) {
                        return false;
                    }
                    
                    const mediaElements = document.querySelectorAll('video, audio');
                    if (mediaElements.length > 0) {
                        const isMuted = mediaElements[0].muted;
                        mediaElements.forEach(element => {
                            element.muted = !isMuted;
                        });
                        return true;
                    }
                    return false;
                })();
                """
                browser_view.webview.evaluate_javascript(script, -1, None, None, None)

    def _on_media_volume_up(self, action, parameter):
        """Handle media volume up shortcut."""
        # Don't interfere if address bar is focused
        if self.address_bar.has_focus():
            return
            
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'get_tab_volume') and hasattr(browser_view, 'set_tab_volume'):
                current_volume = browser_view.get_tab_volume()
                new_volume = min(1.0, current_volume + 0.1)
                browser_view.set_tab_volume(new_volume)

    def _on_media_volume_down(self, action, parameter):
        """Handle media volume down shortcut."""
        # Don't interfere if address bar is focused
        if self.address_bar.has_focus():
            return
            
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'get_tab_volume') and hasattr(browser_view, 'set_tab_volume'):
                current_volume = browser_view.get_tab_volume()
                new_volume = max(0.0, current_volume - 0.1)
                browser_view.set_tab_volume(new_volume)

    def _on_media_fullscreen_toggle(self, action, parameter):
        """Handle media fullscreen toggle shortcut."""
        # Don't interfere if address bar is focused
        if self.address_bar.has_focus():
            return
            
        current_page = self.tab_view.get_selected_page()
        if current_page:
            browser_view = current_page.get_child()
            if hasattr(browser_view, 'webview'):
                script = """
                (function() {
                    // Don't interfere if user is typing in input fields
                    const activeElement = document.activeElement;
                    if (activeElement && (activeElement.tagName === 'INPUT' || 
                                         activeElement.tagName === 'TEXTAREA' || 
                                         activeElement.isContentEditable)) {
                        return false;
                    }
                    
                    const videos = document.querySelectorAll('video');
                    if (videos.length === 0) return false;
                    
                    // Find the first visible or playing video
                    for (let video of videos) {
                        const rect = video.getBoundingClientRect();
                        const isVisible = rect.width > 0 && rect.height > 0;
                        
                        if (isVisible || !video.paused) {
                            if (document.fullscreenElement || document.webkitFullscreenElement) {
                                // Exit fullscreen
                                if (document.exitFullscreen) {
                                    document.exitFullscreen();
                                } else if (document.webkitExitFullscreen) {
                                    document.webkitExitFullscreen();
                                }
                            } else {
                                // Enter fullscreen
                                if (video.requestFullscreen) {
                                    video.requestFullscreen();
                                } else if (video.webkitRequestFullscreen) {
                                    video.webkitRequestFullscreen();
                                }
                            }
                            return true;
                        }
                    }
                    return false;
                })();
                """
                browser_view.webview.evaluate_javascript(script, -1, None, None, None)

    
    def _mark_startup_complete(self) -> bool:
        """Mark startup as complete in the performance manager."""
        app = self.get_application()
        if hasattr(app, "performance_manager"):
            app.performance_manager.mark_startup_complete()
        return False  # Don't repeat this timer
    
    def _start_memory_indicator_updates(self):
        """Start periodic updates of memory usage indicators in tabs."""
        settings = Gio.Settings.new(self.get_application().get_application_id())
        show_memory_indicators = settings.get_boolean("show-memory-usage-indicators")
        
        if show_memory_indicators and self.memory_indicator_timer_id is None:
            # Update memory indicators every 5 seconds
            self.memory_indicator_timer_id = GLib.timeout_add_seconds(5, self._update_memory_indicators)
            debug_print("[PERF] Started memory usage indicator updates")
    
    def _stop_memory_indicator_updates(self):
        """Stop periodic updates of memory usage indicators."""
        if self.memory_indicator_timer_id:
            GLib.source_remove(self.memory_indicator_timer_id)
            self.memory_indicator_timer_id = None
            debug_print("[PERF] Stopped memory usage indicator updates")
    
    def _update_memory_indicators(self) -> bool:
        """Update memory usage indicators for all tabs."""
        try:
            app = self.get_application()
            settings = Gio.Settings.new(app.get_application_id())
            
            # Check if memory indicators should still be shown
            show_memory_indicators = settings.get_boolean("show-memory-usage-indicators")
            if not show_memory_indicators:
                self._stop_memory_indicator_updates()
                # Clear all tooltips
                for i in range(self.tab_view.get_n_pages()):
                    page = self.tab_view.get_nth_page(i)
                    page.set_tooltip_text("")
                return False
            
            # Update tooltip for each tab with memory usage
            for i in range(self.tab_view.get_n_pages()):
                page = self.tab_view.get_nth_page(i)
                browser_view = page.get_child()
                
                if hasattr(browser_view, 'tab_id') and hasattr(app, 'performance_manager'):
                    tab_id = browser_view.tab_id
                    tab_state = app.performance_manager.tab_states.get(tab_id)
                    
                    if tab_state:
                        # Get memory usage from tab state
                        memory_mb = tab_state.memory_usage / (1024 * 1024) if tab_state.memory_usage > 0 else 0
                        cpu_percent = tab_state.cpu_usage
                        
                        # Create tooltip with memory and performance info
                        tooltip_parts = []
                        
                        # Basic tab info
                        title = page.get_title() or "Loading..."
                        if len(title) > 50:
                            title = title[:47] + "..."
                        tooltip_parts.append(f"Tab: {title}")
                        
                        # Memory usage
                        if memory_mb > 0:
                            tooltip_parts.append(f"Memory: {memory_mb:.1f} MB")
                        else:
                            tooltip_parts.append("Memory: < 0.1 MB")
                        
                        # CPU usage
                        if cpu_percent > 0:
                            tooltip_parts.append(f"CPU: {cpu_percent:.1f}%")
                        
                        # Tab state
                        if tab_state.is_suspended:
                            tooltip_parts.append("Status: Suspended")
                        elif tab_state.is_active:
                            tooltip_parts.append("Status: Active")
                        else:
                            tooltip_parts.append("Status: Background")
                        
                        # Container info if available
                        if hasattr(browser_view, 'container_id') and browser_view.container_id != "default":
                            container_name = browser_view.container_id.title()
                            tooltip_parts.append(f"Container: {container_name}")
                        
                        # Private browsing indicator
                        if getattr(browser_view, 'is_private', False):
                            tooltip_parts.append("Mode: Private")
                        
                        tooltip_text = "\n".join(tooltip_parts)
                        page.set_tooltip_text(tooltip_text)
                    else:
                        # Fallback tooltip without performance data
                        title = page.get_title() or "Loading..."
                        if len(title) > 50:
                            title = title[:47] + "..."
                        page.set_tooltip_text(f"Tab: {title}")
                else:
                    # Simple tooltip for tabs without performance tracking
                    title = page.get_title() or "Loading..."
                    if len(title) > 50:
                        title = title[:47] + "..."
                    page.set_tooltip_text(f"Tab: {title}")
            
            return True  # Continue timer
            
        except Exception as e:
            debug_print(f"[PERF] Error updating memory indicators: {e}")
            return True  # Continue timer despite error
    
    def _on_memory_indicators_setting_changed(self, settings, key):
        """Handle changes to the memory indicators setting."""
        show_memory_indicators = settings.get_boolean("show-memory-usage-indicators")
        
        if show_memory_indicators:
            # Start the timer if not already running
            if self.memory_indicator_timer_id is None:
                self._start_memory_indicator_updates()
        else:
            # Stop the timer and clear tooltips
            self._stop_memory_indicator_updates()
            # Clear all tooltips
            for i in range(self.tab_view.get_n_pages()):
                page = self.tab_view.get_nth_page(i)
                page.set_tooltip_text("")
    
    def cleanup_window(self):
        """Clean up resources when window is closing."""
        self._stop_memory_indicator_updates()
