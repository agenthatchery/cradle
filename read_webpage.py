import urllib.request
import urllib.parse
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.in_body = False
        self.ignore_tags = {'script', 'style', 'nav', 'header', 'footer', 'noscript'}
        self.current_tag = ""

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag == 'body':
            self.in_body = True

    def handle_endtag(self, tag):
        if tag == 'body':
            self.in_body = False
        self.current_tag = ""

    def handle_data(self, data):
        if self.in_body and self.current_tag not in self.ignore_tags:
            line = data.strip()
            if line:
                self.text.append(line)

def read_webpage(url: str) -> str:
    """
    Navigates to a specific URL and extracts the visible text content from the body.
    Useful for reading API documentation, GitHub READMEs, or specific web pages.
    """
    try:
        req = urllib.request.Request(
            url, 
            data=None, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        parser = TextExtractor()
        parser.feed(html)
        text_content = "\n".join(parser.text)
        
        # Limit to 10k chars to avoid blowing up context window
        if len(text_content) > 10000:
            return text_content[:10000] + "\n...[Content Truncated]..."
        return text_content
    except Exception as e:
        return f"Failed to read webpage {url}: {str(e)}"
