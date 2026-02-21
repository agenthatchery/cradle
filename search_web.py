import urllib.request
import urllib.parse
import json

def search_web(query: str) -> str:
    """
    Searches the internet for information matching the query using the DuckDuckGo Lite HTML interface
    and returns a summary of the top results. Used for research and discovering new tech/methods.
    """
    # DuckDuckGo Lite HTML search is easy to parse
    # Wait, we can use the duckduckgo html search directly
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        req = urllib.request.Request(
            url, 
            data=None, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
            }
        )
        
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            
        # Basic parsing without BeautifulSoup to keep dependencies low
        results = []
        chunks = html.split('<a class="result__url" href="')
        for chunk in chunks[1:6]: # Top 5
            try:
                link = chunk.split('">')[0]
                snippet_chunk = chunk.split('<a class="result__snippet')[1]
                snippet = snippet_chunk.split('</a>')[0].split('href="')[1].split('">')[1]
                
                # Cleanup simple HTML tags
                snippet = snippet.replace('<b>', '').replace('</b>', '')
                results.append(f"URL: {link}\nSnippet: {snippet}\n")
            except:
                pass
                
        if not results:
            return "Search succeeded but no parseable results were found."
            
        return "Search Results:\n\n" + "\n".join(results)
        
    except Exception as e:
        return f"Search failed: {str(e)}"
