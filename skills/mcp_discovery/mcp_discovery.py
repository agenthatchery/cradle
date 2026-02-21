import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

def search_mcp_servers(query: str) -> str:
    """
    Search for MCP (Model Context Protocol) servers by keyword.
    Returns a list of available MCP servers from Smithery and official registries.
    """
    results = []
    
    # 1. Search Smithery.ai (largest registry)
    try:
        url = f"https://registry.smithery.ai/servers?q={urllib.parse.quote(query)}&limit=10"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Cradle-Agent/1.0',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            servers = data if isinstance(data, list) else data.get('servers', data.get('results', []))
            for s in servers[:5]:
                name = s.get('qualifiedName', s.get('name', 'unknown'))
                desc = s.get('description', 'No description')[:150]
                results.append(f"[Smithery] {name}\n  {desc}")
    except Exception as e:
        logger.debug(f"Smithery search failed: {e}")
    
    # 2. Search official MCP Registry
    try:
        url = f"https://registry.modelcontextprotocol.io/servers?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Cradle-Agent/1.0',
            'Accept': 'application/json',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            servers = data if isinstance(data, list) else data.get('servers', data.get('results', []))
            for s in servers[:5]:
                name = s.get('name', 'unknown')
                desc = s.get('description', 'No description')[:150]
                results.append(f"[Official] {name}\n  {desc}")
    except Exception as e:
        logger.debug(f"Official registry search failed: {e}")
    
    # 3. Fallback: DuckDuckGo search
    if not results:
        try:
            ddg_url = f"https://html.duckduckgo.com/html/?q=MCP+server+{urllib.parse.quote(query)}+model+context+protocol"
            req = urllib.request.Request(ddg_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            
            for block in html.split('class="result__snippet"')[1:6]:
                text = block.split('>')[1].split('<')[0] if '>' in block else ''
                if text.strip():
                    results.append(f"[Web] {text.strip()[:200]}")
        except Exception as e:
            logger.debug(f"DuckDuckGo fallback failed: {e}")
    
    if not results:
        return f"No MCP servers found for '{query}'. Try broader terms like 'database', 'api', 'browser', 'file'."
    
    header = f"=== MCP Server Search: '{query}' — {len(results)} results ===\n"
    body = "\n\n".join(results)
    footer = "\n\nTo integrate an MCP server, use search_web() to find its GitHub repo and installation guide."
    
    return header + body + footer
