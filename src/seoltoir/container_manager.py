# seoltoir/seoltoir/container_manager.py

import gi
gi.require_version("WebKit", "6.0")
gi.require_version("Soup", "3.0") # Keep Soup import as it's used elsewhere for URIs etc.
from gi.repository import WebKit, Gio, GLib, Soup

import os
import shutil # For rmtree

class ContainerManager:
    """
    Manages WebKit.WebContext instances for different containers, adhering to WebKit6.0 API.
    Each container gets its own isolated NetworkSession, meaning separate
    cookies, cache, local storage, etc.
    """
    def __init__(self, app_id: str):
        self.app_id = app_id.lower()
        self.container_contexts = {} # Maps container_id to WebKit.WebContext instance
        self.container_network_sessions = {} # Maps container_id to WebKit.NetworkSession instance
        self.container_data_managers = {} # Maps container_id to WebKit.WebsiteDataManager instance

        # Ensure the default persistent context exists
        self.get_context("default", is_private=False)
        # Ensure the default ephemeral context exists
        self.get_context("private", is_private=True)

    def get_context(self, container_id: str, is_private: bool = False) -> WebKit.WebContext:
        """
        Retrieves or creates a WebContext for the given container_id.
        'default' and 'private' are special IDs.
        """
        if container_id not in self.container_contexts:
            network_session = None
            data_manager = None 
            context = None # Initialize context to None

            # Step 1: Determine NetworkSession and its associated WebsiteDataManager
            if container_id == "default":
                network_session = WebKit.NetworkSession.get_default()
                data_manager = network_session.get_website_data_manager() 
                if hasattr(WebKit.WebContext, 'new_with_network_session'):
                    context = WebKit.WebContext.new_with_network_session(network_session)
                else:
                    context = WebKit.WebContext.new()
                cookie_manager = network_session.get_cookie_manager()
                default_cookie_path = os.path.join(GLib.get_user_data_dir(), self.app_id, "cookies.txt")
                cookie_manager.set_persistent_storage(default_cookie_path, WebKit.CookiePersistentStorage.TEXT)
            elif container_id == "private":
                network_session = WebKit.NetworkSession.new_ephemeral()
                data_manager = network_session.get_website_data_manager()
                if hasattr(WebKit.WebContext, 'new_with_network_session'):
                    context = WebKit.WebContext.new_with_network_session(network_session)
                elif hasattr(WebKit.WebContext, 'new_ephemeral'):
                    context = WebKit.WebContext.new_ephemeral()
                else:
                    context = WebKit.WebContext.new()
                # Don't set persistent storage for ephemeral contexts
            else:
                # Custom container: Attempt to create a persistent WebsiteDataManager using new_with_paths.
                # If new_with_paths is missing, we fall back to ephemeral.
                data_manager_path = os.path.join(GLib.get_user_data_dir(), self.app_id, "container_data", container_id)
                os.makedirs(data_manager_path, exist_ok=True)
                
                try:
                    # Attempt to create a persistent WebsiteDataManager with paths
                    data_manager = WebKit.WebsiteDataManager.new_with_paths(data_manager_path, None)
                    network_session = WebKit.NetworkSession.new_with_website_data_manager(data_manager)
                    if hasattr(WebKit.WebContext, 'new_with_network_session'):
                        context = WebKit.WebContext.new_with_network_session(network_session)
                    else:
                        context = WebKit.WebContext.new()
                    print(f"Created new persistent container '{container_id}' at {data_manager_path}")
                    # Set persistent cookie storage
                    cookie_manager = network_session.get_cookie_manager()
                    cookie_path = os.path.join(data_manager_path, "cookies.txt")
                    cookie_manager.set_persistent_storage(cookie_path, WebKit.CookiePersistentStorage.TEXT)
                except AttributeError:
                    # FALLBACK: If new_with_paths is missing, create an ephemeral manager
                    print(f"WARNING: WebKit.WebsiteDataManager.new_with_paths(path, cache_path) not found in this environment. Custom container '{container_id}' will be ephemeral.")
                    data_manager = WebKit.WebsiteDataManager.new_ephemeral()
                    network_session = WebKit.NetworkSession.new_ephemeral()
                    if hasattr(WebKit.WebContext, 'new_with_network_session'):
                        context = WebKit.WebContext.new_with_network_session(network_session)
                    elif hasattr(WebKit.WebContext, 'new_ephemeral'):
                        context = WebKit.WebContext.new_ephemeral()
                    else:
                        context = WebKit.WebContext.new()
                    print(f"Created new ephemeral container '{container_id}' (persistent path not used).")
                    # Don't set persistent storage for ephemeral contexts
            
            # Store instances for later access (e.g., clearing data, reconfiguring)
            self.container_network_sessions[container_id] = network_session
            self.container_data_managers[container_id] = data_manager 
            self.container_contexts[container_id] = context
            
            # Configure context, passing NetworkSession and DataManager directly
            self._configure_context(context, network_session, data_manager, container_id) 
            
        return self.container_contexts[container_id]

    def _configure_context(self, context: WebKit.WebContext, network_session: WebKit.NetworkSession, data_manager: WebKit.WebsiteDataManager, container_id: str):
        """
        Applies common privacy/network settings to a WebContext, using NetworkSession API.
        """
        
        cookie_manager = network_session.get_cookie_manager()
        cookie_manager.set_accept_policy(
            WebKit.CookieAcceptPolicy.NO_THIRD_PARTY
        )

        #print(f"WARNING: Cannot configure DoH/DoT or explicit TLS policy for container '{container_id}'. API (NetworkSession.get_soup_session) is missing. Using system defaults.")

        app = Gio.Application.get_default()
        if app and hasattr(app, 'download_manager'):
            network_session.connect("download-started", app.download_manager.add_download)

        
    def reconfigure_all_contexts(self):
        """Re-applies global settings (like DoH/DoT, adblock) to all active contexts."""
        settings = Gio.Settings.new(self.app_id)
        from .browser_view import SeoltoirBrowserView
        SeoltoirBrowserView._initialize_global_contexts_and_filters()
    

    def _on_decide_policy(self, web_context, policy_decision, policy_decision_type):
        """
        Shared policy decision handler for all container contexts.
        Reuses the logic from SeoltoirBrowserView for consistency.
        """
        from .browser_view import SeoltoirBrowserView
        SeoltoirBrowserView._on_decide_policy(web_context, policy_decision, policy_decision_type)

    def get_container_ids(self) -> list[str]:
        return [cid for cid in self.container_contexts.keys() if cid not in ["default", "private"]]

    def create_new_custom_container(self, name: str) -> str:
        """Creates a new custom container and returns its ID."""
        container_id = name.lower().replace(" ", "_").replace("/", "_")
        if container_id in self.container_contexts:
            container_id += f"_{GLib.random_int_range(1, 1000)}"
        self.get_context(container_id)
        return container_id

    def delete_container(self, container_id: str):
        """Deletes a custom container and its associated data."""
        if container_id in ["default", "private"]:
            print(f"Cannot delete built-in container '{container_id}'.")
            return
        
        if container_id in self.container_contexts:
            context = self.container_contexts.pop(container_id)
            data_manager = self.container_data_managers.pop(container_id)

            if data_manager:
                data_manager.clear(WebKit.WebsiteDataTypes.ALL, 0, None, None)
            
            if container_id not in ["default", "private"]:
                data_path = os.path.join(GLib.get_user_data_dir(), self.app_id, "container_data", container_id)
                if os.path.exists(data_path):
                    try:
                        shutil.rmtree(data_path)
                        print(f"Container '{container_id}' data directory removed: {data_path}")
                    except OSError as e:
                        print(f"Error removing container data directory {data_path}: {e}")
            print(f"Container '{container_id}' and its data deleted.")
