# seoltoir/seoltoir/https_everywhere_rules.py

import xml.etree.ElementTree as ET
import re

class HttpsEverywhereRules:
    """
    A simplified parser for HTTPS Everywhere rulesets.
    Focuses on `rule` and `exclusion` tags with `from` and `to` attributes.
    Does NOT support: `target`, `securecookie`, `redirection`, `test` tags,
    or advanced regex features beyond basic wildcard conversion.
    """
    def __init__(self):
        self.rules = [] # List of {'from': regex_pattern, 'to': replace_pattern}
        self.exclusions = [] # List of regex_pattern for exclusions

    def parse_rules_from_string(self, xml_string: str):
        try:
            root = ET.fromstring(xml_string)
            self._parse_element(root)
        except ET.ParseError as e:
            print(f"Error parsing HTTPS Everywhere XML string: {e}")

    def parse_rules_from_file(self, file_path: str):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            self._parse_element(root)
        except FileNotFoundError:
            print(f"HTTPS Everywhere ruleset not found: {file_path}")
        except ET.ParseError as e:
            print(f"Error parsing HTTPS Everywhere XML file '{file_path}': {e}")
        except Exception as e:
            print(f"General error reading HTTPS Everywhere rules: {e}")

    def _parse_element(self, element):
        """Recursively parses elements for rules and exclusions."""
        for child in element:
            if child.tag == 'rule':
                from_attr = child.get('from')
                to_attr = child.get('to')
                if from_attr and to_attr:
                    try:
                        # Convert simple wildcards to regex
                        # This is a highly simplified regex conversion
                        regex_from = from_attr.replace('*', '.*')
                        # Ensure it's anchored if it looks like a full URL match
                        if not regex_from.startswith('^'): regex_from = '^' + regex_from
                        if not regex_from.endswith('$'): regex_from = regex_from + '$'
                        self.rules.append({'from_regex': re.compile(regex_from), 'to': to_attr})
                    except re.error as e:
                        print(f"Invalid regex in HTTPS Everywhere rule 'from={from_attr}': {e}")
            elif child.tag == 'exclusion':
                pattern = child.get('pattern')
                if pattern:
                    try:
                        regex_pattern = pattern.replace('*', '.*')
                        if not regex_pattern.startswith('^'): regex_pattern = '^' + regex_pattern
                        if not regex_pattern.endswith('$'): regex_pattern = regex_pattern + '$'
                        self.exclusions.append(re.compile(regex_pattern))
                    except re.error as e:
                        print(f"Invalid regex in HTTPS Everywhere exclusion 'pattern={pattern}': {e}")
            # Recursively parse nested elements like `<ruleset>`
            self._parse_element(child)

    def rewrite_uri(self, uri: str) -> str:
        """
        Attempts to rewrite a URI to HTTPS based on the parsed rules.
        Returns the rewritten URI or the original if no match/excluded.
        """
        if not uri.startswith("http://"):
            return uri # Only rewrite HTTP URIs

        # Check for exclusions first
        for exclusion_regex in self.exclusions:
            if exclusion_regex.search(uri):
                # print(f"HTTPS Everywhere: Excluded {uri}")
                return uri # Do not rewrite if excluded

        # Apply rules
        for rule in self.rules:
            match = rule['from_regex'].search(uri)
            if match:
                # Replace the matched part. `re.sub` is useful here.
                # Simplistic: just replace the whole URI if the pattern matches.
                # A proper implementation would use `re.sub` with groups for `to`
                # attribute's backreferences.
                rewritten_uri = re.sub(rule['from_regex'], rule['to'], uri)
                # Ensure it starts with https if it was http originally and pattern doesn't specify
                if rewritten_uri.startswith("http://") and rewritten_uri.startswith("https://"):
                     return rewritten_uri # Already https in rule
                elif rewritten_uri.startswith("http://"): # Still http, try to force
                     return rewritten_uri.replace("http://", "https://", 1)
                elif not rewritten_uri.startswith("https://") and not rewritten_uri.startswith("http://"):
                    # If `to` attribute is just a path, prepend `https://`
                    return "https://" + rewritten_uri
                else:
                    return rewritten_uri
        return uri # No rule matched

# Example Usage (for testing the parser)
if __name__ == '__main__':
    # A tiny mock ruleset XML (from a real HTTPS Everywhere rule)
    test_xml = """
    <ruleset name="Example.com (partial)">
      <rule from="^http://(www\.)?example\.com/" to="https://$1example.com/"/>
      <rule from="^http://sub\.example\.org/" to="https://secure.example.org/"/>
      <exclusion pattern="^http://blog\.example\.com/"/>
      <rule from="^http://insecure\.test\.com/" to="https://insecure.test.com/"/>
    </ruleset>
    """
    
    rules = HttpsEverywhereRules()
    rules.parse_rules_from_string(test_xml)

    print("--- Testing HTTPS Everywhere Rewrites ---")
    print(f"http://example.com/path -> {rules.rewrite_uri('http://example.com/path')}")
    print(f"http://www.example.com/foo -> {rules.rewrite_uri('http://www.example.com/foo')}")
    print(f"http://sub.example.org/bar -> {rules.rewrite_uri('http://sub.example.org/bar')}")
    print(f"http://blog.example.com/post -> {rules.rewrite_uri('http://blog.example.com/post')}") # Should be excluded
    print(f"http://other.com/ -> {rules.rewrite_uri('http://other.com/')}") # No rule
    print(f"https://secure.com/ -> {rules.rewrite_uri('https://secure.com/')}") # Already HTTPS
