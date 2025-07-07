#!/usr/bin/env python3
"""
Debug script to test reader mode functionality
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit, GLib, Gio
import os

def test_reader_mode_resources():
    """Test if reader mode resources can be loaded"""
    print("Testing reader mode resource loading...")
    
    # Test JS file
    js_path = os.path.join(os.path.dirname(__file__), 'src/seoltoir/reader_mode.js')
    css_path = os.path.join(os.path.dirname(__file__), 'src/seoltoir/reader_mode.css')
    
    try:
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        print(f"✅ JavaScript file loaded: {len(js_content)} characters")
        
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        print(f"✅ CSS file loaded: {len(css_content)} characters")
        
        # Test JS syntax by checking for key class
        if 'class SeoltoirReaderMode' in js_content:
            print("✅ SeoltoirReaderMode class found in JS")
        else:
            print("❌ SeoltoirReaderMode class NOT found in JS")
            
        # Test CSS syntax by checking for key classes
        if '.seoltoir-reader-mode' in css_content:
            print("✅ Reader mode CSS classes found")
        else:
            print("❌ Reader mode CSS classes NOT found")
            
        return True
    except Exception as e:
        print(f"❌ Error loading resources: {e}")
        return False

def test_gsettings_schema():
    """Test if GSettings schema is available"""
    print("\nTesting GSettings schema...")
    
    try:
        settings = Gio.Settings.new("io.github.tobagin.seoltoir")
        enable_reader = settings.get_boolean("enable-reader-mode")
        font_size = settings.get_int("reader-mode-font-size")
        theme = settings.get_string("reader-mode-theme")
        
        print(f"✅ Reader mode enabled: {enable_reader}")
        print(f"✅ Font size: {font_size}")
        print(f"✅ Theme: {theme}")
        return True
    except Exception as e:
        print(f"❌ GSettings error: {e}")
        return False

def test_html_file():
    """Test if test HTML file exists"""
    print("\nTesting HTML test file...")
    
    html_path = os.path.join(os.path.dirname(__file__), 'test_reader_mode.html')
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        print(f"✅ Test HTML file found: {len(html_content)} characters")
        
        if '<article>' in html_content:
            print("✅ Article element found in test HTML")
        else:
            print("❌ No article element in test HTML")
            
        file_uri = f"file://{os.path.abspath(html_path)}"
        print(f"📄 Test URL: {file_uri}")
        return True
    except Exception as e:
        print(f"❌ Error reading HTML file: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Reader Mode Debug Test")
    print("=" * 50)
    
    resources_ok = test_reader_mode_resources()
    settings_ok = test_gsettings_schema()
    html_ok = test_html_file()
    
    print("\n" + "=" * 50)
    if resources_ok and settings_ok and html_ok:
        print("✅ All tests passed! Reader mode should work.")
        print("\n🚀 To test:")
        print("1. Open the browser")
        print("2. Navigate to file://" + os.path.abspath("test_reader_mode.html"))
        print("3. Press Alt+R or use the menu")
    else:
        print("❌ Some tests failed. Check the issues above.")