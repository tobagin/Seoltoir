import json
import re
from abp.filters import parse_line

class AdblockParser:
    """
    Parses Adblock Plus-like rules using the python-abp library
    and converts them into WebKit.UserContentFilter JSON format
    and CSS for element hiding.
    """

    def __init__(self):
        self.url_filters = [] # Stores filters for URL blocking
        self.css_rules = {}   # Stores CSS rules per domain
        self.exception_filters = [] # Stores exception rules

    def parse_rules_from_string(self, rules_string: str):
        """Parses a string containing multiple ABP rules."""
        for line in rules_string.splitlines():
            self.parse_rule(line)

    def parse_rules_from_file(self, file_path: str):
        """Parses rules from a file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    self.parse_rule(line)
        except FileNotFoundError:
            print(f"Adblock filter list not found: {file_path}")
        except Exception as e:
            print(f"Error reading or parsing {file_path}: {e}")

    def parse_rule(self, rule_text: str):
        """Parses a single ABP rule."""
        rule_text = rule_text.strip()
        if not rule_text or rule_text.startswith("!"): # Ignore comments
            return

        try:
            abp_filter = parse_line(rule_text)
            
            if abp_filter.is_exception:
                self.exception_filters.append(abp_filter)
            elif abp_filter.is_elemhide:
                # Element hiding rules are stored as CSS
                # python-abp's Filter object has .selector and .domains
                # Domains can be empty for global rules.
                domains = abp_filter.domains
                if not domains:
                    domains = ["*"] # Global rule
                
                for domain in domains:
                    if domain not in self.css_rules:
                        self.css_rules[domain] = []
                    self.css_rules[domain].append(abp_filter.selector)
            else:
                # Regular URL blocking rules
                self.url_filters.append(abp_filter)

        except Exception as e:
            # print(f"Warning: Could not parse rule '{rule_text}': {e}")
            pass # Silently ignore unparsable rules for now

    def _convert_abp_regex_to_js_regex(self, abp_regex_pattern: str) -> str:
        """
        Converts a simplified ABP regex pattern (e.g., from `Filter.pattern`)
        into a JavaScript-compatible regex string.
        This is a *very* simplified conversion and might not cover all edge cases
        handled by WebKit's internal content filtering.
        """
        # Escape characters that have special meaning in JS regex
        js_regex = re.escape(abp_regex_pattern)
        
        # FIX: Remove invalid escape sequences (e.g., \/ becomes /)
        # Using raw string r'' for regex patterns helps with backslashes.
        # This conversion is still highly simplified for WebKit content filters.
        js_regex = js_regex.replace(r'\*', '.*') # * -> .*
        # Re-evaluate ||domain^ -> regex for domain start. Simpler `.*` at start.
        js_regex = js_regex.replace(r'\|\|', r'^(?:https?|ftp)://(?:[^/]+\.)*') # ||domain^ -> regex for domain start (fixed \)
        js_regex = js_regex.replace(r'\^', r'(?:/|\?|&|$|\b)') # ^ -> delimiter (/, ?, &, $, word boundary) (fixed \)
        js_regex = js_regex.replace(r'\|', '(?:^|$)') # | -> start/end of string (simplified)
        
        return js_regex


    def get_webkit_content_filter_json(self) -> str:
        """
        Returns the JSON string for WebKit.UserContentFilter.
        This focuses on URL blocking rules.
        """
        webkit_rules = []
        
        for abp_filter in self.url_filters:
            js_regex_pattern = self._convert_abp_regex_to_js_regex(abp_filter.pattern)

            webkit_rules.append({
                "trigger": {
                    "url-filter": js_regex_pattern
                },
                "action": {
                    "type": "block"
                }
            })
            
        # Exception rules are handled by should_block_url at runtime, not typically in ContentFilter JSON directly.
        # Removing "type": "ignore-and-load" as it's not a valid ContentFilter action.

        return json.dumps(webkit_rules)

    def get_webkit_css_user_scripts(self) -> dict:
        """
        Returns a dictionary of CSS UserScripts, keyed by domain.
        { "domain": "css_string" }
        These CSS strings are intended to be injected as WebKit.UserScript.
        """
        scripts = {}
        for domain, selectors in self.css_rules.items():
            css_string = " ".join(f"{s} {{ display: none !important; }}" for s in selectors)
            scripts[domain] = css_string
        return scripts

    def should_block_url(self, url: str, options: dict = None) -> bool:
        """
        Checks if a given URL should be blocked based on the parsed rules.
        Uses python-abp's internal matching logic, which includes exceptions.
        `options` can contain 'domain', 'doc_domain', 'third_party', 'elemhide_attrs', etc.
        """
        if options is None: # FIX: Changed `if options === None` to `if options is None`
            options = {}

        # Check against regular blocking filters
        for abp_filter in self.url_filters:
            if abp_filter.matches(url, options=options):
                # Now check against exception filters
                is_exception = False
                for exc_filter in self.exception_filters:
                    if exc_filter.matches(url, options=options):
                        is_exception = True
                        break
                if not is_exception:
                    return True # Should be blocked
        return False

# --- Example Usage (for testing the parser) ---
if __name__ == '__main__':
    parser = AdblockParser()
    
    test_rules = """
! Comment
||example.com^
||doubleclick.net^
/ads/banner.gif
! Element hiding rules
##div.ad-container
facebook.com##.fb_ad
! Exception rule
@@||example.com/allowme.gif^
    """
    
    parser.parse_rules_from_string(test_rules)
    
    print("--- WebKit Content Filter JSON ---")
    print(parser.get_webkit_content_filter_json())
    
    print("\n--- WebKit CSS User Scripts ---")
    for domain, css in parser.get_webkit_css_user_scripts().items():
        print(f"Domain: {domain}\nCSS:\n{css}\n---")

    print("\n--- Testing should_block_url ---")
    print(f"Should block https://example.com/ads/banner.gif? {parser.should_block_url('https://example.com/ads/banner.gif', options={'domain': 'example.com'})}")
    print(f"Should block https://doubleclick.net/tracker.js? {parser.should_block_url('https://doubleclick.net/tracker.js', options={'domain': 'some-site.com', 'third_party': True})}")
    print(f"Should block https://example.com/allowme.gif? {parser.should_block_url('https://example.com/allowme.gif', options={'domain': 'example.com'})}") # Should be False due to exception
    print(f"Should block https://some-other-site.com/image.png? {parser.should_block_url('https://some-other-site.com/image.png')}") # Should be False
