import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0") # For WebKit.Download
from gi.repository import Gtk, Adw, Gio, GLib, WebKit, Gdk
from pathlib import Path
from .debug import debug_print

from .ui_loader import UILoader
import os
import shutil

class DownloadManager(Adw.NavigationPage):
    def __init__(self, initial_download_dir_uri: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # List to keep track of active downloads
        self.downloads = []

        # Load UI from file
        self.page, self.builder = UILoader.load_template('download-manager.ui', 'download_manager')
        
        # Get references to UI widgets
        self.clear_button = self.builder.get_object('clear_button')
        self.download_listbox = self.builder.get_object('download_listbox')
        
        # Set up the page content
        scrolled_window = self.builder.get_object('scrolled_window')
        # self.set_content(scrolled_window)  # No longer needed
        
        # Connect signals
        self.clear_button.connect("clicked", self._on_clear_completed_clicked)

        # The initial_download_dir_uri is mostly informational; actual destination is set by WebKit.Download
        self.default_download_dir_uri = initial_download_dir_uri

    def add_download(self, webkit_download: WebKit.Download):
        """Adds a WebKit.Download object to the manager and displays it."""
        debug_print(f"Adding download: {webkit_download.get_uri()}")
        
        # Create a UI row for the download
        row = Adw.ActionRow.new()
        row.set_title(os.path.basename(GLib.uri_unescape_string(webkit_download.get_uri(), None)))
        row.set_subtitle(f"Downloading from {webkit_download.get_uri()}")
        row.set_icon_name("download-symbolic")

        # Progress bar
        progress_bar = Gtk.ProgressBar.new()
        progress_bar.set_fraction(0.0)
        progress_bar.set_show_text(True)
        progress_bar.set_valign(Gtk.Align.CENTER)
        row.add_suffix(progress_bar)

        # Buttons (Open file, Open folder, Cancel)
        action_box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        action_box.set_valign(Gtk.Align.CENTER)

        open_file_button = Gtk.Button.new_from_icon_name("document-open-symbolic")
        open_file_button.set_tooltip_text("Open file")
        open_file_button.set_sensitive(False) # Only active when download finished
        open_file_button.connect("clicked", self._on_open_file_clicked, webkit_download)
        action_box.append(open_file_button)

        open_folder_button = Gtk.Button.new_from_icon_name("folder-symbolic")
        open_folder_button.set_tooltip_text("Open folder")
        open_folder_button.set_sensitive(False) # Only active when download finished
        open_folder_button.connect("clicked", self._on_open_folder_clicked, webkit_download)
        action_box.append(open_folder_button)

        cancel_button = Gtk.Button.new_from_icon_name("process-stop-symbolic")
        cancel_button.set_tooltip_text("Cancel download")
        cancel_button.connect("clicked", self._on_cancel_download_clicked, webkit_download)
        action_box.append(cancel_button)

        row.add_suffix(action_box)

        self.download_listbox.append(row)
        self.downloads.append({
            "webkit_download": webkit_download,
            "row": row,
            "progress_bar": progress_bar,
            "open_file_button": open_file_button,
            "open_folder_button": open_folder_button,
            "cancel_button": cancel_button,
            "status": "in_progress" # in_progress, completed, failed, cancelled
        })

        # Connect signals from WebKit.Download
        webkit_download.connect("notify::estimated-progress", self._on_download_progress)
        webkit_download.connect("notify::status", self._on_download_status_changed)
        webkit_download.connect("failed", self._on_download_failed)
        webkit_download.connect("finished", self._on_download_finished)

        # Start the download immediately (WebKit handles this)
        # webkit_download.start() # No, WebKit starts it when it returns the Download object

    def _on_download_progress(self, webkit_download, pspec):
        for dl in self.downloads:
            if dl["webkit_download"] == webkit_download:
                progress_bar = dl["progress_bar"]
                progress = webkit_download.get_estimated_progress()
                progress_bar.set_fraction(progress)
                if progress >= 1.0:
                    progress_bar.set_text("Completed")
                else:
                    progress_bar.set_text(f"{progress * 100:.0f}%")
                break

    def _on_download_status_changed(self, webkit_download, pspec):
        for dl in self.downloads:
            if dl["webkit_download"] == webkit_download:
                status = webkit_download.get_status()
                row = dl["row"]
                progress_bar = dl["progress_bar"]
                open_file_button = dl["open_file_button"]
                open_folder_button = dl["open_folder_button"]
                cancel_button = dl["cancel_button"]

                if status == WebKit.DownloadStatus.COMPLETED:
                    debug_print(f"Download completed: {webkit_download.get_destination()}")
                    dl["status"] = "completed"
                    row.set_subtitle(f"Completed: {webkit_download.get_destination()}")
                    progress_bar.set_text("Completed")
                    progress_bar.add_css_class("success") # Visual cue
                    open_file_button.set_sensitive(True)
                    open_folder_button.set_sensitive(True)
                    cancel_button.set_sensitive(False)
                elif status == WebKit.DownloadStatus.CANCELED:
                    debug_print(f"Download cancelled: {webkit_download.get_uri()}")
                    dl["status"] = "cancelled"
                    row.set_subtitle(f"Cancelled: {webkit_download.get_uri()}")
                    progress_bar.set_text("Cancelled")
                    progress_bar.add_css_class("error") # Visual cue
                    cancel_button.set_sensitive(False)
                elif status == WebKit.DownloadStatus.FAILED:
                    debug_print(f"Download failed: {webkit_download.get_uri()}")
                    dl["status"] = "failed"
                    row.set_subtitle(f"Failed: {webkit_download.get_uri()}")
                    progress_bar.set_text("Failed")
                    progress_bar.add_css_class("error") # Visual cue
                    cancel_button.set_sensitive(False)
                break

    def _on_download_failed(self, webkit_download, error):
        debug_print(f"Download error: {error.message}")
        # Status change signal will handle UI updates

    def _on_download_finished(self, webkit_download):
        # This is emitted after COMPLETED/CANCELED/FAILED.
        # No additional UI updates needed here, _on_download_status_changed handles it.
        pass

    def _on_open_file_clicked(self, button, webkit_download):
        file_path = webkit_download.get_destination()
        if file_path:
            # Use Gtk.show_uri to open the file with default application
            Gtk.show_uri(self.get_root(), f"file://{file_path}", Gdk.CURRENT_TIME)
            debug_print(f"Opening file: {file_path}")

    def _on_open_folder_clicked(self, button, webkit_download):
        file_path = webkit_download.get_destination()
        if file_path:
            # Open the directory containing the file
            folder_path = os.path.dirname(file_path)
            Gtk.show_uri(self.get_root(), f"file://{folder_path}", Gdk.CURRENT_TIME)
            debug_print(f"Opening folder: {folder_path}")

    def _on_cancel_download_clicked(self, button, webkit_download):
        webkit_download.cancel()
        debug_print(f"Download cancelled by user: {webkit_download.get_uri()}")

    def _on_clear_completed_clicked(self, button):
        to_remove = []
        for dl in self.downloads:
            if dl["status"] in ["completed", "failed", "cancelled"]:
                self.download_listbox.remove(dl["row"])
                to_remove.append(dl)
        
        for dl in to_remove:
            self.downloads.remove(dl)
        debug_print("Cleared completed downloads.")
