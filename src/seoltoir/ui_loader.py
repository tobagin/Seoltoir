import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib
import os

class UILoader:
    """Utility class for loading UI files from the data directory."""
    
    @staticmethod
    def get_ui_file_path(ui_filename: str) -> str:
        """Get the full path to a UI file in the data directory."""
        # Try to find the UI file in the installed data directory
        data_dirs = [
            # Development path (when running from source)
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'ui'),
            # Installed path
            os.path.join(GLib.get_user_data_dir(), 'seoltoir', 'ui'),
            # System-wide installed path
            '/usr/share/seoltoir/ui',
            '/usr/local/share/seoltoir/ui',
        ]
        
        for data_dir in data_dirs:
            ui_path = os.path.join(data_dir, ui_filename)
            if os.path.exists(ui_path):
                return ui_path
        
        raise FileNotFoundError(f"UI file '{ui_filename}' not found in any of the expected locations: {data_dirs}")
    
    @staticmethod
    def load_template(ui_filename: str, template_name: str, **kwargs):
        """Load a UI template from a UI file and return the widget."""
        ui_path = UILoader.get_ui_file_path(ui_filename)
        
        # Create a GtkBuilder and load the UI file
        builder = Gtk.Builder()
        builder.add_from_file(ui_path)
        
        # Get the template widget
        widget = builder.get_object(template_name)
        if not widget:
            raise ValueError(f"Template '{template_name}' not found in UI file '{ui_filename}'")
        
        # Set any additional properties passed as kwargs
        for key, value in kwargs.items():
            if hasattr(widget, f'set_{key}'):
                getattr(widget, f'set_{key}')(value)
            elif hasattr(widget, key):
                setattr(widget, key, value)
        
        return widget, builder
    
    @staticmethod
    def load_dialog(ui_filename: str, template_name: str, parent=None, **kwargs):
        """Load a dialog template and set up common dialog properties."""
        dialog, builder = UILoader.load_template(ui_filename, template_name, **kwargs)
        
        if parent:
            dialog.set_transient_for(parent)
            dialog.set_modal(True)
        
        return dialog, builder 