#!/usr/bin/env python3
"""
Performance monitor window for Seoltoir browser.
Shows real-time resource usage, tab statistics, and performance metrics.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio

import time
import psutil
from typing import Dict, List
from .debug import debug_print


class PerformanceMonitorWindow(Adw.PreferencesWindow):
    """Performance monitoring window with real-time stats."""
    
    def __init__(self, application, **kwargs):
        super().__init__(**kwargs)
        self.application = application
        self.performance_manager = getattr(application, 'performance_manager', None)
        
        # Window configuration
        self.set_title("Performance Monitor")
        self.set_default_size(600, 700)
        self.set_modal(False)
        self.set_resizable(True)
        
        # Timer for updating stats
        self.update_timer_id = None
        
        # Create UI
        self._create_ui()
        
        # Start updating
        self._start_updates()
        
        # Connect to window close event
        self.connect("close-request", self._on_close_request)
    
    def _create_ui(self):
        """Create the performance monitor UI."""
        
        # System Performance Page
        system_page = Adw.PreferencesPage()
        system_page.set_title("System Performance")
        system_page.set_icon_name("computer-symbolic")
        self.add(system_page)
        
        # System Stats Group
        system_group = Adw.PreferencesGroup()
        system_group.set_title("System Resources")
        system_group.set_description("Current system resource usage")
        system_page.add(system_group)
        
        # Memory Usage
        self.memory_row = Adw.ActionRow()
        self.memory_row.set_title("Memory Usage")
        self.memory_progress = Gtk.ProgressBar()
        self.memory_progress.set_hexpand(True)
        self.memory_progress.set_valign(Gtk.Align.CENTER)
        self.memory_row.add_suffix(self.memory_progress)
        self.memory_label = Gtk.Label()
        self.memory_label.set_margin_start(10)
        self.memory_row.add_suffix(self.memory_label)
        system_group.add(self.memory_row)
        
        # CPU Usage
        self.cpu_row = Adw.ActionRow()
        self.cpu_row.set_title("CPU Usage")
        self.cpu_progress = Gtk.ProgressBar()
        self.cpu_progress.set_hexpand(True)
        self.cpu_progress.set_valign(Gtk.Align.CENTER)
        self.cpu_row.add_suffix(self.cpu_progress)
        self.cpu_label = Gtk.Label()
        self.cpu_label.set_margin_start(10)
        self.cpu_row.add_suffix(self.cpu_label)
        system_group.add(self.cpu_row)
        
        # Battery Status
        self.battery_row = Adw.ActionRow()
        self.battery_row.set_title("Battery Status")
        self.battery_label = Gtk.Label()
        self.battery_row.add_suffix(self.battery_label)
        system_group.add(self.battery_row)
        
        # Browser Performance Group
        browser_group = Adw.PreferencesGroup()
        browser_group.set_title("Browser Performance")
        browser_group.set_description("Seoltoir browser resource usage")
        system_page.add(browser_group)
        
        # Active Tabs
        self.active_tabs_row = Adw.ActionRow()
        self.active_tabs_row.set_title("Active Tabs")
        self.active_tabs_label = Gtk.Label()
        self.active_tabs_row.add_suffix(self.active_tabs_label)
        browser_group.add(self.active_tabs_row)
        
        # Suspended Tabs
        self.suspended_tabs_row = Adw.ActionRow()
        self.suspended_tabs_row.set_title("Suspended Tabs")
        self.suspended_tabs_label = Gtk.Label()
        self.suspended_tabs_row.add_suffix(self.suspended_tabs_label)
        browser_group.add(self.suspended_tabs_row)
        
        # Cache Usage
        self.cache_row = Adw.ActionRow()
        self.cache_row.set_title("Cache Usage")
        self.cache_progress = Gtk.ProgressBar()
        self.cache_progress.set_hexpand(True)
        self.cache_progress.set_valign(Gtk.Align.CENTER)
        self.cache_row.add_suffix(self.cache_progress)
        self.cache_label = Gtk.Label()
        self.cache_label.set_margin_start(10)
        self.cache_row.add_suffix(self.cache_label)
        browser_group.add(self.cache_row)
        
        # Tab Details Page
        tabs_page = Adw.PreferencesPage()
        tabs_page.set_title("Tab Details")
        tabs_page.set_icon_name("tab-symbolic")
        self.add(tabs_page)
        
        # Active Tabs Group
        active_tabs_group = Adw.PreferencesGroup()
        active_tabs_group.set_title("Active Tabs")
        active_tabs_group.set_description("Currently active browser tabs")
        tabs_page.add(active_tabs_group)
        
        # Active tabs list
        self.active_tabs_listbox = Gtk.ListBox()
        self.active_tabs_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.active_tabs_listbox.add_css_class("boxed-list")
        active_tabs_group.add(self.active_tabs_listbox)
        
        # Suspended Tabs Group
        suspended_tabs_group = Adw.PreferencesGroup()
        suspended_tabs_group.set_title("Suspended Tabs")
        suspended_tabs_group.set_description("Tabs suspended to save memory")
        tabs_page.add(suspended_tabs_group)
        
        # Suspended tabs list
        self.suspended_tabs_listbox = Gtk.ListBox()
        self.suspended_tabs_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.suspended_tabs_listbox.add_css_class("boxed-list")
        suspended_tabs_group.add(self.suspended_tabs_listbox)
        
        # Controls Page
        controls_page = Adw.PreferencesPage()
        controls_page.set_title("Controls")
        controls_page.set_icon_name("preferences-system-symbolic")
        self.add(controls_page)
        
        # Performance Actions Group
        actions_group = Adw.PreferencesGroup()
        actions_group.set_title("Performance Actions")
        actions_group.set_description("Manual performance management controls")
        controls_page.add(actions_group)
        
        # Force Garbage Collection
        gc_row = Adw.ActionRow()
        gc_row.set_title("Force Memory Cleanup")
        gc_row.set_subtitle("Trigger immediate cache cleanup and tab suspension")
        gc_button = Gtk.Button.new_with_label("Clean Now")
        gc_button.set_valign(Gtk.Align.CENTER)
        gc_button.add_css_class("suggested-action")
        gc_button.connect("clicked", self._on_force_cleanup)
        gc_row.add_suffix(gc_button)
        actions_group.add(gc_row)
        
        # Load All Deferred Tabs
        load_tabs_row = Adw.ActionRow()
        load_tabs_row.set_title("Load Deferred Tabs")
        load_tabs_row.set_subtitle("Force loading of all deferred startup tabs")
        load_button = Gtk.Button.new_with_label("Load All")
        load_button.set_valign(Gtk.Align.CENTER)
        load_button.connect("clicked", self._on_load_deferred_tabs)
        load_tabs_row.add_suffix(load_button)
        actions_group.add(load_tabs_row)
        
        # Performance Settings Group
        settings_group = Adw.PreferencesGroup()
        settings_group.set_title("Performance Settings")
        settings_group.set_description("Quick access to performance configuration")
        controls_page.add(settings_group)
        
        # Tab Suspension Toggle
        suspension_row = Adw.SwitchRow()
        suspension_row.set_title("Tab Suspension")
        suspension_row.set_subtitle("Automatically suspend inactive tabs")
        settings = Gio.Settings.new(self.application.get_application_id())
        suspension_row.set_active(settings.get_boolean("enable-tab-suspension"))
        suspension_row.connect("notify::active", self._on_suspension_toggle)
        settings_group.add(suspension_row)
        
        # Memory Pressure Handling Toggle
        memory_row = Adw.SwitchRow()
        memory_row.set_title("Memory Pressure Handling")
        memory_row.set_subtitle("Automatically manage resources when memory is low")
        memory_row.set_active(settings.get_boolean("enable-memory-pressure-handling"))
        memory_row.connect("notify::active", self._on_memory_pressure_toggle)
        settings_group.add(memory_row)
        
        # Cache Cleanup Toggle
        cache_row = Adw.SwitchRow()
        cache_row.set_title("Automatic Cache Cleanup")
        cache_row.set_subtitle("Automatically clean cache when size limits are exceeded")
        cache_row.set_active(settings.get_boolean("enable-cache-cleanup"))
        cache_row.connect("notify::active", self._on_cache_cleanup_toggle)
        settings_group.add(cache_row)
    
    def _start_updates(self):
        """Start the periodic update timer."""
        # Update every 2 seconds
        self.update_timer_id = GLib.timeout_add_seconds(2, self._update_stats)
        # Initial update
        self._update_stats()
    
    def _update_stats(self) -> bool:
        """Update all performance statistics."""
        try:
            self._update_system_stats()
            self._update_browser_stats()
            self._update_tab_lists()
        except Exception as e:
            debug_print(f"[PERF] Error updating performance monitor: {e}")
        
        return True  # Continue timer
    
    def _update_system_stats(self):
        """Update system performance statistics."""
        try:
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent / 100.0
            self.memory_progress.set_fraction(memory_percent)
            self.memory_label.set_text(f"{memory.percent:.1f}%")
            
            # CPU usage
            cpu_percent = psutil.cpu_percent()
            self.cpu_progress.set_fraction(cpu_percent / 100.0)
            self.cpu_label.set_text(f"{cpu_percent:.1f}%")
            
            # Battery status
            try:
                battery = psutil.sensors_battery()
                if battery:
                    if battery.power_plugged:
                        self.battery_label.set_text(f"{battery.percent:.0f}% (Charging)")
                    else:
                        self.battery_label.set_text(f"{battery.percent:.0f}% (Battery)")
                else:
                    self.battery_label.set_text("N/A")
            except (AttributeError, OSError):
                self.battery_label.set_text("N/A")
                
        except Exception as e:
            debug_print(f"[PERF] Error updating system stats: {e}")
    
    def _update_browser_stats(self):
        """Update browser performance statistics."""
        if not self.performance_manager:
            return
            
        try:
            # Get performance stats
            stats = self.performance_manager.get_performance_stats()
            
            # Update tab counts
            active_tabs = stats.get('active_tabs', 0)
            suspended_tabs = stats.get('suspended_tabs', 0)
            total_tabs = stats.get('total_tabs', 0)
            
            self.active_tabs_label.set_text(f"{active_tabs}")
            self.suspended_tabs_label.set_text(f"{suspended_tabs}")
            
            # Update cache usage
            cache_stats = self.performance_manager.get_cache_usage_estimate()
            cache_percent = cache_stats.get('cache_usage_percent', 0) / 100.0
            cache_mb = cache_stats.get('total_cache_mb', 0)
            cache_limit = cache_stats.get('cache_limit_mb', 500)
            
            self.cache_progress.set_fraction(min(cache_percent, 1.0))
            self.cache_label.set_text(f"{cache_mb:.0f}/{cache_limit} MB")
            
        except Exception as e:
            debug_print(f"[PERF] Error updating browser stats: {e}")
    
    def _update_tab_lists(self):
        """Update the tab lists."""
        if not self.performance_manager:
            return
            
        try:
            # Clear existing lists
            while self.active_tabs_listbox.get_first_child():
                self.active_tabs_listbox.remove(self.active_tabs_listbox.get_first_child())
            while self.suspended_tabs_listbox.get_first_child():
                self.suspended_tabs_listbox.remove(self.suspended_tabs_listbox.get_first_child())
            
            # Add current tabs
            for tab_id, tab_state in self.performance_manager.tab_states.items():
                row = self._create_tab_row(tab_state)
                
                if tab_state.is_suspended:
                    self.suspended_tabs_listbox.append(row)
                else:
                    self.active_tabs_listbox.append(row)
                    
            # Add placeholder if empty
            if not self.active_tabs_listbox.get_first_child():
                placeholder = Adw.ActionRow()
                placeholder.set_title("No active tabs")
                self.active_tabs_listbox.append(placeholder)
                
            if not self.suspended_tabs_listbox.get_first_child():
                placeholder = Adw.ActionRow()
                placeholder.set_title("No suspended tabs")
                self.suspended_tabs_listbox.append(placeholder)
                
        except Exception as e:
            debug_print(f"[PERF] Error updating tab lists: {e}")
    
    def _create_tab_row(self, tab_state) -> Adw.ActionRow:
        """Create a row for displaying tab information."""
        row = Adw.ActionRow()
        
        # Get tab title and URL
        title = getattr(tab_state.browser_view, 'get_title', lambda: "Unknown")()
        uri = getattr(tab_state.browser_view, 'get_uri', lambda: "")()
        
        if not title or title.strip() == "":
            title = "Loading..." if not tab_state.is_suspended else tab_state.suspended_title
        
        # Truncate long titles
        if len(title) > 50:
            title = title[:47] + "..."
            
        row.set_title(title)
        
        # Show URL as subtitle
        if uri and len(uri) > 60:
            uri = uri[:57] + "..."
        row.set_subtitle(uri or "No URL")
        
        # Add status indicators
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        
        # Active indicator
        if tab_state.is_active:
            active_label = Gtk.Label()
            active_label.set_text("●")
            active_label.add_css_class("success")
            active_label.set_tooltip_text("Active tab")
            status_box.append(active_label)
        
        # Private indicator
        if getattr(tab_state.browser_view, 'is_private', False):
            private_label = Gtk.Label()
            private_label.set_text("🔒")
            private_label.set_tooltip_text("Private tab")
            status_box.append(private_label)
        
        # Suspended indicator
        if tab_state.is_suspended:
            suspended_label = Gtk.Label()
            suspended_label.set_text("💤")
            suspended_label.set_tooltip_text("Suspended tab")
            status_box.append(suspended_label)
        
        # Container indicator
        container_id = getattr(tab_state.browser_view, 'container_id', 'default')
        if container_id != 'default':
            container_label = Gtk.Label()
            container_label.set_text(f"[{container_id}]")
            container_label.add_css_class("caption")
            container_label.set_tooltip_text(f"Container: {container_id}")
            status_box.append(container_label)
        
        row.add_suffix(status_box)
        
        return row
    
    def _on_force_cleanup(self, button):
        """Handle force cleanup button click."""
        if self.performance_manager:
            # Force cache cleanup
            self.performance_manager.force_cache_cleanup()
            
            # Force memory pressure handling
            self.performance_manager._handle_memory_pressure(100)  # Simulate high pressure
            
            # Show notification
            toast = Adw.Toast.new("Memory cleanup performed")
            # We don't have access to toast overlay here, so we'll just debug print
            debug_print("[PERF] Manual memory cleanup performed")
    
    def _on_load_deferred_tabs(self, button):
        """Handle load deferred tabs button click."""
        if self.performance_manager:
            deferred_count = len(self.performance_manager.deferred_tabs)
            self.performance_manager.load_all_deferred_tabs()
            debug_print(f"[PERF] Loaded {deferred_count} deferred tabs")
    
    def _on_suspension_toggle(self, switch, param):
        """Handle tab suspension toggle."""
        settings = Gio.Settings.new(self.application.get_application_id())
        settings.set_boolean("enable-tab-suspension", switch.get_active())
    
    def _on_memory_pressure_toggle(self, switch, param):
        """Handle memory pressure toggle."""
        settings = Gio.Settings.new(self.application.get_application_id())
        settings.set_boolean("enable-memory-pressure-handling", switch.get_active())
    
    def _on_cache_cleanup_toggle(self, switch, param):
        """Handle cache cleanup toggle."""
        settings = Gio.Settings.new(self.application.get_application_id())
        settings.set_boolean("enable-cache-cleanup", switch.get_active())
    
    def _on_close_request(self, window):
        """Handle window close request."""
        if self.update_timer_id:
            GLib.source_remove(self.update_timer_id)
            self.update_timer_id = None
        return False  # Allow window to close