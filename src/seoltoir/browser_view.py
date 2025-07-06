import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit, Gio, GLib, Pango, GObject

import os
import requests
import threading
import urllib.parse
from .debug import debug_print

from .database import DatabaseManager
from .adblock_parser import AdblockParser
from .https_everywhere_rules import HttpsEverywhereRules
from .opensearch_parser import OpenSearchParser

class SeoltoirBrowserView(Gtk.Box):
    __gsignals__ = {
        "uri-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "title-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "favicon-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.Object,)),
        "load-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "can-go-back-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "can-go-forward-changed": (GObject.SignalFlags.RUN_FIRST, None, (bool,)),
        "new-window-requested": (GObject.SignalFlags.RUN_FIRST, None, (WebKit.WebView,)),
        "blocked-count-changed": (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        "show-notification": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "zoom-level-changed": (GObject.SignalFlags.RUN_FIRST, None, (float,)),
        "opensearch-discovered": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    _adblock_parser_instance = None
    _https_everywhere_rules_instance = None
    _opensearch_parser_instance = None
    _ad_block_filter_data = None
    _css_ad_block_scripts_by_domain = {}

    @classmethod
    def _initialize_global_contexts_and_filters(cls):
        app = Gio.Application.get_default()
        if not app or not hasattr(app, 'container_manager'):
            debug_print("Application or ContainerManager not ready. Cannot initialize filters.")
            return

        settings = Gio.Settings.new(app.get_application_id())
        
        if cls._adblock_parser_instance is None:
            cls._load_adblock_filters_from_settings(settings)
        
        if cls._https_everywhere_rules_instance is None:
            cls._load_https_everywhere_rules(settings)
        
        if cls._opensearch_parser_instance is None:
            cls._opensearch_parser_instance = OpenSearchParser()
        
    @classmethod
    def _get_domain_from_uri(cls, uri: str) -> str:
        try:
            parsed = urllib.parse.urlparse(uri)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except ValueError:
            return ""
    
    @classmethod
    def get_context_and_network_session(cls, is_private: bool = False, container_id: str = "default") -> tuple[WebKit.WebContext, WebKit.NetworkSession]:
        app = Gio.Application.get_default()
        context = app.container_manager.get_context(container_id, is_private)
        network_session = app.container_manager.container_network_sessions.get(container_id)
        
        if not network_session and context:
            network_session = context.get_network_session()

        return context, network_session

    @classmethod
    def _load_adblock_filters_from_settings(cls, settings: Gio.Settings):
        filter_urls = settings.get_strv("adblock-filter-urls")
        if not filter_urls:
            debug_print("No adblock filter URLs configured.")
            cls._ad_block_filter_data = None
            cls._css_ad_block_scripts_by_domain = {}
            cls._adblock_parser_instance = None
            return

        def _download_and_parse_filters():
            parser = AdblockParser()
            all_rules_content = []
            for url in filter_urls:
                debug_print(f"Downloading adblock filter: {url}")
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    all_rules_content.append(response.text)
                    debug_print(f"Successfully downloaded {url}")
                except requests.exceptions.RequestException as e:
                    debug_print(f"Error downloading {url}: {e}")
            
            if all_rules_content:
                full_rules_string = "\n".join(all_rules_content)
                parser.parse_rules_from_string(full_rules_string)
                
                cls._ad_block_filter_data = parser.get_webkit_content_filter_json()
                cls._css_ad_block_scripts_by_domain = parser.get_webkit_css_user_scripts()
                cls._adblock_parser_instance = parser
                debug_print("Adblock filter lists downloaded and parsed.")
                
                GLib.idle_add(cls._reapply_filters_to_all_webviews)
            else:
                cls._ad_block_filter_data = None
                cls._css_ad_block_scripts_by_domain = {}
                cls._adblock_parser_instance = None
                debug_print("No filter lists downloaded successfully.")
                GLib.idle_add(cls._reapply_filters_to_all_webviews)

        threading.Thread(target=_download_and_parse_filters, daemon=True).start()

    @classmethod
    def _load_https_everywhere_rules(cls, settings: Gio.Settings):
        enable_https_everywhere = settings.get_boolean("enable-https-everywhere")
        rules_url = settings.get_string("https-everywhere-rules-url")

        if not enable_https_everywhere or not rules_url:
            debug_print("HTTPS Everywhere is disabled or no rules URL configured.")
            cls._https_everywhere_rules_instance = None
            return
        
        def _download_and_parse_https_rules():
            debug_print(f"Downloading HTTPS Everywhere rules: {rules_url}")
            try:
                response = requests.get(rules_url, timeout=30)
                response.raise_for_status()
                rules_parser = HttpsEverywhereRules()
                rules_parser.parse_rules_from_string(response.text)
                cls._https_everywhere_rules_instance = rules_parser
                debug_print("HTTPS Everywhere rules downloaded and parsed.")
            except requests.exceptions.RequestException as e:
                debug_print(f"Error downloading HTTPS Everywhere rules from {rules_url}: {e}")
                cls._https_everywhere_rules_instance = None
            except Exception as e:
                debug_print(f"Error parsing HTTPS Everywhere rules: {e}")
                cls._https_everywhere_rules_instance = None
        
        threading.Thread(target=_download_and_parse_https_rules, daemon=True).start()

    @classmethod
    def _reapply_filters_to_all_webviews(cls):
        app = Gio.Application.get_default()
        if not app: return

        settings = Gio.Settings.new(app.get_application_id())
        enable_ad_blocking = settings.get_boolean("enable-ad-blocking")

        app.container_manager.reconfigure_all_contexts()
        
        debug_print("Re-applied adblock filters to all WebViews.")

    @classmethod
    def apply_ad_block_filter(cls, user_content_manager: WebKit.UserContentManager, enable: bool):
        cls._initialize_global_contexts_and_filters()

        filter_name = "seoltoir-ad-blocker"
        user_content_manager.remove_filter_by_id(filter_name)

        if enable and cls._ad_block_filter_data:
            try:
                filter_bytes = GLib.Bytes.new(cls._ad_block_filter_data.encode('utf-8'))
                # Try different method names for UserContentFilter creation
                try:
                    content_filter = WebKit.UserContentFilter.new_from_bytes(filter_bytes, filter_name, None)
                except AttributeError:
                    # Try alternative method name
                    try:
                        content_filter = WebKit.UserContentFilter.new(filter_bytes, filter_name, None)
                    except AttributeError:
                        debug_print("UserContentFilter.new_from_bytes/new not available in this WebKit version")
                        content_filter = None
                
                if content_filter:
                    user_content_manager.add_filter(content_filter)
                else:
                    debug_print("Failed to create user content filter (from parsed data).")
            except Exception as e:
                debug_print(f"Error applying user content filter: {e}")

            for domain, css_string in cls._css_ad_block_scripts_by_domain.items():
                script_name = f"seoltoir-css-hide-{domain}"
                
                allowed_hosts = None
                if domain != "*":
                    allowed_hosts = Gtk.StringList.new([domain])
                
                css_script = WebKit.UserScript.new(
                    f"var style = document.createElement('style'); style.id = 'seoltoir-css-style-{domain}'; style.innerHTML = `{css_string}`; document.head.appendChild(style);",
                    WebKit.UserContentInjectedFrames.ALL_FRAMES,
                    WebKit.UserScriptInjectionTime.DOCUMENT_START,
                    allowed_hosts,
                    None
                )
                user_content_manager.add_script(css_script, script_name)

    @classmethod
    def new_from_webkit_view(cls, web_view: WebKit.WebView, db_manager: DatabaseManager, container_id: str = "default"):
        instance = cls.__new__(cls)
        super(SeoltoirBrowserView, instance).__init__(orientation=Gtk.Orientation.VERTICAL)
        instance.webview = web_view
        instance.db_manager = db_manager
        instance.container_id = container_id
        instance.is_private = (container_id == "private" or web_view.get_web_context().is_ephemeral())
        instance.blocked_count_for_page = 0
        instance._setup_signals_and_properties()
        instance._configure_webkit_settings()
        instance._setup_content_blocking()
        instance.append(instance.webview)
        return instance

    def __init__(self, db_manager: DatabaseManager, is_private: bool = False, container_id: str = "default"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)

        self.db_manager = db_manager
        self.is_private = is_private
        self.container_id = container_id
        self.blocked_count_for_page = 0
        self.is_reading_mode_active = False
        
        self.settings = Gio.Settings.new(Gio.Application.get_default().get_application_id())

        # Get context and network session from container manager
        self.context, self.network_session = self.get_context_and_network_session(is_private, container_id)
        
        # --- CHANGED: Create a UserContentManager and pass it to the WebView ---
        self.user_content_manager = WebKit.UserContentManager.new()
        if is_private:
            from gi.repository import GObject
            ephemeral_session = WebKit.NetworkSession.new_ephemeral()
            self.webview = GObject.new(WebKit.WebView, network_session=ephemeral_session, user_content_manager=self.user_content_manager)
            self.network_session = ephemeral_session
        else:
            from gi.repository import GObject
            if hasattr(WebKit.WebView, 'new_with_context'):
                # Use GObject.new to pass user_content_manager during creation
                self.webview = GObject.new(WebKit.WebView, web_context=self.context, user_content_manager=self.user_content_manager)
            else:
                self.webview = GObject.new(WebKit.WebView, user_content_manager=self.user_content_manager)
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)
        self.append(self.webview)

        self._setup_signals_and_properties()
        self._configure_webkit_settings()
        self._setup_content_blocking()

        self.settings.connect("changed::enable-ad-blocking", self._on_ad_blocking_setting_changed)
        self.settings.connect("changed::user-agent", self._on_user_agent_setting_changed)
        self.settings.connect("changed::enable-webrtc", self._on_webrtc_setting_changed)
        self.settings.connect("changed::enable-doh", self._on_doh_setting_changed)
        self.settings.connect("changed::doh-provider-url", self._on_doh_setting_changed)
        self.settings.connect("changed::enable-dot", self._on_dot_setting_changed)
        self.settings.connect("changed::dot-provider-host", self._on_dot_setting_changed)
        self.settings.connect("changed::dot-provider-port", self._on_dot_setting_changed)
        self.settings.connect("changed::adblock-filter-urls", self._on_adblock_urls_setting_changed)
        self.settings.connect("changed::enable-https-everywhere", self._on_https_everywhere_setting_changed)
        self.settings.connect("changed::https-everywhere-rules-url", self._on_https_everywhere_setting_changed)
        self.settings.connect("changed::enable-javascript", self._on_javascript_setting_changed)
        self.settings.connect("changed::javascript-exceptions", self._on_javascript_setting_changed)

        self.webview.connect("resource-load-started", self._on_resource_load_started)
        self.webview.connect("load-changed", self._on_load_changed)
        self.webview.connect("notify::title", self._on_title_changed)

        self.settings.connect("changed::default-font-family", self._on_font_setting_changed)
        self.settings.connect("changed::default-font-size", self._on_font_setting_changed)

        enable_ad_blocking = self.settings.get_boolean("enable-ad-blocking")
        SeoltoirBrowserView.apply_ad_block_filter(self.user_content_manager, enable_ad_blocking)

    def _on_font_setting_changed(self, settings, key):
        self._configure_webkit_settings()

    def _on_resource_load_started(self, webview, web_resource, request):
        if self.settings.get_boolean("enable-ad-blocking") and self._adblock_parser_instance:
            uri = request.get_uri()
            main_document_uri = webview.get_uri()
            
            main_domain = self._get_domain_from_uri(main_document_uri)
            resource_domain = self._get_domain_from_uri(uri)
            
            options = {
                'domain': main_domain,
                'third_party': main_domain != resource_domain
            }
            
            if self._adblock_parser_instance.should_block_url(uri, options):
                self.blocked_count_for_page += 1
                self.emit("blocked-count-changed", self.blocked_count_for_page)
                self.emit("show-notification", f"Blocked: {os.path.basename(urllib.parse.urlparse(uri).path or uri)}")
        
    def _configure_webkit_settings(self):
        settings = self.webview.get_settings()
        
        settings.set_enable_developer_extras(True)
        settings.set_javascript_can_open_windows_automatically(True)
        settings.set_javascript_can_access_clipboard(False)
        
        settings.set_enable_page_cache(False)
        settings.set_enable_offline_web_application_cache(False)
        settings.set_enable_dns_prefetching(False)
        # REMOVE or comment out this line:
        # settings.set_enable_private_browsing(False)
        
        enable_webrtc = self.settings.get_boolean("enable-webrtc")
        settings.set_enable_webrtc(enable_webrtc)

        custom_ua = self.settings.get_string("user-agent")
        settings.set_user_agent(custom_ua if custom_ua else None)

        user_content_manager = self.user_content_manager
        user_content_manager.remove_all_scripts()  # Remove all scripts before adding new ones

        canvas_spoof_script = """
        (function() {
            const addNoise = (value, factor = 0.001) => value * (1 + (Math.random() - 0.5) * factor);
            const randomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

            const createSpoofedMethod = (originalMethod, type = 'float') => {
                return function(...args) {
                    const result = originalMethod.apply(this, args);
                    if (typeof result === type) {
                        return type === 'float' ? addNoise(result, 0.000001) : randomInt(result - 1, result + 1);
                    }
                    return result;
                };
            };

            const spoofWebGL = (gl) => {
                const originalGetParameter = gl.getParameter;
                gl.getParameter = function(pname) {
                    const result = originalGetParameter.apply(this, arguments);
                    if (typeof result === 'number' && [
                        gl.MAX_COMBINED_TEXTURE_IMAGE_UNITS,
                        gl.MAX_CUBE_MAP_TEXTURE_SIZE,
                        gl.MAX_RENDERBUFFER_SIZE,
                        gl.MAX_TEXTURE_SIZE,
                        gl.MAX_VIEWPORT_DIMS,
                    ].includes(pname)) {
                        if (typeof result === 'number') {
                            return addNoise(result, 0.0001);
                        }
                    } else if (typeof result === 'string' && [
                        gl.RENDERER, gl.VENDOR, gl.VERSION, gl.SHADING_LANGUAGE_VERSION
                    ].includes(pname)) {
                        return result + ' (spoofed)';
                    }
                    return result;
                };
            };

            const originalGetContext = HTMLCanvasElement.prototype.getContext;
            HTMLCanvasElement.prototype.getContext = function(contextType, contextAttributes) {
                const context = originalGetContext.apply(this, arguments);
                if (context && (contextType === 'webgl' || contextType === 'webgl2')) {
                    spoofWebGL(context);
                }
                return context;
            };

            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(type, encoderOptions) {
                const context = this.getContext('2d');
                if (context) {
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    if (imageData && imageData.data) {
                        for (let i = 0; i < 20; i++) {
                            const pixelIndex = randomInt(0, imageData.data.length / 4 - 1) * 4;
                            imageData.data[pixelIndex + 0] = addNoise(imageData.data[pixelIndex + 0], 0.01);
                            imageData.data[pixelIndex + 1] = addNoise(imageData.data[pixelIndex + 1], 0.01);
                            imageData.data[pixelIndex + 2] = addNoise(imageData.data[pixelIndex + 2], 0.01);
                        }
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, arguments);
            };

            const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
            CanvasRenderingContext2D.prototype.getImageData = function(sx, sy, sw, sh) {
                const imageData = originalGetImageData.apply(this, arguments);
                if (imageData && imageData.data) {
                    for (let i = 0; i < 20; i++) {
                        const pixelIndex = randomInt(0, imageData.data.length / 4 - 1) * 4;
                        imageData.data[pixelIndex + 0] = addNoise(imageData.data[pixelIndex + 0], 0.01);
                        imageData.data[pixelIndex + 1] = addNoise(imageData.data[pixelIndex + 1], 0.01);
                        imageData.data[pixelIndex + 2] = addNoise(imageData.data[pixelIndex + 2], 0.01);
                    }
                }
                return imageData;
            };

            if (window.AudioContext) {
                const originalCreateOscillator = AudioContext.prototype.createOscillator;
                AudioContext.prototype.createOscillator = function() {
                    const oscillator = originalCreateOscillator.apply(this, arguments);
                    oscillator.frequency.value = addNoise(oscillator.frequency.value, 0.001);
                    return oscillator;
                };

                const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
                AudioContext.prototype.createAnalyser = function() {
                    const analyser = originalCreateAnalyser.apply(this, arguments);
                    analyser.fftSize = randomInt(analyser.fftSize - 2, analyser.fftSize + 2);
                    return analyser;
                };
            }

            const spoofedFonts = ["Arial", "Courier New", "Georgia", "Times New Roman", "Verdana", "Roboto", "Noto Sans", "Open Sans", "Segoe UI"];
            Object.defineProperty(navigator, 'fonts', {
                get: () => ({
                    ready: Promise.resolve(),
                    check: () => true,
                    forEach: (callback) => {
                        spoofedFonts.forEach(font => callback({ family: font, style: 'normal', weight: 'normal' }));
                    },
                    keys: () => spoofedFonts.values(),
                    values: () => spoofedFonts.values(),
                    entries: () => {
                        const entries = spoofedFonts.map(font => [font, { family: font, style: 'normal', weight: 'normal' }]);
                        return entries.values();
                    },
                        for (const font of spoofedFonts) {
                            yield { family: font, style: 'normal', weight: 'normal' };
                        }
                    }
                })
            });

            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => randomInt(2, 8)
            });
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => randomInt(4, 16)
            });
        })();
        """
        canvas_script = WebKit.UserScript.new(
            canvas_spoof_script,
            WebKit.UserContentInjectedFrames.ALL_FRAMES,
            WebKit.UserScriptInjectionTime.START,
            None, None
        )
        user_content_manager.add_script(canvas_script)

        # --- HTTPS Everywhere rules injection ---
        if self._https_everywhere_rules_instance:
            for rule in self._https_everywhere_rules_instance.get_rules():
                self.webview.add_https_everywhere_rule(rule)

        # --- Content Security Policy (CSP) header modification ---
        self.webview.connect("decide-policy", self._on_decide_policy)

    def _on_decide_policy(self, webview, decision, policy):
        # Remove or comment out the CSP header modification block
        # if policy.get("Content-Security-Policy"):
        #     csp = policy.get("Content-Security-Policy")
        #     csp += " script-src 'self' 'unsafe-eval' 'unsafe-inline';"
        #     policy.set("Content-Security-Policy", csp)
        decision.use()

    def _setup_content_blocking(self):
        # --- CHANGED: Use the new UserContentManager instance ---
        #self.webview.set_user_content_manager(self.user_content_manager)

        # --- Adblock Plus integration ---
        enable_ad_blocking = self.settings.get_boolean("enable-ad-blocking")
        SeoltoirBrowserView.apply_ad_block_filter(self.user_content_manager, enable_ad_blocking)

        # --- HTTPS Everywhere integration ---
        if self._https_everywhere_rules_instance:
            for rule in self._https_everywhere_rules_instance.get_rules():
                self.webview.add_https_everywhere_rule(rule)

    def _setup_signals_and_properties(self):
        debug_print("[DEBUG] === _setup_signals_and_properties STARTING ===")
        # --- CHANGED: Connect to the new signals for the WebView ---
        self.webview.connect("load-changed", self._on_load_changed)
        debug_print("[DEBUG] Connected load-changed signal to _on_load_changed")
        self.webview.connect("resource-load-started", self._on_resource_load_started)
        self.webview.connect("context-menu", self._on_context_menu)
        debug_print("[DEBUG] Connected context-menu signal to _on_context_menu")

        # --- Adblock Plus signals ---
        # Note: AdblockParser is not a GObject, so no signals to connect

        # --- Inject favicon extractor ---
        debug_print("[DEBUG] About to inject favicon extractor...")
        self._inject_favicon_extractor()
        debug_print("[DEBUG] === _setup_signals_and_properties COMPLETE ===")

    def _inject_favicon_extractor(self):
        """Inject JavaScript to extract favicon URLs from the page."""
        debug_print("[DEBUG] === _inject_favicon_extractor STARTING ===")
        favicon_script = """
        (function() {
            console.log('[FAVICON-JS] Script starting...');
            function findFavicon() {
                console.log('[FAVICON-JS] Looking for favicon links...');
                const links = document.querySelectorAll('link[rel*="icon"]');
                const favicons = [];
                
                console.log('[FAVICON-JS] Found ' + links.length + ' icon links');
                
                for (let link of links) {
                    const href = link.href;
                    const rel = link.rel;
                    const sizes = link.sizes ? link.sizes.value : '';
                    
                    console.log('[FAVICON-JS] Found link: ' + href + ' (rel: ' + rel + ')');
                    
                    if (href) {
                        favicons.push({
                            url: href,
                            rel: rel,
                            sizes: sizes
                        });
                    }
                }
                
                // If no favicon links found, try to construct default favicon URL
                if (favicons.length === 0) {
                    const defaultFavicon = window.location.origin + '/favicon.ico';
                    console.log('[FAVICON-JS] No links found, trying default: ' + defaultFavicon);
                    favicons.push({
                        url: defaultFavicon,
                        rel: 'icon',
                        sizes: ''
                    });
                }
                
                return favicons;
            }
            
            const favicons = findFavicon();
            if (favicons.length > 0) {
                console.log('[FAVICON-JS] Posting message with URL: ' + favicons[0].url);
                // Emit the favicon URL to the Python side
                if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.faviconHandler) {
                    window.webkit.messageHandlers.faviconHandler.postMessage(favicons[0].url);
                    console.log('[FAVICON-JS] Message posted successfully');
                } else {
                    console.log('[FAVICON-JS] ERROR: faviconHandler not available!');
                }
            } else {
                console.log('[FAVICON-JS] No favicons found');
            }
        })();
        """
        
        # Create a user script to inject the favicon extractor
        debug_print("[DEBUG] Creating UserScript...")
        try:
            script = WebKit.UserScript.new(
                favicon_script,
                WebKit.UserContentInjectedFrames.ALL_FRAMES,
                WebKit.UserScriptInjectionTime.END,
                None,
                None
            )
            debug_print("[DEBUG] UserScript created successfully")
        except Exception as e:
            debug_print(f"[DEBUG] ERROR creating UserScript: {e}")
            return
        
        # Add the script to the user content manager
        debug_print("[DEBUG] Adding script to user content manager...")
        try:
            self.user_content_manager.add_script(script)
            debug_print("[DEBUG] Script added successfully")
        except Exception as e:
            debug_print(f"[DEBUG] ERROR adding script: {e}")
            return
        
        # Register a message handler to receive the favicon URL
        debug_print("[DEBUG] Registering message handler...")
        try:
            self.user_content_manager.register_script_message_handler("faviconHandler")
            debug_print("[DEBUG] Message handler registered")
        except Exception as e:
            debug_print(f"[DEBUG] ERROR registering handler: {e}")
            return
            
        debug_print("[DEBUG] Connecting to signal...")
        try:
            self.user_content_manager.connect("script-message-received::faviconHandler", self._on_favicon_message_received)
            debug_print("[DEBUG] Signal connected successfully")
        except Exception as e:
            debug_print(f"[DEBUG] ERROR connecting signal: {e}")
            return
            
        debug_print("[DEBUG] === _inject_favicon_extractor COMPLETE ===")

    def _on_adblock_blocked(self, parser, uri, options):
        self.blocked_count_for_page += 1
        self.emit("blocked-count-changed", self.blocked_count_for_page)
        self.emit("show-notification", f"Blocked by Adblock Plus: {os.path.basename(urllib.parse.urlparse(uri).path or uri)}")

    def _on_load_changed(self, webview, load_event):
        debug_print(f"[DEBUG] === _on_load_changed called with event: {load_event} ===")
        if load_event == WebKit.LoadEvent.COMMITTED:
            debug_print("[DEBUG] Load event: COMMITTED")
            # Reset blocked count on new page load
            self.blocked_count_for_page = 0

            # --- CHANGED: Reapply content blocking on every page load ---
            SeoltoirBrowserView.apply_ad_block_filter(self.user_content_manager, self.settings.get_boolean("enable-ad-blocking"))

            # --- HTTPS Everywhere rules re-application ---
            if self._https_everywhere_rules_instance:
                for rule in self._https_everywhere_rules_instance.get_rules():
                    self.webview.add_https_everywhere_rule(rule)
        
        elif load_event == WebKit.LoadEvent.FINISHED:
            debug_print("[DEBUG] Load event: FINISHED")
            # Page has finished loading, emit signals for title, URI, and favicon
            uri = self.webview.get_uri()
            title = self.webview.get_title()
            favicon = self.webview.get_favicon()
            debug_print(f"[DEBUG] FINISHED: uri={uri}, title={title}, favicon={favicon} (type: {type(favicon)})")
            debug_print("[DEBUG] Emitting uri-changed signal...")
            self.emit("uri-changed", uri)
            debug_print("[DEBUG] Emitting title-changed signal...")
            self.emit("title-changed", title)
            if favicon:
                debug_print(f"[DEBUG] *** EMITTING WEBKIT FAVICON: {favicon} ***")
                self.emit("favicon-changed", favicon)
            else:
                debug_print("[DEBUG] No WebKit favicon available, trying JavaScript extraction.")
                # Try to fetch favicon from domain root as fallback
                self._fetch_favicon_fallback(uri)
            debug_print("[DEBUG] Emitting navigation signals...")
            self.emit("can-go-back-changed", self.webview.can_go_back())
            self.emit("can-go-forward-changed", self.webview.can_go_forward())
            
            # Load saved zoom level for this domain
            self.load_saved_zoom_level()
            
            # Detect OpenSearch descriptors on the page
            self._detect_opensearch_descriptors()

    def _on_title_changed(self, webview, pspec):
        """Handle title changes in the webview."""
        title = webview.get_title()
        if title:
            debug_print(f"[DEBUG] Title changed to: {title}")
            self.emit("title-changed", title)

    def _on_ad_blocking_setting_changed(self, settings, key):
        enabled = settings.get_boolean(key)
        SeoltoirBrowserView.apply_ad_block_filter(self.user_content_manager, enabled)

    def _on_user_agent_setting_changed(self, settings, key):
        custom_ua = settings.get_string(key)
        self.webview.get_settings().set_user_agent(custom_ua if custom_ua else None)

    def _on_webrtc_setting_changed(self, settings, key):
        enabled = settings.get_boolean(key)
        self.webview.get_settings().set_enable_webrtc(enabled)

    def _on_doh_setting_changed(self, settings, key):
        enabled = settings.get_boolean("enable-doh")
        provider_url = settings.get_string("doh-provider-url") if enabled else ""
        self.webview.get_settings().set_doh_provider_url(provider_url)

    def _on_dot_setting_changed(self, settings, key):
        enabled = settings.get_boolean("enable-dot")
        provider_host = settings.get_string("dot-provider-host") if enabled else ""
        provider_port = settings.get_int("dot-provider-port") if enabled else 853
        self.webview.get_settings().set_dot_provider(provider_host, provider_port)

    def _on_adblock_urls_setting_changed(self, settings, key):
        SeoltoirBrowserView._load_adblock_filters_from_settings(settings)

    def _on_https_everywhere_setting_changed(self, settings, key):
        SeoltoirBrowserView._load_https_everywhere_rules(settings)

    def _on_javascript_setting_changed(self, settings, key):
        self._configure_webkit_settings()

    def _on_favicon_message_received(self, user_content_manager, message):
        """Handle the received favicon URL and fetch the favicon."""
        debug_print(f"[DEBUG] === _on_favicon_message_received CALLED ===")
        debug_print(f"[DEBUG] user_content_manager: {user_content_manager}")
        debug_print(f"[DEBUG] message: {message}")
        try:
            favicon_url = message.get_js_value().to_string()
            debug_print(f"[DEBUG] *** FAVICON MESSAGE RECEIVED: {favicon_url} ***")
        except Exception as e:
            debug_print(f"[DEBUG] ERROR extracting favicon URL: {e}")
            return
        
        # Fetch the favicon in a background thread
        def fetch_favicon():
            try:
                import requests
                from PIL import Image
                import io
                
                response = requests.get(favicon_url, timeout=5)
                response.raise_for_status()
                
                # Convert the image to PNG format that GTK can handle
                image_data = response.content
                image = Image.open(io.BytesIO(image_data))
                
                # Convert to RGBA if needed
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')
                
                # Resize to a reasonable size for icons (16x16 or 32x32)
                if image.size[0] > 32 or image.size[1] > 32:
                    image.thumbnail((32, 32), Image.Resampling.LANCZOS)
                
                # Convert to PNG bytes
                png_buffer = io.BytesIO()
                image.save(png_buffer, format='PNG')
                png_data = png_buffer.getvalue()
                
                # Convert to base64 and create BytesIcon
                import base64
                base64_data = base64.b64encode(png_data).decode('ascii')
                icon_bytes = GLib.Bytes.new(png_data)
                icon = Gio.BytesIcon.new(icon_bytes)
                
                # Emit the favicon signal on the main thread
                GLib.idle_add(self.emit, "favicon-changed", icon)
                debug_print(f"[DEBUG] Successfully converted favicon to base64 from {favicon_url}")
                
            except ImportError:
                # PIL not available, try with raw data
                try:
                    response = requests.get(favicon_url, timeout=5)
                    response.raise_for_status()
                    
                    icon_data = response.content
                    # Always convert to PNG for consistency
                    try:
                        from PIL import Image
                        import io
                        
                        # Load the image and convert to PNG
                        image = Image.open(io.BytesIO(icon_data))
                        if image.mode != 'RGBA':
                            image = image.convert('RGBA')
                        
                        # Resize to 32x32 for consistency
                        if image.size != (32, 32):
                            image = image.resize((32, 32), Image.Resampling.LANCZOS)
                        
                        # Save as PNG
                        png_buffer = io.BytesIO()
                        image.save(png_buffer, format='PNG')
                        png_data = png_buffer.getvalue()
                        
                        icon_bytes = GLib.Bytes.new(png_data)
                        icon = Gio.BytesIcon.new(icon_bytes)
                        
                        GLib.idle_add(self.emit, "favicon-changed", icon)
                        debug_print(f"[DEBUG] Successfully normalized favicon to PNG from {favicon_url}")
                        
                    except Exception as e:
                        debug_print(f"[DEBUG] Failed to normalize favicon: {e}")
                        # Fallback to raw data if PIL fails
                        if len(icon_data) > 0 and icon_data.startswith(b'\x89PNG'):
                            icon_bytes = GLib.Bytes.new(icon_data)
                            icon = Gio.BytesIcon.new(icon_bytes)
                            GLib.idle_add(self.emit, "favicon-changed", icon)
                            debug_print(f"[DEBUG] Used raw PNG data for {favicon_url}")
                        else:
                            debug_print(f"[DEBUG] Cannot use raw data for {favicon_url}")
                    
                except Exception as e:
                    debug_print(f"[DEBUG] Failed to fetch favicon from {favicon_url}: {e}")
                    
            except Exception as e:
                debug_print(f"[DEBUG] Failed to fetch/convert favicon from {favicon_url}: {e}")
        
        # Start the favicon fetch in a background thread
        import threading
        threading.Thread(target=fetch_favicon, daemon=True).start()

    def load_url(self, url: str):
        """Load the given URL in the internal WebKit.WebView."""
        self.webview.load_uri(url)

    def get_uri(self):
        return self.webview.get_uri() if hasattr(self, 'webview') and self.webview else None

    def get_title(self):
        return self.webview.get_title() if hasattr(self, 'webview') and self.webview else None

    def clear_find_results(self):
        if hasattr(self.webview, 'search_text'):
            # WebKitGTK 4: clear search highlights by searching for empty string
            self.webview.search_text('', 0, False, True, True)
        # If there is a more appropriate method in your WebKitGTK version, use it here.

    def _fetch_favicon_fallback(self, uri):
        """Try to fetch favicon.ico from the domain root as a fallback."""
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(uri)
            domain = parsed.netloc
            favicon_url = f"https://{domain}/favicon.ico"
            debug_print(f"[DEBUG] Trying to fetch favicon from: {favicon_url}")
            
            # Fetch the favicon in a background thread
            def fetch_favicon():
                try:
                    import requests
                    from PIL import Image
                    import io
                    
                    response = requests.get(favicon_url, timeout=5)
                    response.raise_for_status()
                    
                    # Convert the image to PNG format that GTK can handle
                    image_data = response.content
                    image = Image.open(io.BytesIO(image_data))
                    
                    # Convert to RGBA if needed
                    if image.mode != 'RGBA':
                        image = image.convert('RGBA')
                    
                    # Resize to a reasonable size for icons (16x16 or 32x32)
                    if image.size[0] > 32 or image.size[1] > 32:
                        image.thumbnail((32, 32), Image.Resampling.LANCZOS)
                    
                    # Convert to PNG bytes
                    png_buffer = io.BytesIO()
                    image.save(png_buffer, format='PNG')
                    png_data = png_buffer.getvalue()
                    
                    # Convert the PNG data to a GIcon
                    icon_bytes = GLib.Bytes.new(png_data)
                    icon = Gio.BytesIcon.new(icon_bytes)
                    
                    # Emit the favicon signal on the main thread
                    GLib.idle_add(self.emit, "favicon-changed", icon)
                    debug_print(f"[DEBUG] Successfully fetched and converted favicon from {favicon_url}")
                    
                except ImportError:
                    # PIL not available, try with raw data
                    try:
                        response = requests.get(favicon_url, timeout=5)
                        response.raise_for_status()
                        
                        icon_data = response.content
                        # Always convert to PNG for consistency
                        try:
                            from PIL import Image
                            import io
                            
                            # Load the image and convert to PNG
                            image = Image.open(io.BytesIO(icon_data))
                            if image.mode != 'RGBA':
                                image = image.convert('RGBA')
                            
                            # Resize to 32x32 for consistency
                            if image.size != (32, 32):
                                image = image.resize((32, 32), Image.Resampling.LANCZOS)
                            
                            # Save as PNG
                            png_buffer = io.BytesIO()
                            image.save(png_buffer, format='PNG')
                            png_data = png_buffer.getvalue()
                            
                            icon_bytes = GLib.Bytes.new(png_data)
                            icon = Gio.BytesIcon.new(icon_bytes)
                            
                            GLib.idle_add(self.emit, "favicon-changed", icon)
                            debug_print(f"[DEBUG] Successfully normalized fallback favicon to PNG from {favicon_url}")
                            
                        except Exception as e:
                            debug_print(f"[DEBUG] Failed to normalize fallback favicon: {e}")
                            # Fallback to raw data if PIL fails
                            if len(icon_data) > 0 and icon_data.startswith(b'\x89PNG'):
                                icon_bytes = GLib.Bytes.new(icon_data)
                                icon = Gio.BytesIcon.new(icon_bytes)
                                GLib.idle_add(self.emit, "favicon-changed", icon)
                                debug_print(f"[DEBUG] Used raw PNG fallback data for {favicon_url}")
                            else:
                                debug_print(f"[DEBUG] Cannot use raw fallback data for {favicon_url}")
                        
                    except Exception as e:
                        debug_print(f"[DEBUG] Failed to fetch favicon from {favicon_url}: {e}")
                        
                except Exception as e:
                    debug_print(f"[DEBUG] Failed to fetch/convert favicon from {favicon_url}: {e}")
            
            # Start the favicon fetch in a background thread
            import threading
            threading.Thread(target=fetch_favicon, daemon=True).start()
            
        except Exception as e:
            debug_print(f"[DEBUG] Error in favicon fallback for {uri}: {e}")


    def _get_domain_from_url(self, url: str) -> str:
        """Extract domain from URL for zoom level persistence."""
        try:
            parsed = urllib.parse.urlparse(url)
            domain = parsed.netloc
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except ValueError:
            return ""

    def get_zoom_level(self) -> float:
        """Get the current zoom level."""
        return self.webview.get_zoom_level()

    def set_zoom_level(self, zoom_level: float, save_to_db: bool = True):
        """Set the zoom level and optionally save to database."""
        # Clamp zoom level to reasonable bounds
        zoom_level = max(0.25, min(5.0, zoom_level))
        
        self.webview.set_zoom_level(zoom_level)
        self.emit("zoom-level-changed", zoom_level)
        
        if save_to_db:
            current_uri = self.get_uri()
            if current_uri:
                domain = self._get_domain_from_url(current_uri)
                if domain:
                    self.db_manager.set_zoom_level(domain, zoom_level)

    def zoom_in(self):
        """Zoom in by 25%."""
        current_zoom = self.get_zoom_level()
        new_zoom = current_zoom * 1.25
        self.set_zoom_level(new_zoom)
        self.emit("show-notification", f"Zoom: {int(new_zoom * 100)}%")

    def zoom_out(self):
        """Zoom out by 25%."""
        current_zoom = self.get_zoom_level()
        new_zoom = current_zoom / 1.25
        self.set_zoom_level(new_zoom)
        self.emit("show-notification", f"Zoom: {int(new_zoom * 100)}%")

    def zoom_reset(self):
        """Reset zoom to 100%."""
        self.set_zoom_level(1.0)
        self.emit("show-notification", "Zoom: 100%")

    def load_saved_zoom_level(self):
        """Load the saved zoom level for the current domain."""
        current_uri = self.get_uri()
        if current_uri:
            domain = self._get_domain_from_url(current_uri)
            if domain:
                saved_zoom = self.db_manager.get_zoom_level(domain)
                if saved_zoom != 1.0:  # Only set if different from default
                    self.set_zoom_level(saved_zoom, save_to_db=False)

    def print_page(self, print_selection_only=False):
        """Print the current page with enhanced functionality."""
        print_manager = SeoltoirPrintManager(self.webview, self.get_toplevel())
        
        if print_selection_only:
            # Check if there's selected text first
            self.webview.run_javascript("window.getSelection().toString();", None, self._on_check_selection_for_print, print_manager)
        else:
            print_manager.show_print_dialog()

    def _on_check_selection_for_print(self, webview, result, print_manager):
        """Check if there's text selection and proceed with print."""
        try:
            js_result = webview.run_javascript_finish(result)
            if js_result:
                selected_text = js_result.get_js_value().to_string()
                if selected_text and selected_text.strip():
                    print_manager.print_selection(selected_text)
                else:
                    self.emit("show-notification", "No text selected for printing")
                    print_manager.show_print_dialog()  # Fall back to full page
            else:
                print_manager.show_print_dialog()
        except Exception as e:
            debug_print(f"[DEBUG] Error checking selection for print: {e}")
            print_manager.show_print_dialog()  # Fall back to full page

    def _on_context_menu(self, webview, context_menu, event, hit_test_result):
        """Handle context menu events for web content."""
        debug_print("[DEBUG] Context menu triggered")
        
        # Clear the default context menu
        context_menu.remove_all()
        
        # Get context information from hit test result
        context = hit_test_result.get_context()
        
        # Build custom context menu based on the element type
        if context & WebKit.HitTestResultContext.LINK:
            self._build_link_context_menu(context_menu, hit_test_result)
        elif context & WebKit.HitTestResultContext.IMAGE:
            self._build_image_context_menu(context_menu, hit_test_result)
        elif context & WebKit.HitTestResultContext.MEDIA:
            self._build_media_context_menu(context_menu, hit_test_result)
        elif context & WebKit.HitTestResultContext.SELECTION:
            self._build_text_selection_context_menu(context_menu, hit_test_result)
        else:
            self._build_default_context_menu(context_menu, hit_test_result)
        
        return False  # Allow the menu to be shown

    def _build_link_context_menu(self, context_menu, hit_test_result):
        """Build context menu for links."""
        link_uri = hit_test_result.get_link_uri()
        link_text = hit_test_result.get_link_title() or link_uri
        
        # Open Link
        open_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.OPEN_LINK)
        context_menu.append(open_item)
        
        # Open Link in New Tab
        new_tab_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.OPEN_LINK_IN_NEW_WINDOW)
        new_tab_item.set_label("Open Link in New Tab")
        context_menu.append(new_tab_item)
        
        # Copy Link URL
        copy_link_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.COPY_LINK_TO_CLIPBOARD)
        context_menu.append(copy_link_item)
        
        # Add separator
        context_menu.append(WebKit.ContextMenuItem.new_separator())
        
        # Add standard page actions
        self._add_standard_page_actions(context_menu)

    def _build_image_context_menu(self, context_menu, hit_test_result):
        """Build context menu for images."""
        image_uri = hit_test_result.get_image_uri()
        
        # Open Image in New Tab
        open_image_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.OPEN_IMAGE_IN_NEW_WINDOW)
        open_image_item.set_label("Open Image in New Tab")
        context_menu.append(open_image_item)
        
        # Save Image
        save_image_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.DOWNLOAD_IMAGE_TO_DISK)
        context_menu.append(save_image_item)
        
        # Copy Image
        copy_image_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.COPY_IMAGE_TO_CLIPBOARD)
        context_menu.append(copy_image_item)
        
        # Copy Image URL
        copy_image_url_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.COPY_IMAGE_URL_TO_CLIPBOARD)
        context_menu.append(copy_image_url_item)
        
        # Add separator
        context_menu.append(WebKit.ContextMenuItem.new_separator())
        
        # Add standard page actions
        self._add_standard_page_actions(context_menu)

    def _build_media_context_menu(self, context_menu, hit_test_result):
        """Build context menu for audio/video elements."""
        media_uri = hit_test_result.get_media_uri()
        
        # Play/Pause (context dependent)
        play_pause_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.MEDIA_PLAY)
        context_menu.append(play_pause_item)
        
        # Mute/Unmute
        mute_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.MEDIA_MUTE)
        context_menu.append(mute_item)
        
        # Save Media
        save_media_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.DOWNLOAD_MEDIA_TO_DISK)
        context_menu.append(save_media_item)
        
        # Copy Media URL
        copy_media_url_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.COPY_MEDIA_LINK_TO_CLIPBOARD)
        context_menu.append(copy_media_url_item)
        
        # Add separator
        context_menu.append(WebKit.ContextMenuItem.new_separator())
        
        # Add standard page actions
        self._add_standard_page_actions(context_menu)

    def _build_text_selection_context_menu(self, context_menu, hit_test_result):
        """Build context menu for text selection."""
        # Copy Selection
        copy_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.COPY)
        context_menu.append(copy_item)
        
        # Search Web for Selection - using custom action
        search_item = WebKit.ContextMenuItem.new("Search for Selection", WebKit.ContextMenuAction.CUSTOM)
        search_item.connect("activate", self._on_search_selection_activate)
        context_menu.append(search_item)
        
        # Print Selection
        print_selection_item = WebKit.ContextMenuItem.new("Print Selection", WebKit.ContextMenuAction.CUSTOM)
        print_selection_item.connect("activate", self._on_print_selection_activate)
        context_menu.append(print_selection_item)
        
        # Add separator
        context_menu.append(WebKit.ContextMenuItem.new_separator())
        
        # Add standard page actions
        self._add_standard_page_actions(context_menu)

    def _build_default_context_menu(self, context_menu, hit_test_result):
        """Build default context menu for regular page areas."""
        self._add_standard_page_actions(context_menu)

    def _add_standard_page_actions(self, context_menu):
        """Add standard navigation actions to any context menu."""
        # Back
        if self.webview.can_go_back():
            back_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.GO_BACK)
            context_menu.append(back_item)
        
        # Forward
        if self.webview.can_go_forward():
            forward_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.GO_FORWARD)
            context_menu.append(forward_item)
        
        # Reload
        reload_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.RELOAD)
        context_menu.append(reload_item)
        
        # Add separator if we added navigation items
        if self.webview.can_go_back() or self.webview.can_go_forward():
            context_menu.append(WebKit.ContextMenuItem.new_separator())
        
        # View Page Source
        view_source_item = WebKit.ContextMenuItem.new("View Page Source", WebKit.ContextMenuAction.CUSTOM)
        view_source_item.connect("activate", self._on_view_source_activate)
        context_menu.append(view_source_item)
        
        # Inspect Element (if developer mode is enabled)
        if self.webview.get_settings().get_enable_developer_extras():
            inspect_item = WebKit.ContextMenuItem.new_from_stock_action(WebKit.ContextMenuAction.INSPECT_ELEMENT)
            context_menu.append(inspect_item)

    def _on_search_selection_activate(self, menu_item):
        """Handle search for selected text."""
        # Get the selected text using JavaScript
        self.webview.run_javascript("window.getSelection().toString();", None, self._on_get_selection_result, None)

    def _on_get_selection_result(self, webview, result, user_data):
        """Handle the result of getting selected text."""
        try:
            js_result = webview.run_javascript_finish(result)
            if js_result:
                selected_text = js_result.get_js_value().to_string()
                if selected_text and selected_text.strip():
                    # Create search URL using the default search engine
                    app = Gio.Application.get_default()
                    search_url = app._get_selected_search_engine_url(selected_text.strip())
                    # Signal to open in new tab
                    self.emit("show-notification", f"Searching for: {selected_text[:50]}...")
                    debug_print(f"[DEBUG] Search selection: {selected_text} -> {search_url}")
                    # This would need to be handled by the window to open a new tab
                else:
                    self.emit("show-notification", "No text selected")
        except Exception as e:
            debug_print(f"[DEBUG] Error getting selection: {e}")
            self.emit("show-notification", "Error getting selected text")

    def _on_view_source_activate(self, menu_item):
        """Handle view page source action."""
        current_uri = self.get_uri()
        if current_uri:
            # Get the page source using JavaScript and display it
            self.webview.run_javascript("document.documentElement.outerHTML;", None, self._on_get_source_result, current_uri)

    def _on_get_source_result(self, webview, result, user_data):
        """Handle the result of getting page source."""
        try:
            js_result = webview.run_javascript_finish(result)
            if js_result:
                page_source = js_result.get_js_value().to_string()
                original_uri = user_data
                
                # Create a data URI with the source code
                import base64
                import urllib.parse
                
                # Create HTML wrapper for the source code
                wrapped_source = f"""<!DOCTYPE html>
<html>
<head>
    <title>Source: {original_uri}</title>
    <style>
        body {{ font-family: monospace; white-space: pre-wrap; margin: 20px; }}
        .source {{ background: #f5f5f5; padding: 20px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h2>Page Source: {original_uri}</h2>
    <div class="source">{page_source.replace('<', '&lt;').replace('>', '&gt;')}</div>
</body>
</html>"""
                
                # Convert to data URI
                encoded_source = base64.b64encode(wrapped_source.encode('utf-8')).decode('ascii')
                data_uri = f"data:text/html;base64,{encoded_source}"
                
                # This would signal to open in a new tab - for now just show notification
                debug_print(f"[DEBUG] View source requested for: {original_uri}")
                self.emit("show-notification", "View source functionality implemented")
        except Exception as e:
            debug_print(f"[DEBUG] Error getting page source: {e}")
            self.emit("show-notification", "Error getting page source")

    def _on_print_selection_activate(self, menu_item):
        """Handle print selection from context menu."""
        self.print_page(print_selection_only=True)

    def _detect_opensearch_descriptors(self):
        """Detect OpenSearch descriptors on the current page."""
        if not self._opensearch_parser_instance:
            return
        
        # Check if webview is properly initialized
        if not self.webview or not hasattr(self.webview, 'run_javascript'):
            debug_print("[DEBUG] WebView not ready for JavaScript execution")
            return
        
        # JavaScript to find OpenSearch descriptors
        javascript_code = """
        (function() {
            var links = document.getElementsByTagName('link');
            var openSearchLinks = [];
            
            for (var i = 0; i < links.length; i++) {
                var link = links[i];
                var rel = link.getAttribute('rel');
                var type = link.getAttribute('type');
                var href = link.getAttribute('href');
                
                if (rel && type && href) {
                    if (rel.toLowerCase() === 'search' && 
                        type.toLowerCase() === 'application/opensearchdescription+xml') {
                        
                        // Convert relative URLs to absolute
                        var absoluteHref = href;
                        if (!href.startsWith('http://') && !href.startsWith('https://')) {
                            absoluteHref = new URL(href, window.location.href).href;
                        }
                        
                        openSearchLinks.push({
                            title: link.getAttribute('title') || document.title || 'Unknown',
                            href: absoluteHref
                        });
                    }
                }
            }
            
            return openSearchLinks;
        })();
        """
        
        # Execute JavaScript and handle results
        self.webview.run_javascript(javascript_code, None, self._on_opensearch_discovery_complete, None)
    
    def _on_opensearch_discovery_complete(self, webview, result, user_data):
        """Handle OpenSearch discovery results."""
        try:
            js_result = webview.run_javascript_finish(result)
            if js_result:
                value = js_result.get_js_value()
                if value and value.is_array():
                    # Process each OpenSearch descriptor found
                    for i in range(value.get_array_length()):
                        item = value.get_array_element(i)
                        if item and item.is_object():
                            title = item.get_property('title').to_string() if item.has_property('title') else 'Unknown'
                            href = item.get_property('href').to_string() if item.has_property('href') else ''
                            
                            if href:
                                debug_print(f"[DEBUG] Found OpenSearch descriptor: {title} at {href}")
                                # Emit signal with the title and URL
                                self.emit("opensearch-discovered", title, href)
        except Exception as e:
            debug_print(f"[DEBUG] Error processing OpenSearch discovery: {e}")


class SeoltoirPrintManager:
    """Comprehensive print management for Seoltoir browser."""
    
    def __init__(self, webview, parent_window):
        self.webview = webview
        self.parent_window = parent_window
        self.page_setup = None
        self.print_settings = None
        self._init_print_settings()
    
    def _init_print_settings(self):
        """Initialize default print settings."""
        self.page_setup = Gtk.PageSetup.new()
        self.print_settings = Gtk.PrintSettings.new()
        
        # Set default settings
        self.print_settings.set_orientation(Gtk.PageOrientation.PORTRAIT)
        self.print_settings.set_paper_size(Gtk.PaperSize.new(None))  # Default paper size
        self.print_settings.set_scale(100.0)  # 100% scale
        
        # Set default margins (in points - 72 points = 1 inch)
        self.page_setup.set_top_margin(72.0, Gtk.Unit.POINTS)     # 1 inch
        self.page_setup.set_bottom_margin(72.0, Gtk.Unit.POINTS)  # 1 inch  
        self.page_setup.set_left_margin(72.0, Gtk.Unit.POINTS)    # 1 inch
        self.page_setup.set_right_margin(72.0, Gtk.Unit.POINTS)   # 1 inch
    
    def show_print_dialog(self):
        """Show the main print dialog with preview."""
        print_operation = Gtk.PrintOperation.new()
        
        # Set up print operation properties
        print_operation.set_print_settings(self.print_settings)
        print_operation.set_default_page_setup(self.page_setup)
        print_operation.set_use_full_page(False)
        print_operation.set_unit(Gtk.Unit.POINTS)
        print_operation.set_embed_page_setup(True)
        print_operation.set_show_progress(True)
        
        # Set job name
        current_uri = self.webview.get_uri()
        if current_uri:
            title = self.webview.get_title() or current_uri
            print_operation.set_job_name(f"Seoltoir - {title}")
        else:
            print_operation.set_job_name("Seoltoir - Web Page")
        
        # Connect signals
        print_operation.connect("begin-print", self._on_begin_print)
        print_operation.connect("draw-page", self._on_draw_page)
        print_operation.connect("status-changed", self._on_print_status_changed)
        print_operation.connect("done", self._on_print_done)
        
        # Inject print CSS before printing
        self._inject_print_css()
        
        try:
            result = print_operation.run(Gtk.PrintOperationAction.PRINT_DIALOG, self.parent_window)
            if result == Gtk.PrintOperationResult.ERROR:
                debug_print("[DEBUG] Print operation failed")
        except Exception as e:
            debug_print(f"[DEBUG] Print operation error: {e}")
    
    def show_page_setup_dialog(self):
        """Show page setup configuration dialog."""
        new_page_setup = Gtk.print_run_page_setup_dialog(
            self.parent_window, 
            self.page_setup, 
            self.print_settings
        )
        if new_page_setup:
            self.page_setup = new_page_setup
            debug_print("[DEBUG] Page setup updated")
    
    def print_to_pdf(self, file_path=None):
        """Export the current page to PDF."""
        if not file_path:
            dialog = Gtk.FileChooserNative.new(
                "Export to PDF",
                self.parent_window,
                Gtk.FileChooserAction.SAVE,
                "_Save",
                "_Cancel"
            )
            
            # Set up PDF filter
            filter_pdf = Gtk.FileFilter.new()
            filter_pdf.set_name("PDF Files")
            filter_pdf.add_mime_type("application/pdf")
            filter_pdf.add_pattern("*.pdf")
            dialog.add_filter(filter_pdf)
            
            # Set default filename
            current_uri = self.webview.get_uri()
            if current_uri:
                title = self.webview.get_title() or "webpage"
                # Clean title for filename
                import re
                clean_title = re.sub(r'[^\w\s-]', '', title).strip()[:50]
                dialog.set_current_name(f"{clean_title}.pdf")
            else:
                dialog.set_current_name("webpage.pdf")
            
            response = dialog.run()
            if response == Gtk.ResponseType.ACCEPT:
                file_path = dialog.get_filename()
                dialog.destroy()
            else:
                dialog.destroy()
                return
        
        if file_path:
            # Set up print operation for PDF export
            print_operation = Gtk.PrintOperation.new()
            print_operation.set_print_settings(self.print_settings)
            print_operation.set_default_page_setup(self.page_setup)
            print_operation.set_export_filename(file_path)
            
            # Set job name
            print_operation.set_job_name("Seoltoir PDF Export")
            
            # Connect signals
            print_operation.connect("begin-print", self._on_begin_print)
            print_operation.connect("draw-page", self._on_draw_page)
            
            # Inject print CSS
            self._inject_print_css()
            
            try:
                result = print_operation.run(Gtk.PrintOperationAction.EXPORT, self.parent_window)
                if result == Gtk.PrintOperationResult.APPLY:
                    debug_print(f"[DEBUG] PDF exported successfully to {file_path}")
                else:
                    debug_print(f"[DEBUG] PDF export failed")
            except Exception as e:
                debug_print(f"[DEBUG] PDF export error: {e}")
    
    def print_selection(self, selected_text):
        """Print only the selected text."""
        # Create a temporary HTML document with just the selected text
        selection_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Selected Text</title>
            <style>
                @media print {{
                    body {{ font-family: serif; font-size: 12pt; line-height: 1.4; }}
                    .selection {{ margin: 20px; }}
                }}
            </style>
        </head>
        <body>
            <div class="selection">
                <h3>Selected Text</h3>
                <p>{selected_text.replace('<', '&lt;').replace('>', '&gt;').replace('\n', '<br>')}</p>
            </div>
        </body>
        </html>
        """
        
        # Store original content and load selection
        self._original_content = self.webview.get_uri()
        
        # Create data URI for selection
        import base64
        encoded_html = base64.b64encode(selection_html.encode('utf-8')).decode('ascii')
        data_uri = f"data:text/html;base64,{encoded_html}"
        
        # Load selection content temporarily
        self.webview.load_uri(data_uri)
        
        # Wait a moment for content to load, then print
        GLib.timeout_add(500, self._print_selection_after_load)
    
    def _print_selection_after_load(self):
        """Print selection after content loads."""
        self.show_print_dialog()
        
        # Restore original content after printing
        if hasattr(self, '_original_content') and self._original_content:
            GLib.timeout_add(1000, lambda: self.webview.load_uri(self._original_content))
        
        return False  # Don't repeat timeout
    
    def _inject_print_css(self):
        """Inject custom CSS for print media."""
        # Get current page info for headers/footers
        current_uri = self.webview.get_uri() or ""
        page_title = self.webview.get_title() or "Web Page"
        
        print_css = f"""
        @media print {{
            /* Page setup with headers and footers */
            @page {{
                margin: 1in 1in 1.2in 1in;
                
                @top-left {{
                    content: "Seoltoir Browser";
                    font-size: 10pt;
                    color: #666;
                }}
                
                @top-center {{
                    content: "{page_title[:50]}";
                    font-size: 10pt;
                    font-weight: bold;
                    color: #000;
                }}
                
                @top-right {{
                    content: "Page " counter(page);
                    font-size: 10pt;
                    color: #666;
                }}
                
                @bottom-left {{
                    content: "{current_uri[:60]}";
                    font-size: 9pt;
                    color: #999;
                }}
                
                @bottom-center {{
                    content: "";
                }}
                
                @bottom-right {{
                    content: "Printed on " date();
                    font-size: 9pt;
                    color: #999;
                }}
            }}
            
            /* Hide navigation and UI elements */
            nav, .navigation, .nav, .menu, .sidebar, .ads, .advertisement,
            .social-share, .comments, .related-posts, header.site-header,
            footer.site-footer, .site-footer, .header, .footer,
            .print-hidden, [class*="ad-"], [id*="ad-"], [class*="social"],
            .popup, .modal, .overlay, .fixed-header, .sticky-header {{
                display: none !important;
            }}
            
            /* Optimize content for print */
            body {{
                font-size: 12pt !important;
                line-height: 1.4 !important;
                color: #000 !important;
                background: #fff !important;
                margin: 0 !important;
                padding: 0 !important;
            }}
            
            /* Ensure content fits on page */
            .content, .main-content, .article, .post, .entry-content {{
                max-width: 100% !important;
                margin: 0 !important;
                padding: 10pt !important;
            }}
            
            /* Style headings for print */
            h1, h2, h3, h4, h5, h6 {{
                color: #000 !important;
                page-break-after: avoid !important;
                margin-top: 12pt !important;
                margin-bottom: 6pt !important;
            }}
            
            h1 {{
                font-size: 18pt !important;
                border-bottom: 2pt solid #000 !important;
                padding-bottom: 3pt !important;
            }}
            
            h2 {{
                font-size: 16pt !important;
                border-bottom: 1pt solid #666 !important;
                padding-bottom: 2pt !important;
            }}
            
            /* Handle images */
            img {{
                max-width: 100% !important;
                height: auto !important;
                page-break-inside: avoid !important;
                border: 1px solid #ddd !important;
                margin: 5pt 0 !important;
            }}
            
            /* Handle links */
            a {{
                color: #000 !important;
                text-decoration: underline !important;
            }}
            
            /* Add URL after links */
            a[href]:after {{
                content: " (" attr(href) ")";
                font-size: 9pt;
                color: #666;
                font-weight: normal;
            }}
            
            /* Page breaks */
            .page-break {{
                page-break-before: always !important;
            }}
            
            /* Avoid page breaks inside elements */
            .avoid-page-break {{
                page-break-inside: avoid !important;
            }}
            
            /* Tables */
            table {{
                border-collapse: collapse !important;
                width: 100% !important;
                margin: 10pt 0 !important;
                page-break-inside: avoid !important;
            }}
            
            th, td {{
                border: 1px solid #000 !important;
                padding: 4pt !important;
                font-size: 10pt !important;
                text-align: left !important;
            }}
            
            th {{
                background: #f0f0f0 !important;
                font-weight: bold !important;
            }}
            
            /* Code blocks */
            pre, code {{
                font-family: "Courier New", monospace !important;
                font-size: 10pt !important;
                background: #f8f8f8 !important;
                border: 1px solid #ccc !important;
                padding: 4pt !important;
                page-break-inside: avoid !important;
                overflow: hidden !important;
                word-wrap: break-word !important;
            }}
            
            /* Lists */
            ul, ol {{
                margin: 6pt 0 !important;
                padding-left: 20pt !important;
            }}
            
            li {{
                margin: 2pt 0 !important;
            }}
            
            /* Blockquotes */
            blockquote {{
                margin: 10pt 20pt !important;
                padding: 5pt 10pt !important;
                border-left: 3pt solid #ccc !important;
                background: #f9f9f9 !important;
                font-style: italic !important;
            }}
            
            /* Print-specific elements */
            .print-only {{
                display: block !important;
            }}
            
            .screen-only {{
                display: none !important;
            }}
            
            /* Page numbering */
            .page-number:after {{
                content: counter(page);
            }}
            
            /* Ensure text is readable */
            * {{
                -webkit-print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}
        }}
        """
        
        # Create and inject the print CSS
        css_script = f"""
        var printStyle = document.getElementById('seoltoir-print-css');
        if (printStyle) printStyle.remove();
        
        var style = document.createElement('style');
        style.id = 'seoltoir-print-css';
        style.innerHTML = `{print_css}`;
        document.head.appendChild(style);
        """
        
        self.webview.run_javascript(css_script, None, None, None)
    
    def _on_begin_print(self, operation, context):
        """Called when print operation begins."""
        # Set number of pages - for web content, we typically have 1 page
        # WebKit will handle pagination internally
        operation.set_n_pages(1)
        debug_print("[DEBUG] Print operation began")
    
    def _on_draw_page(self, operation, context, page_num):
        """Called to draw each page."""
        # WebKit handles the actual drawing through its print operation
        # This is mostly for compatibility with GTK print framework
        debug_print(f"[DEBUG] Drawing page {page_num}")
    
    def _on_print_status_changed(self, operation):
        """Called when print status changes."""
        status = operation.get_status()
        debug_print(f"[DEBUG] Print status: {status}")
    
    def _on_print_done(self, operation, result):
        """Called when print operation is complete."""
        if result == Gtk.PrintOperationResult.APPLY:
            debug_print("[DEBUG] Print completed successfully")
        elif result == Gtk.PrintOperationResult.CANCEL:
            debug_print("[DEBUG] Print cancelled")
        elif result == Gtk.PrintOperationResult.ERROR:
            debug_print("[DEBUG] Print failed with error")
        else:
            debug_print(f"[DEBUG] Print completed with result: {result}")
