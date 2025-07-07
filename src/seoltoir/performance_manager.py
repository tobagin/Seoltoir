#!/usr/bin/env python3
"""
Performance manager for Seoltoir browser.
Handles tab suspension, memory management, and resource optimization.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import GLib, Gio, WebKit

import time
import psutil
import threading
from typing import Dict, List, Optional, Tuple
from .debug import debug_print


class TabState:
    """Represents the state of a tab for performance management."""
    def __init__(self, tab_id: str, browser_view, is_active: bool = False):
        self.tab_id = tab_id
        self.browser_view = browser_view
        self.is_active = is_active
        self.is_suspended = False
        self.last_active_time = time.time()
        self.memory_usage = 0
        self.cpu_usage = 0
        self.suspended_title = ""
        self.suspended_uri = ""
        self.load_time = time.time()
        
    def update_activity(self):
        """Update the last active time."""
        self.last_active_time = time.time()
        self.is_active = True
        
    def get_inactive_time(self) -> float:
        """Get time in seconds since tab was last active."""
        return time.time() - self.last_active_time


class PerformanceManager:
    """Manages browser performance optimization."""
    
    def __init__(self, application):
        self.application = application
        self.settings = Gio.Settings.new(application.get_application_id())
        
        # Tab management
        self.tab_states: Dict[str, TabState] = {}
        self.suspension_timer_id = None
        self.memory_monitor_timer_id = None
        
        # Performance monitoring
        self.cpu_usage_history = []
        self.memory_usage_history = []
        self.last_memory_check = time.time()
        
        # System monitoring
        self.system_memory_total = psutil.virtual_memory().total
        self.is_on_battery = self._check_battery_status()
        self.battery_monitor_timer_id = None
        
        # Cache management
        self.cache_cleanup_timer_id = None
        
        # Startup optimization
        self.startup_mode = self.settings.get_string("startup-tab-loading-mode")
        self.deferred_tabs = []  # Tabs waiting to be loaded
        self.startup_complete = False
        
        # Process monitoring
        self.process_monitor_timer_id = None
        self.crashed_tabs = []  # Track tabs that have crashed
        self.tab_process_health = {}  # Track process health per tab
        
        # Resource limits
        self.tab_resource_limits = {
            'max_memory_mb': 512,  # Max memory per tab in MB
            'max_cpu_percent': 25,  # Max CPU percentage per tab
            'max_network_kbps': 1000  # Max network usage per tab in KB/s
        }
        
        # Initialize monitoring
        self._start_monitoring()
        
        debug_print("[PERF] Performance manager initialized")
    
    def _check_battery_status(self) -> bool:
        """Check if system is running on battery power."""
        try:
            battery = psutil.sensors_battery()
            return battery is not None and not battery.power_plugged
        except (AttributeError, OSError):
            return False
    
    def _start_monitoring(self):
        """Start performance monitoring timers."""
        if self.settings.get_boolean("enable-tab-suspension"):
            # Check for tab suspension every 30 seconds
            self.suspension_timer_id = GLib.timeout_add_seconds(
                30, self._check_tab_suspension
            )
            
        if self.settings.get_boolean("enable-memory-pressure-handling"):
            # Monitor memory pressure every 15 seconds
            self.memory_monitor_timer_id = GLib.timeout_add_seconds(
                15, self._check_memory_pressure
            )
            
        if self.settings.get_boolean("enable-cache-cleanup"):
            # Check cache size every 5 minutes
            self.cache_cleanup_timer_id = GLib.timeout_add_seconds(
                300, self._check_cache_size
            )
            
        # Monitor process health every 10 seconds
        self.process_monitor_timer_id = GLib.timeout_add_seconds(
            10, self._check_process_health
        )
        
        if self.settings.get_boolean("enable-battery-optimization"):
            # Monitor battery status every 30 seconds
            self.battery_monitor_timer_id = GLib.timeout_add_seconds(
                30, self._check_battery_optimization
            )
    
    def register_tab(self, tab_id: str, browser_view, is_active: bool = False) -> TabState:
        """Register a new tab for performance monitoring."""
        tab_state = TabState(tab_id, browser_view, is_active)
        self.tab_states[tab_id] = tab_state
        
        debug_print(f"[PERF] Registered tab {tab_id}, active: {is_active}")
        
        # Apply lazy loading if enabled
        if self.settings.get_boolean("enable-lazy-image-loading"):
            self._apply_lazy_loading(browser_view)
            
        return tab_state
    
    def unregister_tab(self, tab_id: str):
        """Unregister a tab from performance monitoring."""
        if tab_id in self.tab_states:
            tab_state = self.tab_states[tab_id]
            if tab_state.is_suspended:
                self._resume_tab(tab_id, force=True)
            del self.tab_states[tab_id]
            debug_print(f"[PERF] Unregistered tab {tab_id}")
    
    def set_tab_active(self, tab_id: str, is_active: bool):
        """Update tab active status."""
        if tab_id in self.tab_states:
            tab_state = self.tab_states[tab_id]
            
            # Set all other tabs as inactive if this one is active
            if is_active:
                for other_id, other_state in self.tab_states.items():
                    if other_id != tab_id:
                        other_state.is_active = False
                        
            tab_state.is_active = is_active
            if is_active:
                tab_state.update_activity()
                
                # Resume tab if it was suspended
                if tab_state.is_suspended:
                    self._resume_tab(tab_id)
                    
            debug_print(f"[PERF] Tab {tab_id} active: {is_active}")
    
    def _check_tab_suspension(self) -> bool:
        """Check if any tabs should be suspended."""
        if not self.settings.get_boolean("enable-tab-suspension"):
            return True
            
        suspension_timeout = self.settings.get_int("tab-suspension-timeout")
        max_concurrent_tabs = self.settings.get_int("max-concurrent-tabs")
        
        # Count active tabs
        active_tabs = [t for t in self.tab_states.values() if not t.is_suspended]
        inactive_tabs = [t for t in active_tabs if not t.is_active]
        
        # Sort by inactive time (oldest first)
        inactive_tabs.sort(key=lambda t: t.get_inactive_time(), reverse=True)
        
        suspended_count = 0
        
        # Suspend tabs based on timeout
        for tab_state in inactive_tabs:
            if tab_state.get_inactive_time() > suspension_timeout:
                self._suspend_tab(tab_state.tab_id)
                suspended_count += 1
        
        # Suspend excess tabs if over limit
        if len(active_tabs) > max_concurrent_tabs:
            excess_count = len(active_tabs) - max_concurrent_tabs
            for i in range(min(excess_count, len(inactive_tabs))):
                if not inactive_tabs[i].is_suspended:
                    self._suspend_tab(inactive_tabs[i].tab_id)
                    suspended_count += 1
        
        if suspended_count > 0:
            debug_print(f"[PERF] Suspended {suspended_count} tabs")
            
        return True  # Continue timer
    
    def _suspend_tab(self, tab_id: str):
        """Suspend a tab to save memory."""
        if tab_id not in self.tab_states:
            return
            
        tab_state = self.tab_states[tab_id]
        if tab_state.is_suspended or tab_state.is_active:
            return
            
        browser_view = tab_state.browser_view
        webview = browser_view.webview
        
        # Store tab information
        tab_state.suspended_uri = browser_view.get_uri() or ""
        tab_state.suspended_title = browser_view.get_title() or "Suspended Tab"
        
        # Replace content with suspension page
        suspension_html = self._create_suspension_page(
            tab_state.suspended_title, 
            tab_state.suspended_uri
        )
        
        # Load suspension page
        webview.load_html(suspension_html, None)
        
        # Mark as suspended
        tab_state.is_suspended = True
        
        debug_print(f"[PERF] Suspended tab {tab_id}: {tab_state.suspended_title}")
        
        # Update tab title to indicate suspension
        GLib.idle_add(self._update_suspended_tab_ui, tab_id)
    
    def _resume_tab(self, tab_id: str, force: bool = False):
        """Resume a suspended tab."""
        if tab_id not in self.tab_states:
            return
            
        tab_state = self.tab_states[tab_id]
        if not tab_state.is_suspended:
            return
            
        # Don't resume unless active or forced
        if not tab_state.is_active and not force:
            return
            
        browser_view = tab_state.browser_view
        webview = browser_view.webview
        
        # Reload original URI
        if tab_state.suspended_uri:
            webview.load_uri(tab_state.suspended_uri)
        else:
            # Fallback to homepage
            homepage = self.settings.get_string("homepage")
            webview.load_uri(homepage)
            
        # Mark as resumed
        tab_state.is_suspended = False
        tab_state.update_activity()
        
        debug_print(f"[PERF] Resumed tab {tab_id}: {tab_state.suspended_title}")
        
        # Update UI
        GLib.idle_add(self._update_resumed_tab_ui, tab_id)
    
    def _create_suspension_page(self, title: str, uri: str) -> str:
        """Create HTML content for suspended tab page."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            margin: 0;
            padding: 40px;
            font-family: -webkit-system-font, system-ui, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
        }}
        .container {{
            max-width: 500px;
            background: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        .icon {{
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.8;
        }}
        h1 {{
            margin: 0 0 10px 0;
            font-size: 24px;
            font-weight: 300;
        }}
        .url {{
            opacity: 0.7;
            font-size: 14px;
            word-break: break-all;
            margin: 10px 0 20px 0;
        }}
        .note {{
            opacity: 0.6;
            font-size: 12px;
            margin-top: 20px;
        }}
        .resume-btn {{
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 20px;
            transition: all 0.3s ease;
        }}
        .resume-btn:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">💤</div>
        <h1>Tab Suspended</h1>
        <div class="url">{uri}</div>
        <p>This tab was suspended to save memory and improve performance.</p>
        <button class="resume-btn" onclick="window.location.reload()">
            Resume Tab
        </button>
        <div class="note">
            The tab will automatically resume when you switch to it.
        </div>
    </div>
</body>
</html>
        """
    
    def _update_suspended_tab_ui(self, tab_id: str):
        """Update UI to show tab is suspended."""
        # This will be implemented when integrating with window.py
        pass
    
    def _update_resumed_tab_ui(self, tab_id: str):
        """Update UI to show tab is resumed."""
        # This will be implemented when integrating with window.py
        pass
    
    def _check_memory_pressure(self) -> bool:
        """Check system memory pressure and take action if needed."""
        if not self.settings.get_boolean("enable-memory-pressure-handling"):
            return True
            
        try:
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            threshold = self.settings.get_int("memory-pressure-threshold")
            
            # Store memory usage for monitoring
            self.memory_usage_history.append(memory_percent)
            if len(self.memory_usage_history) > 100:
                self.memory_usage_history.pop(0)
            
            if memory_percent > threshold:
                debug_print(f"[PERF] Memory pressure detected: {memory_percent}%")
                self._handle_memory_pressure(memory_percent)
                
        except Exception as e:
            debug_print(f"[PERF] Error checking memory pressure: {e}")
            
        return True  # Continue timer
    
    def _handle_memory_pressure(self, memory_percent: float):
        """Handle high memory usage by suspending tabs."""
        # Get inactive tabs sorted by memory usage (if available)
        inactive_tabs = [
            t for t in self.tab_states.values() 
            if not t.is_active and not t.is_suspended
        ]
        
        # Sort by inactive time (suspend oldest first)
        inactive_tabs.sort(key=lambda t: t.get_inactive_time(), reverse=True)
        
        # Suspend tabs until memory pressure is reduced
        tabs_to_suspend = min(len(inactive_tabs), 3)  # Don't suspend too many at once
        
        for i in range(tabs_to_suspend):
            self._suspend_tab(inactive_tabs[i].tab_id)
            
        if tabs_to_suspend > 0:
            debug_print(f"[PERF] Suspended {tabs_to_suspend} tabs due to memory pressure")
    
    def _apply_lazy_loading(self, browser_view):
        """Apply lazy loading to images in the browser view."""
        threshold = self.settings.get_int("lazy-loading-threshold")
        
        # Inject lazy loading JavaScript
        lazy_loading_script = f"""
        (function() {{
            const threshold = {threshold};
            const images = document.querySelectorAll('img');
            
            const lazyLoad = (entries, observer) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        const img = entry.target;
                        if (img.dataset.src) {{
                            img.src = img.dataset.src;
                            img.removeAttribute('data-src');
                            observer.unobserve(img);
                        }}
                    }}
                }});
            }};
            
            const observer = new IntersectionObserver(lazyLoad, {{
                rootMargin: `${{threshold}}px`
            }});
            
            images.forEach(img => {{
                if (img.src && !img.complete) {{
                    img.dataset.src = img.src;
                    img.src = '';
                    observer.observe(img);
                }}
            }});
        }})();
        """
        
        # Apply the script after page load
        def apply_lazy_loading():
            browser_view.webview.evaluate_javascript(
                lazy_loading_script, -1, None, None, None
            )
            
        # Connect to load events
        browser_view.webview.connect("load-changed", 
            lambda webview, load_event: 
                apply_lazy_loading() if load_event == WebKit.LoadEvent.FINISHED else None
        )
    
    def get_performance_stats(self) -> Dict:
        """Get current performance statistics."""
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent()
            
            active_tabs = len([t for t in self.tab_states.values() if not t.is_suspended])
            suspended_tabs = len([t for t in self.tab_states.values() if t.is_suspended])
            
            return {
                "memory_percent": memory.percent,
                "memory_used_gb": memory.used / (1024**3),
                "memory_total_gb": memory.total / (1024**3),
                "cpu_percent": cpu_percent,
                "active_tabs": active_tabs,
                "suspended_tabs": suspended_tabs,
                "total_tabs": len(self.tab_states),
                "is_on_battery": self._check_battery_status()
            }
        except Exception as e:
            debug_print(f"[PERF] Error getting performance stats: {e}")
            return {}
    
    def _check_cache_size(self) -> bool:
        """Check cache size and clean up if needed."""
        if not self.settings.get_boolean("enable-cache-cleanup"):
            return True
            
        try:
            cache_limit_mb = self.settings.get_int("cache-size-limit")
            cache_limit_bytes = cache_limit_mb * 1024 * 1024
            
            # Get current cache usage from all containers
            total_cache_size = 0
            containers_to_clean = []
            
            if hasattr(self.application, 'container_manager'):
                for container_id, network_session in self.application.container_manager.container_network_sessions.items():
                    data_manager = network_session.get_website_data_manager()
                    
                    # Get cache data size (this is asynchronous in real WebKit, but we'll estimate)
                    try:
                        # Estimate cache size - this is a simplified approach
                        cache_estimate = self._estimate_container_cache_size(container_id)
                        total_cache_size += cache_estimate
                        
                        if cache_estimate > 0:
                            containers_to_clean.append((container_id, network_session, cache_estimate))
                            
                    except Exception as e:
                        debug_print(f"[PERF] Error checking cache for container {container_id}: {e}")
            
            if total_cache_size > cache_limit_bytes:
                debug_print(f"[PERF] Cache size ({total_cache_size / 1024 / 1024:.1f} MB) exceeds limit ({cache_limit_mb} MB)")
                self._cleanup_cache(containers_to_clean, total_cache_size - cache_limit_bytes)
                
        except Exception as e:
            debug_print(f"[PERF] Error checking cache size: {e}")
            
        return True  # Continue timer
    
    def _estimate_container_cache_size(self, container_id: str) -> int:
        """Estimate cache size for a container."""
        try:
            # This is a simplified estimation - in a real implementation,
            # you'd use WebKit's website data APIs to get actual sizes
            
            # Count active tabs in this container
            active_tabs_in_container = 0
            for tab_state in self.tab_states.values():
                if hasattr(tab_state.browser_view, 'container_id') and tab_state.browser_view.container_id == container_id:
                    if not tab_state.is_suspended:
                        active_tabs_in_container += 1
            
            # Estimate based on active tabs (rough approximation)
            # Each active tab might use 10-50 MB of cache on average
            estimated_size = active_tabs_in_container * 25 * 1024 * 1024  # 25 MB per tab
            
            return estimated_size
            
        except Exception as e:
            debug_print(f"[PERF] Error estimating cache size for container {container_id}: {e}")
            return 0
    
    def _cleanup_cache(self, containers_to_clean: List, excess_bytes: int):
        """Clean up cache data to reduce usage."""
        debug_print(f"[PERF] Starting cache cleanup to free {excess_bytes / 1024 / 1024:.1f} MB")
        
        # Sort containers by cache size (clean largest first)
        containers_to_clean.sort(key=lambda x: x[2], reverse=True)
        
        bytes_cleaned = 0
        
        for container_id, network_session, cache_size in containers_to_clean:
            if bytes_cleaned >= excess_bytes:
                break
                
            try:
                data_manager = network_session.get_website_data_manager()
                
                # Clear different types of website data based on severity
                if bytes_cleaned < excess_bytes * 0.3:  # Light cleanup first
                    # Clear just offline cache and favicons
                    types_to_clear = (WebKit.WebsiteDataTypes.DISK_CACHE | 
                                    WebKit.WebsiteDataTypes.MEMORY_CACHE)
                elif bytes_cleaned < excess_bytes * 0.7:  # Medium cleanup
                    # Add session storage and web SQL
                    types_to_clear = (WebKit.WebsiteDataTypes.DISK_CACHE | 
                                    WebKit.WebsiteDataTypes.MEMORY_CACHE |
                                    WebKit.WebsiteDataTypes.SESSION_STORAGE |
                                    WebKit.WebsiteDataTypes.WEBSQL_DATABASES)
                else:  # Aggressive cleanup
                    # Clear most cache data except cookies and local storage
                    types_to_clear = (WebKit.WebsiteDataTypes.DISK_CACHE | 
                                    WebKit.WebsiteDataTypes.MEMORY_CACHE |
                                    WebKit.WebsiteDataTypes.SESSION_STORAGE |
                                    WebKit.WebsiteDataTypes.WEBSQL_DATABASES |
                                    WebKit.WebsiteDataTypes.INDEXEDDB_DATABASES)
                
                # Perform the cleanup
                data_manager.clear(types_to_clear, 0, None, None)
                
                bytes_cleaned += cache_size * 0.7  # Estimate 70% cleanup
                debug_print(f"[PERF] Cleaned cache for container {container_id}")
                
            except Exception as e:
                debug_print(f"[PERF] Error cleaning cache for container {container_id}: {e}")
        
        debug_print(f"[PERF] Cache cleanup completed, estimated {bytes_cleaned / 1024 / 1024:.1f} MB freed")
    
    def _check_process_health(self) -> bool:
        """Monitor tab process health and recover crashed tabs."""
        try:
            for tab_id, tab_state in list(self.tab_states.items()):
                if tab_state.is_suspended:
                    continue
                    
                browser_view = tab_state.browser_view
                webview = browser_view.webview
                
                # Check if the web process is responsive
                try:
                    is_responsive = webview.get_is_web_process_responsive()
                    
                    # Track process health history
                    if tab_id not in self.tab_process_health:
                        self.tab_process_health[tab_id] = {
                            'responsive_checks': 0,
                            'unresponsive_count': 0,
                            'last_recovery': 0
                        }
                    
                    health = self.tab_process_health[tab_id]
                    health['responsive_checks'] += 1
                    
                    if not is_responsive:
                        health['unresponsive_count'] += 1
                        debug_print(f"[PERF] Tab {tab_id} web process unresponsive ({health['unresponsive_count']} times)")
                        
                        # If unresponsive for 3+ consecutive checks, consider recovery
                        if (health['unresponsive_count'] >= 3 and 
                            time.time() - health['last_recovery'] > 30):  # Don't recover too frequently
                            
                            self._recover_unresponsive_tab(tab_id, tab_state)
                            health['last_recovery'] = time.time()
                            health['unresponsive_count'] = 0
                    else:
                        # Reset unresponsive count on successful response
                        health['unresponsive_count'] = 0
                        
                    # Check resource limits
                    self._enforce_tab_resource_limits(tab_id, tab_state)
                        
                except AttributeError:
                    # Method not available in this WebKit version
                    debug_print(f"[PERF] Process responsiveness check not available for tab {tab_id}")
                except Exception as e:
                    debug_print(f"[PERF] Error checking process health for tab {tab_id}: {e}")
                    
        except Exception as e:
            debug_print(f"[PERF] Error in process health monitoring: {e}")
            
        return True  # Continue timer
    
    def _recover_unresponsive_tab(self, tab_id: str, tab_state: TabState):
        """Recover an unresponsive tab by reloading it."""
        debug_print(f"[PERF] Attempting to recover unresponsive tab {tab_id}")
        
        try:
            browser_view = tab_state.browser_view
            webview = browser_view.webview
            current_uri = browser_view.get_uri()
            
            # Add to crashed tabs list
            if tab_id not in self.crashed_tabs:
                self.crashed_tabs.append(tab_id)
            
            # Try to terminate the web process gracefully first
            try:
                webview.terminate_web_process()
                debug_print(f"[PERF] Terminated web process for tab {tab_id}")
            except Exception as e:
                debug_print(f"[PERF] Could not terminate web process for tab {tab_id}: {e}")
            
            # Wait a moment then reload
            def delayed_reload():
                try:
                    if current_uri:
                        webview.load_uri(current_uri)
                        debug_print(f"[PERF] Reloaded tab {tab_id} with URI: {current_uri}")
                    else:
                        # Load homepage as fallback
                        homepage = self.settings.get_string("homepage")
                        webview.load_uri(homepage)
                        debug_print(f"[PERF] Reloaded tab {tab_id} with homepage")
                except Exception as e:
                    debug_print(f"[PERF] Error during tab recovery reload: {e}")
                return False  # Don't repeat
            
            # Schedule reload after 2 seconds
            GLib.timeout_add_seconds(2, delayed_reload)
            
        except Exception as e:
            debug_print(f"[PERF] Error recovering tab {tab_id}: {e}")
    
    def get_process_health_stats(self) -> Dict:
        """Get process health statistics."""
        total_tabs = len(self.tab_states)
        crashed_tabs = len(self.crashed_tabs)
        unresponsive_tabs = 0
        
        for health in self.tab_process_health.values():
            if health.get('unresponsive_count', 0) > 0:
                unresponsive_tabs += 1
        
        return {
            "total_tabs": total_tabs,
            "crashed_tabs": crashed_tabs,
            "recovered_tabs": crashed_tabs,  # All crashed tabs are attempted recovery
            "unresponsive_tabs": unresponsive_tabs,
            "healthy_tabs": total_tabs - unresponsive_tabs
        }
    
    def _enforce_tab_resource_limits(self, tab_id: str, tab_state: TabState):
        """Enforce resource limits on a tab."""
        try:
            # This is a simplified implementation
            # In a full implementation, you would:
            # 1. Monitor actual memory usage per WebKit process
            # 2. Monitor CPU usage per process
            # 3. Monitor network usage per tab
            
            # For now, we'll use tab age and activity as proxies
            inactive_time = tab_state.get_inactive_time()
            
            # If tab has been inactive for a long time and uses estimated resources
            if inactive_time > 600:  # 10 minutes
                estimated_memory = self._estimate_tab_memory_usage(tab_state)
                
                if estimated_memory > self.tab_resource_limits['max_memory_mb']:
                    debug_print(f"[PERF] Tab {tab_id} exceeds memory limit, suspending")
                    self._suspend_tab(tab_id)
                    
        except Exception as e:
            debug_print(f"[PERF] Error enforcing resource limits for tab {tab_id}: {e}")
    
    def _estimate_tab_memory_usage(self, tab_state: TabState) -> int:
        """Estimate memory usage for a tab in MB."""
        # This is a simplified estimation
        # Factors that affect memory usage:
        base_memory = 50  # Base memory for a tab
        
        # Add memory based on tab age (older tabs might have more cached content)
        age_minutes = (time.time() - tab_state.load_time) / 60
        age_memory = min(age_minutes * 2, 100)  # Up to 100MB for age
        
        # Add memory if tab is active
        activity_memory = 20 if tab_state.is_active else 0
        
        # Add memory for media content (simplified check)
        media_memory = 0
        try:
            uri = tab_state.browser_view.get_uri() or ""
            if any(media in uri.lower() for media in ['youtube', 'video', 'audio', 'stream']):
                media_memory = 50
        except:
            pass
            
        total_estimated = base_memory + age_memory + activity_memory + media_memory
        return int(total_estimated)
    
    def set_tab_resource_limits(self, limits: Dict):
        """Update resource limits for tabs."""
        self.tab_resource_limits.update(limits)
        debug_print(f"[PERF] Updated tab resource limits: {self.tab_resource_limits}")
    
    def get_tab_resource_usage(self) -> Dict:
        """Get resource usage statistics for all tabs."""
        tab_usage = {}
        
        for tab_id, tab_state in self.tab_states.items():
            estimated_memory = self._estimate_tab_memory_usage(tab_state)
            
            tab_usage[tab_id] = {
                "estimated_memory_mb": estimated_memory,
                "is_over_limit": estimated_memory > self.tab_resource_limits['max_memory_mb'],
                "inactive_time": tab_state.get_inactive_time(),
                "is_suspended": tab_state.is_suspended
            }
            
        return tab_usage
    
    def _check_battery_optimization(self) -> bool:
        """Check battery status and apply optimizations when on battery."""
        if not self.settings.get_boolean("enable-battery-optimization"):
            return True
            
        try:
            was_on_battery = self.is_on_battery
            self.is_on_battery = self._check_battery_status()
            
            # If we switched to battery power, apply optimizations
            if self.is_on_battery and not was_on_battery:
                debug_print("[PERF] Switched to battery power, applying optimizations")
                self._apply_battery_optimizations()
            # If we switched to AC power, remove optimizations
            elif not self.is_on_battery and was_on_battery:
                debug_print("[PERF] Switched to AC power, removing battery optimizations")
                self._remove_battery_optimizations()
                
        except Exception as e:
            debug_print(f"[PERF] Error in battery optimization check: {e}")
            
        return True  # Continue timer
    
    def _apply_battery_optimizations(self):
        """Apply optimizations when running on battery."""
        try:
            # Reduce tab suspension timeout for more aggressive suspension
            current_timeout = self.settings.get_int("tab-suspension-timeout")
            battery_timeout = max(60, current_timeout // 2)  # Half timeout, min 1 minute
            
            # Reduce max concurrent tabs
            current_max = self.settings.get_int("max-concurrent-tabs")
            battery_max = max(5, current_max // 2)  # Half max tabs, min 5
            
            # More aggressive memory pressure threshold
            current_threshold = self.settings.get_int("memory-pressure-threshold")
            battery_threshold = max(60, current_threshold - 15)  # Lower threshold by 15%
            
            debug_print(f"[PERF] Battery optimizations: timeout={battery_timeout}s, max_tabs={battery_max}, threshold={battery_threshold}%")
            
            # Store original values if not already stored
            if not hasattr(self, '_original_battery_settings'):
                self._original_battery_settings = {
                    'tab-suspension-timeout': current_timeout,
                    'max-concurrent-tabs': current_max,
                    'memory-pressure-threshold': current_threshold
                }
            
            # Apply battery optimizations temporarily
            # Note: These would ideally be temporary overrides, not permanent settings changes
            # For this implementation, we'll use internal overrides
            self._battery_overrides = {
                'tab-suspension-timeout': battery_timeout,
                'max-concurrent-tabs': battery_max,
                'memory-pressure-threshold': battery_threshold
            }
            
            # Force suspension of some inactive tabs immediately
            self._battery_suspend_tabs()
            
        except Exception as e:
            debug_print(f"[PERF] Error applying battery optimizations: {e}")
    
    def _remove_battery_optimizations(self):
        """Remove battery optimizations when on AC power."""
        try:
            # Clear battery overrides
            if hasattr(self, '_battery_overrides'):
                delattr(self, '_battery_overrides')
                
            debug_print("[PERF] Removed battery optimizations")
            
        except Exception as e:
            debug_print(f"[PERF] Error removing battery optimizations: {e}")
    
    def _battery_suspend_tabs(self):
        """Aggressively suspend tabs when on battery."""
        try:
            inactive_tabs = [
                (tab_id, tab_state) for tab_id, tab_state in self.tab_states.items()
                if not tab_state.is_active and not tab_state.is_suspended
            ]
            
            # Sort by inactive time (oldest first)
            inactive_tabs.sort(key=lambda x: x[1].get_inactive_time(), reverse=True)
            
            # Suspend up to half of inactive tabs when on battery
            tabs_to_suspend = len(inactive_tabs) // 2
            
            for i in range(min(tabs_to_suspend, len(inactive_tabs))):
                tab_id, tab_state = inactive_tabs[i]
                if tab_state.get_inactive_time() > 30:  # Only suspend if inactive for 30+ seconds
                    self._suspend_tab(tab_id)
                    
            debug_print(f"[PERF] Battery mode: suspended {min(tabs_to_suspend, len(inactive_tabs))} tabs")
            
        except Exception as e:
            debug_print(f"[PERF] Error in battery tab suspension: {e}")
    
    def get_effective_setting(self, setting_name: str, default_value=None):
        """Get setting value with battery optimizations applied."""
        if (hasattr(self, '_battery_overrides') and 
            self.is_on_battery and 
            setting_name in self._battery_overrides):
            return self._battery_overrides[setting_name]
        
        if default_value is not None:
            return self.settings.get_int(setting_name) if default_value is not None else self.settings.get_boolean(setting_name)
        
        return None
    
    def force_cache_cleanup(self):
        """Force immediate cache cleanup."""
        debug_print("[PERF] Forcing cache cleanup")
        self._check_cache_size()
    
    def get_cache_usage_estimate(self) -> Dict:
        """Get estimated cache usage across all containers."""
        total_cache_size = 0
        container_cache_sizes = {}
        
        if hasattr(self.application, 'container_manager'):
            for container_id in self.application.container_manager.container_network_sessions:
                cache_size = self._estimate_container_cache_size(container_id)
                container_cache_sizes[container_id] = cache_size
                total_cache_size += cache_size
        
        cache_limit_mb = self.settings.get_int("cache-size-limit")
        cache_limit_bytes = cache_limit_mb * 1024 * 1024
        
        return {
            "total_cache_mb": total_cache_size / 1024 / 1024,
            "cache_limit_mb": cache_limit_mb,
            "cache_usage_percent": (total_cache_size / cache_limit_bytes * 100) if cache_limit_bytes > 0 else 0,
            "container_cache_sizes": {k: v / 1024 / 1024 for k, v in container_cache_sizes.items()}
        }
    
    def should_defer_tab_loading(self, is_initial_tab: bool = False) -> bool:
        """Check if tab loading should be deferred based on startup mode."""
        if not self.settings.get_boolean("enable-startup-optimization"):
            return False
            
        if self.startup_complete:
            return False
            
        startup_mode = self.startup_mode
        
        if startup_mode == "immediate":
            return False
        elif startup_mode == "lazy":
            # Load first tab immediately, defer others
            return not is_initial_tab
        elif startup_mode == "on-demand":
            # Defer all tabs until explicitly requested
            return True
        
        return False
    
    def defer_tab_loading(self, tab_id: str, url: str, browser_view):
        """Defer tab loading until later."""
        if tab_id not in [t[0] for t in self.deferred_tabs]:
            self.deferred_tabs.append((tab_id, url, browser_view))
            debug_print(f"[PERF] Deferred loading for tab {tab_id}: {url}")
    
    def load_deferred_tab(self, tab_id: str):
        """Load a specific deferred tab."""
        for i, (deferred_id, url, browser_view) in enumerate(self.deferred_tabs):
            if deferred_id == tab_id:
                debug_print(f"[PERF] Loading deferred tab {tab_id}: {url}")
                browser_view.load_url(url)
                del self.deferred_tabs[i]
                break
    
    def load_all_deferred_tabs(self):
        """Load all deferred tabs."""
        debug_print(f"[PERF] Loading {len(self.deferred_tabs)} deferred tabs")
        for tab_id, url, browser_view in self.deferred_tabs:
            browser_view.load_url(url)
        self.deferred_tabs.clear()
    
    def mark_startup_complete(self):
        """Mark startup as complete and load deferred tabs if needed."""
        self.startup_complete = True
        debug_print("[PERF] Startup marked as complete")
        
        if self.startup_mode == "lazy":
            # Load deferred tabs after a short delay
            GLib.timeout_add_seconds(2, self._delayed_tab_loading)
    
    def _delayed_tab_loading(self) -> bool:
        """Load deferred tabs with a delay."""
        if self.deferred_tabs:
            # Load one tab at a time to avoid overwhelming the system
            tab_id, url, browser_view = self.deferred_tabs.pop(0)
            debug_print(f"[PERF] Loading deferred tab: {url}")
            browser_view.load_url(url)
            
            if self.deferred_tabs:
                # Schedule next tab in 1 second
                GLib.timeout_add_seconds(1, self._delayed_tab_loading)
                
        return False  # Don't repeat this timer
    
    def create_lazy_loading_placeholder(self, url: str, title: str = "Tab") -> str:
        """Create HTML placeholder for lazy-loaded tabs."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            margin: 0;
            padding: 40px;
            font-family: -webkit-system-font, system-ui, sans-serif;
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
        }}
        .container {{
            max-width: 500px;
            background: rgba(255, 255, 255, 0.1);
            padding: 40px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }}
        .icon {{
            font-size: 64px;
            margin-bottom: 20px;
            opacity: 0.8;
        }}
        h1 {{
            margin: 0 0 10px 0;
            font-size: 24px;
            font-weight: 300;
        }}
        .url {{
            opacity: 0.7;
            font-size: 14px;
            word-break: break-all;
            margin: 10px 0 20px 0;
        }}
        .load-btn {{
            background: rgba(255, 255, 255, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
            margin-top: 20px;
            transition: all 0.3s ease;
        }}
        .load-btn:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }}
        .note {{
            opacity: 0.6;
            font-size: 12px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">⚡</div>
        <h1>Tab Ready to Load</h1>
        <div class="url">{url}</div>
        <p>This tab will load when you visit it to improve startup performance.</p>
        <button class="load-btn" onclick="window.location.href='{url}'">
            Load Now
        </button>
        <div class="note">
            Click the tab or the button above to load the page.
        </div>
    </div>
</body>
</html>
        """

    def cleanup(self):
        """Clean up performance manager resources."""
        if self.suspension_timer_id:
            GLib.source_remove(self.suspension_timer_id)
            self.suspension_timer_id = None
            
        if self.memory_monitor_timer_id:
            GLib.source_remove(self.memory_monitor_timer_id)
            self.memory_monitor_timer_id = None
            
        if self.cache_cleanup_timer_id:
            GLib.source_remove(self.cache_cleanup_timer_id)
            self.cache_cleanup_timer_id = None
            
        if self.process_monitor_timer_id:
            GLib.source_remove(self.process_monitor_timer_id)
            self.process_monitor_timer_id = None
            
        if self.battery_monitor_timer_id:
            GLib.source_remove(self.battery_monitor_timer_id)
            self.battery_monitor_timer_id = None
            
        debug_print("[PERF] Performance manager cleaned up")