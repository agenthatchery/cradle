# MCP Server Discovery Skill

## Purpose
Enables Cradle to search the internet for Model Context Protocol (MCP) servers. 
This allows the agent to autonomously discover new tools, data sources, and integrations, accelerating the path to Kardashev Level 3.

## Usage
The skill exposes one Python function to the agent's tool-calling interface:
`search_mcp_servers(query: str) -> str`

## Data Sources
1. **Smithery.ai**: The largest public registry of AI agent MCP servers.
2. **registry.modelcontextprotocol.io**: The official Anthropic-backed registry.
3. **DuckDuckGo**: HTML scraping fallback if APIs fail.

## Evolution Notes
As of Phase 7, Cradle uses this skill to learn about new backend integrations. 
In Phase 8, this skill should be expanded to allow Cradle to not just *discover*, but automatically *install* and *mount* MCP servers into its own Docker container.
