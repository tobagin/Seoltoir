"""Picture-in-Picture window implementation for Seoltoir browser."""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
gi.require_version('WebKit', '6.0')

from gi.repository import Gtk, Adw, Gdk, GLib, WebKit, GObject
from .ui_loader import UILoader


class PiPWindow(Gtk.Window):
    """Floating Picture-in-Picture window for video content."""
    
    __gsignals__ = {
        "return-to-main": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }
    
    def __init__(self, source_webview, application=None):
        super().__init__()
        
        self.application = application
        self.source_webview = source_webview
        self.pip_webview = None
        self.media_uri = None
        self.is_playing = False
        self.current_volume = 1.0
        
        self._setup_window()
        self._create_pip_webview()
        self._setup_controls()
        self._setup_signals()
    
    def _setup_window(self):
        """Configure the PiP window properties."""
        self.set_title("Picture in Picture")
        self.set_default_size(320, 240)
        self.set_resizable(True)
        
        # Always on top behavior (limited in GTK4)
        # Note: GTK4 removed many window management functions
        # The window will still function, just without always-on-top
        
        # Remove window decorations for floating effect
        header_bar = Gtk.HeaderBar()
        header_bar.set_show_title_buttons(False)
        self.set_titlebar(header_bar)
        
        # Add close button to header
        close_button = Gtk.Button()
        close_button.set_icon_name("window-close-symbolic")
        close_button.add_css_class("circular")
        close_button.connect("clicked", self._on_close_clicked)
        header_bar.pack_end(close_button)
        
        # Add minimize button
        minimize_button = Gtk.Button()
        minimize_button.set_icon_name("window-minimize-symbolic")
        minimize_button.add_css_class("circular")
        minimize_button.connect("clicked", self._on_minimize_clicked)
        header_bar.pack_end(minimize_button)
    
    def _create_pip_webview(self):
        """Create a WebView for PiP content."""
        self.pip_webview = WebKit.WebView()
        
        # Configure WebView settings for media playback
        settings = self.pip_webview.get_settings()
        try:
            settings.set_enable_media_stream(True)
            settings.set_media_playback_requires_user_gesture(False)
            settings.set_media_playback_allows_inline(True)
        except AttributeError:
            # Some settings may not be available in all WebKit versions
            pass
        
        # Create main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(main_box)
        
        # Add WebView to scrolled window for better handling
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self.pip_webview)
        
        main_box.append(scrolled)
    
    def _setup_controls(self):
        """Set up PiP control overlay."""
        # Create overlay for controls
        self.overlay = Gtk.Overlay()
        
        # Get the main box and replace with overlay
        main_box = self.get_child()
        self.set_child(self.overlay)
        self.overlay.set_child(main_box)
        
        # Create controls box
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        controls_box.set_halign(Gtk.Align.CENTER)
        controls_box.set_valign(Gtk.Align.END)
        controls_box.set_margin_bottom(10)
        controls_box.add_css_class("osd")
        
        # Play/Pause button
        self.play_pause_button = Gtk.Button()
        self.play_pause_button.set_icon_name("media-playback-pause-symbolic")
        self.play_pause_button.add_css_class("circular")
        self.play_pause_button.connect("clicked", self._on_play_pause_clicked)
        controls_box.append(self.play_pause_button)
        
        # Volume button and scale
        volume_button = Gtk.VolumeButton()
        volume_button.set_value(self.current_volume)
        volume_button.connect("value-changed", self._on_volume_changed)
        controls_box.append(volume_button)
        
        # Return to main window button
        return_button = Gtk.Button()
        return_button.set_icon_name("view-restore-symbolic")
        return_button.set_tooltip_text("Return to main window")
        return_button.add_css_class("circular")
        return_button.connect("clicked", self._on_return_clicked)
        controls_box.append(return_button)
        
        # Add controls to overlay
        self.overlay.add_overlay(controls_box)
        
        # Initially hide controls
        self.controls_box = controls_box
        self.controls_visible = False
        self._hide_controls()
    
    def _setup_signals(self):
        """Set up signal connections."""
        # Window signals
        self.connect("close-request", self._on_close_request)
        
        # Mouse motion for showing controls
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("motion", self._on_mouse_motion)
        self.add_controller(motion_controller)
        
        # WebView signals
        if self.pip_webview:
            self.pip_webview.connect("load-changed", self._on_pip_load_changed)
    
    def load_media(self, media_uri):
        """Load media content in PiP window."""
        self.media_uri = media_uri
        
        # Create HTML for media playback
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    margin: 0;
                    padding: 0;
                    background: black;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                }}
                video {{
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                }}
            </style>
        </head>
        <body>
            <video controls autoplay>
                <source src="{media_uri}" type="video/mp4">
                <source src="{media_uri}" type="video/webm">
                <source src="{media_uri}" type="video/ogg">
                Your browser does not support the video tag.
            </video>
            <script>
                const video = document.querySelector('video');
                video.addEventListener('play', () => {{
                    window.webkit.messageHandlers.pipControl.postMessage({{action: 'play'}});
                }});
                video.addEventListener('pause', () => {{
                    window.webkit.messageHandlers.pipControl.postMessage({{action: 'pause'}});
                }});
                video.addEventListener('volumechange', () => {{
                    window.webkit.messageHandlers.pipControl.postMessage({{
                        action: 'volume', 
                        volume: video.volume
                    }});
                }});
            </script>
        </body>
        </html>
        """
        
        self.pip_webview.load_html(html_content, None)
    
    def _on_pip_load_changed(self, webview, load_event):
        """Handle PiP WebView load changes."""
        if load_event == WebKit.LoadEvent.FINISHED:
            # Register message handler for media controls
            content_manager = webview.get_user_content_manager()
            try:
                content_manager.register_script_message_handler("pipControl")
                content_manager.connect("script-message-received::pipControl", 
                                      self._on_pip_control_message)
            except Exception as e:
                debug_print(f"Error setting up PiP control handler: {e}")
    
    def _on_pip_control_message(self, manager, message):
        """Handle messages from PiP WebView."""
        try:
            data = message.to_dict()
            action = data.get("action")
            
            if action == "play":
                self.is_playing = True
                self.play_pause_button.set_icon_name("media-playback-pause-symbolic")
            elif action == "pause":
                self.is_playing = False
                self.play_pause_button.set_icon_name("media-playback-start-symbolic")
            elif action == "volume":
                self.current_volume = data.get("volume", 1.0)
        except Exception as e:
            debug_print(f"Error handling PiP control message: {e}")
    
    def _on_play_pause_clicked(self, button):
        """Handle play/pause button click."""
        script = "document.querySelector('video').paused ? document.querySelector('video').play() : document.querySelector('video').pause();"
        self.pip_webview.evaluate_javascript(script, -1, None, None, None)
    
    def _on_volume_changed(self, button, value):
        """Handle volume change."""
        self.current_volume = value
        script = f"document.querySelector('video').volume = {value};"
        self.pip_webview.evaluate_javascript(script, -1, None, None, None)
    
    def _on_return_clicked(self, button):
        """Handle return to main window."""
        # Emit signal to return to main window
        self.emit("return-to-main")
        self.close()
    
    def _on_close_clicked(self, button):
        """Handle close button click."""
        self.close()
    
    def _on_minimize_clicked(self, button):
        """Handle minimize button click."""
        self.minimize()
    
    def _on_close_request(self, window):
        """Handle window close request."""
        return False  # Allow closing
    
    def _on_mouse_motion(self, controller, x, y):
        """Handle mouse motion to show/hide controls."""
        self._show_controls()
        
        # Hide controls after 3 seconds of inactivity
        if hasattr(self, '_hide_timeout'):
            GLib.source_remove(self._hide_timeout)
        
        self._hide_timeout = GLib.timeout_add_seconds(3, self._hide_controls)
    
    def _show_controls(self):
        """Show the control overlay."""
        if not self.controls_visible:
            self.controls_box.set_visible(True)
            self.controls_visible = True
    
    def _hide_controls(self):
        """Hide the control overlay."""
        if self.controls_visible:
            self.controls_box.set_visible(False)
            self.controls_visible = False
        return False  # Remove timeout


