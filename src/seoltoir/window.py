import gi
import os
import urllib.parse
import cairo
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, Adw, WebKit, Gio, GLib, Pango
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
        self.address_bar = builder.get_object('address_bar')
        self.privacy_indicator = builder.get_object('privacy_indicator')
        self.tab_view = builder.get_object('tab_view')
        self.tab_bar = builder.get_object('tab_bar')
        self.new_tab_button = builder.get_object('new_tab_button')
        self.find_bar = builder.get_object('find_bar')
        self.find_entry = builder.get_object('find_entry')
        self.find_prev_button = builder.get_object('find_prev_button')
        self.find_next_button = builder.get_object('find_next_button')
        self.close_find_button = builder.get_object('close_find_button')
        self.toast_overlay = builder.get_object('toast_overlay')
        self.main_box = builder.get_object('main_box')
        
        # Get headerbar buttons
        self.bookmark_button = builder.get_object('bookmark_button')
        self.downloads_button = builder.get_object('downloads_button')
        
        # Set up the window content - use the toast_overlay as our content
        self.set_content(self.toast_overlay)
        
        # Connect signals
        self.address_bar.connect("activate", self._on_address_bar_activate)
        self.new_tab_button.connect("clicked", self._on_new_tab_clicked)
        self.find_entry.connect("search-changed", self._on_find_entry_changed)
        self.find_entry.connect("activate", self._on_find_entry_activated)
        self.find_next_button.connect("clicked", self._on_find_next_clicked)
        self.find_prev_button.connect("clicked", self._on_find_prev_clicked)
        self.close_find_button.connect("clicked", self._on_find_in_page)
        
        # Connect headerbar button signals
        self.bookmark_button.connect("clicked", self._on_bookmark_button_clicked)
        self.downloads_button.connect("clicked", self._on_downloads_button_clicked)
        
        # Connect signals for navigation buttons to current tab
        self.back_button.connect("clicked", self._on_back_button_clicked)
        self.forward_button.connect("clicked", self._on_forward_button_clicked)
        self.reload_button.connect("clicked", self._on_reload_button_clicked)

        # Connect tab_view signals to update address bar and button sensitivity
        self.tab_view.connect("page-attached", self._on_page_attached)
        self.tab_view.connect("notify::selected-page", self._on_selected_page_changed)
        self.tab_view.connect("notify::n-pages", self._on_n_pages_changed)

        # Database Manager from the Application
        self.db_manager = application.db_manager

        # Initial Tab - use GSettings for homepage
        settings = Gio.Settings.new(self.get_application().get_application_id())
        initial_homepage = settings.get_string("homepage")
        self.open_new_tab_with_url(initial_homepage)

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
        self.add_action(Gio.SimpleAction.new("print_current_page", None))
        self.lookup_action("print_current_page").connect("activate", self._on_print_current_page)
        self.add_action(Gio.SimpleAction.new("show_import_export_dialog", None))
        self.lookup_action("show_import_export_dialog").connect("activate", self._on_show_import_export_dialog)
        
        self.add_action(Gio.SimpleAction.new("show_downloads", None))
        self.lookup_action("show_downloads").connect("activate", self._on_show_downloads)
        self.add_action(Gio.SimpleAction.new("bookmark_current_page", None))
        self.lookup_action("bookmark_current_page").connect("activate", self._on_bookmark_current_page)

        # --- Tier 6: Tab Context Menu Actions ---
        self.add_action(Gio.SimpleAction.new("close_current_tab", None))
        self.lookup_action("close_current_tab").connect("activate", self._on_close_current_tab)
        self.add_action(Gio.SimpleAction.new("close_other_tabs", None))
        self.lookup_action("close_other_tabs").connect("activate", self._on_close_other_tabs)
        self.add_action(Gio.SimpleAction.new("duplicate_current_tab", None))
        self.lookup_action("duplicate_current_tab").connect("activate", self._on_duplicate_current_tab)
        self.add_action(Gio.SimpleAction.new("new_private_tab_from_context", None))
        self.lookup_action("new_private_tab_from_context").connect("activate", self._on_new_private_tab_action_activated) # Reuse action

        self.address_bar.connect("notify::has-focus", self._on_address_bar_focus_notify)

        self.new_tab_button_header = builder.get_object('new_tab_button_header')
        self.new_private_tab_button_header = builder.get_object('new_private_tab_button_header')
        self.new_tab_button_header.connect("clicked", self._on_new_tab_clicked)
        self.new_private_tab_button_header.connect("clicked", self._on_new_private_tab_action_activated)

    def _on_address_bar_activate(self, entry):
        url = entry.get_text()
        if not url.startswith("http://") and not url.startswith("https://"):
            if "." in url:
                url = "https://" + url
            else:
                url = self.get_application()._get_selected_search_engine_url(url)

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

        if is_private:
            page_title = "Private Tab"
            page_icon = "security-high-symbolic"
        else:
            page_title = "Loading..."
            page_icon = "web-browser-symbolic"

        page = self.tab_view.append(browser_view)
        page.set_title(page_title)
        icon = Gio.ThemedIcon.new(page_icon)
        page.set_icon(icon)

        # Load the URL if no web_view was provided
        if not web_view:
            # Set the initial URL in the address bar
            self.address_bar.set_text(url)
            browser_view.load_url(url)
        
        self.tab_view.set_selected_page(page)
        
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
            self.address_bar.set_text(uri)

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
        debug_print(f"[DEBUG] _on_browser_favicon_changed called with favicon: {favicon} (type: {type(favicon)})")
        page = self._get_page_for_child(browser_view)
        if page:
            if favicon:
                debug_print(f"[DEBUG] Setting tab icon to favicon: {favicon}")
                page.set_icon(favicon)
            else:
                debug_print(f"[DEBUG] Reverting to default icon")
                page.set_icon(self._get_default_icon())

    def _get_default_icon(self):
        """Get the default icon for tabs."""
        # Try to get the default icon from the application
        try:
            # Use a simple default icon - you can replace this with your app's icon
            return Gio.ThemedIcon.new("applications-internet")
        except:
            # Fallback to a generic icon
            return Gio.ThemedIcon.new("text-html")

    def _on_browser_load_changed(self, browser_view, load_event):
        current_page = self.tab_view.get_selected_page()
        if current_page and current_page.get_child() == browser_view:
            self.back_button.set_sensitive(browser_view.webview.can_go_back())
            self.forward_button.set_sensitive(browser_view.webview.can_go_forward())

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

    def _on_selected_page_changed(self, tab_view, param):
        page = tab_view.get_selected_page()
        if page:
            browser_view = page.get_child()
            uri = browser_view.get_uri()
            # Always update address bar, even if URI is None initially
            self.address_bar.set_text(uri if uri else "")
            self.back_button.set_sensitive(browser_view.webview.can_go_back())
            self.forward_button.set_sensitive(browser_view.webview.can_go_forward())
            self.privacy_indicator.set_text(f"{browser_view.blocked_count_for_page} blocked") # Update indicator
        else:
            self.get_application().quit()

    def _on_page_closed(self, tab_view, page):
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
                browser_view.find_text(text, WebKit.FindOptions.WRAP_AROUND, True)
                self._show_notification(f"Searching for '{text}'...")
            else:
                browser_view.clear_find_results()
                self._show_notification("Search cleared.")

    def _on_find_entry_activated(self, entry):
        # When Enter is pressed in the find entry, find the next occurrence
        text = entry.get_text()
        current_page = self.tab_view.get_selected_page()
        if current_page and text:
            browser_view = current_page.get_child()
            browser_view.find_text(text, WebKit.FindOptions.WRAP_AROUND, True) # Find next


    def _on_find_next_clicked(self, button):
        text = self.find_entry.get_text()
        current_page = self.tab_view.get_selected_page()
        if current_page and text:
            browser_view = current_page.get_child()
            browser_view.find_text(text, WebKit.FindOptions.WRAP_AROUND, True)


    def _on_find_prev_clicked(self, button):
        text = self.find_entry.get_text()
        current_page = self.tab_view.get_selected_page()
        if current_page and text:
            browser_view = current_page.get_child()
            # Use FIND_OPTIONS_BACKWARDS for previous search
            browser_view.find_text(text, WebKit.FindOptions.WRAP_AROUND | WebKit.FindOptions.BACKWARDS, True)


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
            if hasattr(browser_view, 'toggle_reading_mode'):
                browser_view.toggle_reading_mode()
            else:
                self._on_show_notification(None, "Reading mode is not available.")

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
            self.address_bar.set_text(uri)

    def _on_address_bar_focus_notify(self, entry, param):
        if entry.has_focus:
            GLib.idle_add(lambda: entry.select_region(0, -1))
