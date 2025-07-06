import xml.etree.ElementTree as ET
import urllib.parse
from typing import Optional, Dict, Any
import requests
from .debug import debug_print

class OpenSearchParser:
    """Parser for OpenSearch description documents."""
    
    # OpenSearch XML namespace
    OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def parse_opensearch_url(self, opensearch_url: str) -> Optional[Dict[str, Any]]:
        """Parse OpenSearch description from URL."""
        try:
            response = self.session.get(opensearch_url, timeout=self.timeout)
            response.raise_for_status()
            
            return self.parse_opensearch_xml(response.text, opensearch_url)
        except requests.RequestException as e:
            debug_print(f"Failed to fetch OpenSearch description from {opensearch_url}: {e}")
            return None
    
    def parse_opensearch_xml(self, xml_content: str, base_url: str = None) -> Optional[Dict[str, Any]]:
        """Parse OpenSearch XML content."""
        try:
            # Handle XML with namespace
            root = ET.fromstring(xml_content)
            
            # Extract search engine information
            engine_data = {
                'name': self._get_element_text(root, 'ShortName'),
                'description': self._get_element_text(root, 'Description'),
                'url': None,
                'suggestions_url': None,
                'favicon_url': None,
                'input_encoding': self._get_element_text(root, 'InputEncoding', 'UTF-8'),
            }
            
            # Find search URLs
            for url_elem in root.findall(f'.//{{{self.OPENSEARCH_NS}}}Url'):
                url_type = url_elem.get('type', '')
                template = url_elem.get('template', '')
                
                if not template:
                    continue
                
                # Convert absolute URLs if base_url is provided
                if base_url and not template.startswith(('http://', 'https://')):
                    template = urllib.parse.urljoin(base_url, template)
                
                # Main search URL
                if url_type in ['text/html', 'application/xhtml+xml']:
                    engine_data['url'] = template
                
                # Search suggestions URL
                elif url_type in ['application/json', 'application/x-suggestions+json']:
                    engine_data['suggestions_url'] = template
            
            # Find favicon/icon
            for image_elem in root.findall(f'.//{{{self.OPENSEARCH_NS}}}Image'):
                image_url = image_elem.text
                if image_url:
                    # Convert relative URLs to absolute
                    if base_url and not image_url.startswith(('http://', 'https://')):
                        image_url = urllib.parse.urljoin(base_url, image_url)
                    engine_data['favicon_url'] = image_url
                    break
            
            # Validate required fields
            if not engine_data['name'] or not engine_data['url']:
                debug_print("OpenSearch description missing required fields (name or URL)")
                return None
            
            # Clean up the URL template for our system
            if engine_data['url']:
                engine_data['url'] = self._convert_opensearch_template(engine_data['url'])
            
            if engine_data['suggestions_url']:
                engine_data['suggestions_url'] = self._convert_opensearch_template(engine_data['suggestions_url'])
            
            return engine_data
            
        except ET.ParseError as e:
            debug_print(f"Failed to parse OpenSearch XML: {e}")
            return None
    
    def _get_element_text(self, root: ET.Element, tag_name: str, default: str = None) -> str:
        """Get text content of an element, handling namespace."""
        elem = root.find(f'.//{{{self.OPENSEARCH_NS}}}{tag_name}')
        if elem is not None and elem.text:
            return elem.text.strip()
        return default
    
    def _convert_opensearch_template(self, template: str) -> str:
        """Convert OpenSearch template parameters to our format."""
        # OpenSearch uses {searchTerms} parameter, we use %s
        template = template.replace('{searchTerms}', '%s')
        
        # Handle other common parameters
        template = template.replace('{count}', '10')  # Default count
        template = template.replace('{startIndex}', '0')  # Default start index
        template = template.replace('{startPage}', '1')  # Default start page
        template = template.replace('{language}', 'en')  # Default language
        template = template.replace('{inputEncoding}', 'UTF-8')  # Default encoding
        template = template.replace('{outputEncoding}', 'UTF-8')  # Default encoding
        
        return template
    
    def discover_opensearch_from_html(self, html_content: str, page_url: str) -> list[str]:
        """Discover OpenSearch description URLs from HTML content."""
        opensearch_urls = []
        
        try:
            # Simple regex-based parsing to find OpenSearch links
            import re
            
            # Look for link tags with OpenSearch rel attribute
            link_pattern = r'<link[^>]+rel=["\'](?:search|opensearch)["\'][^>]*>'
            links = re.findall(link_pattern, html_content, re.IGNORECASE)
            
            for link in links:
                # Extract href attribute
                href_match = re.search(r'href=["\']([^"\']+)["\']', link, re.IGNORECASE)
                if href_match:
                    href = href_match.group(1)
                    
                    # Convert relative URLs to absolute
                    if not href.startswith(('http://', 'https://')):
                        href = urllib.parse.urljoin(page_url, href)
                    
                    opensearch_urls.append(href)
                    
        except Exception as e:
            debug_print(f"Failed to discover OpenSearch from HTML: {e}")
        
        return opensearch_urls
    
    def generate_keyword_from_name(self, name: str) -> str:
        """Generate a keyword from the search engine name."""
        # Simple keyword generation: take first word, lowercase, limit to 10 chars
        if not name:
            return ""
        
        # Remove common words and clean
        words = name.lower().split()
        cleaned_words = [word for word in words if word not in ['search', 'engine', 'web', 'the', 'a', 'an']]
        
        if cleaned_words:
            keyword = cleaned_words[0]
        else:
            keyword = words[0] if words else name.lower()
        
        # Clean non-alphanumeric characters
        keyword = ''.join(c for c in keyword if c.isalnum())
        
        # Limit length
        return keyword[:10]
    
    def validate_search_engine_data(self, engine_data: Dict[str, Any]) -> bool:
        """Validate that search engine data is complete and usable."""
        # Check required fields
        if not engine_data.get('name') or not engine_data.get('url'):
            return False
        
        # Check URL format
        url = engine_data.get('url', '')
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Check if URL has search parameter placeholder
        if '%s' not in url:
            return False
        
        return True