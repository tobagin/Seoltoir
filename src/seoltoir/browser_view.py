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
    }

    _adblock_parser_instance = None
    _https_everywhere_rules_instance = None
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
            self.webview = GObject.new(WebKit.WebView, network_session=ephemeral_session)
            self.network_session = ephemeral_session
        else:
            if hasattr(WebKit.WebView, 'new_with_context'):
                self.webview = WebKit.WebView.new_with_context(self.context)
            else:
        self.webview = WebKit.WebView.new()
        self.webview.set_vexpand(True)
        self.webview.set_hexpand(True)
        self.append(self.webview)

        #self._setup_signals_and_properties()
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

        self.settings.connect("changed::default-font-family", self._on_font_setting_changed)
        self.settings.connect("changed::default-font-size", self._on_font_setting_changed)

        self.settings = Gio.Settings.new(Gio.Application.get_default().get_application_id())
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
        # --- CHANGED: Connect to the new signals for the WebView ---
        self.webview.connect("load-changed", self._on_load_changed)
        debug_print("[DEBUG] Connected load-changed signal to _on_load_changed")
        self.webview.connect("resource-load-started", self._on_resource_load_started)

        # --- Adblock Plus signals ---
        if self._adblock_parser_instance:
            self._adblock_parser_instance.connect("blocked", self._on_adblock_blocked)

        # --- Inject favicon extractor ---
        self._inject_favicon_extractor()

    def _inject_favicon_extractor(self):
        """Inject JavaScript to extract favicon URLs from the page."""
        favicon_script = """
        (function() {
            function findFavicon() {
                const links = document.querySelectorAll('link[rel*="icon"]');
                const favicons = [];
                
                for (let link of links) {
                    const href = link.href;
                    const rel = link.rel;
                    const sizes = link.sizes ? link.sizes.value : '';
                    
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
                // Emit the favicon URL to the Python side
                window.webkit.messageHandlers.faviconHandler.postMessage(favicons[0].url);
            }
        })();
        """
        
        # Create a user script to inject the favicon extractor
        script = WebKit.UserScript.new(
            favicon_script,
            WebKit.UserContentInjectedFrames.ALL_FRAMES,
            WebKit.UserScriptInjectionTime.DOCUMENT_END,
            None,
            None
        )
        
        # Add the script to the user content manager
        self.user_content_manager.add_script(script, "favicon-extractor")
        
        # Register a message handler to receive the favicon URL
        self.user_content_manager.register_script_message_handler("faviconHandler", self._on_favicon_message_received)

    def _on_adblock_blocked(self, parser, uri, options):
        self.blocked_count_for_page += 1
        self.emit("blocked-count-changed", self.blocked_count_for_page)
        self.emit("show-notification", f"Blocked by Adblock Plus: {os.path.basename(urllib.parse.urlparse(uri).path or uri)}")

    def _on_load_changed(self, webview, load_event):
        debug_print(f"[DEBUG] _on_load_changed called with event: {load_event}")
        if load_event == WebKit.LoadEvent.COMMITTED:
            # Reset blocked count on new page load
            self.blocked_count_for_page = 0

            # --- CHANGED: Reapply content blocking on every page load ---
            SeoltoirBrowserView.apply_ad_block_filter(self.user_content_manager, self.settings.get_boolean("enable-ad-blocking"))

            # --- HTTPS Everywhere rules re-application ---
            if self._https_everywhere_rules_instance:
                for rule in self._https_everywhere_rules_instance.get_rules():
                    self.webview.add_https_everywhere_rule(rule)
        
        elif load_event == WebKit.LoadEvent.FINISHED:
            # Page has finished loading, emit signals for title, URI, and favicon
            uri = self.webview.get_uri()
            title = self.webview.get_title()
            favicon = self.webview.get_favicon()
            debug_print(f"[DEBUG] FINISHED: uri={uri}, title={title}, favicon={favicon} (type: {type(favicon)})")
            self.emit("uri-changed", uri)
            self.emit("title-changed", title)
            if favicon:
                self.emit("favicon-changed", favicon)
            else:
                debug_print("[DEBUG] No favicon available after page load.")
                # Try to fetch favicon from domain root as fallback
                self._fetch_favicon_fallback(uri)
            self.emit("can-go-back-changed", self.webview.can_go_back())
            self.emit("can-go-forward-changed", self.webview.can_go_forward())

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

    def _on_favicon_message_received(self, webview, message, data):
        """Handle the received favicon URL and fetch the favicon."""
        favicon_url = data
        debug_print(f"[DEBUG] Received favicon URL: {favicon_url}")
        
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
                    icon_bytes = GLib.Bytes.new(icon_data)
                    icon = Gio.BytesIcon.new(icon_bytes)
                    
                    GLib.idle_add(self.emit, "favicon-changed", icon)
                    debug_print(f"[DEBUG] Successfully fetched favicon from {favicon_url} (raw)")
                    
                except Exception as e:
                    debug_print(f"[DEBUG] Failed to fetch favicon from {favicon_url}: {e}")
                    # Emit signal to revert to default icon
                    GLib.idle_add(self.emit, "favicon-changed", None)
                    
            except Exception as e:
                debug_print(f"[DEBUG] Failed to fetch/convert favicon from {favicon_url}: {e}")
                # Emit signal to revert to default icon
                GLib.idle_add(self.emit, "favicon-changed", None)
        
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
                        icon_bytes = GLib.Bytes.new(icon_data)
                        icon = Gio.BytesIcon.new(icon_bytes)
                        
                        GLib.idle_add(self.emit, "favicon-changed", icon)
                        debug_print(f"[DEBUG] Successfully fetched favicon from {favicon_url} (raw)")
                        
                    except Exception as e:
                        debug_print(f"[DEBUG] Failed to fetch favicon from {favicon_url}: {e}")
                        # Emit signal to revert to default icon
                        GLib.idle_add(self.emit, "favicon-changed", None)
                        
                except Exception as e:
                    debug_print(f"[DEBUG] Failed to fetch/convert favicon from {favicon_url}: {e}")
                    # Emit signal to revert to default icon
                    GLib.idle_add(self.emit, "favicon-changed", None)
            
            # Start the favicon fetch in a background thread
            import threading
            threading.Thread(target=fetch_favicon, daemon=True).start()
            
        except Exception as e:
            debug_print(f"[DEBUG] Error in favicon fallback for {uri}: {e}")
            # Emit signal to revert to default icon
            GLib.idle_add(self.emit, "favicon-changed", None)