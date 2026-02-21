import re
import json
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

def parse_and_execute_tools(text, tools_list):
    """
    Parses tool calls from text and executes them.
    Currently supports:
    1. <minimax:tool_call> or <tool_call> XML format
    """
    results = []
    
    # Create a map for tool lookup
    tool_map = {f.__name__: f for f in tools_list}
    
    # 1. Look for XML blocks (minimax:tool_call or just tool_call)
    xml_blocks = re.findall(r'<(?:minimax:)?tool_call>(.*?)</(?:minimax:)?tool_call>', text, re.DOTALL | re.IGNORECASE)
    
    for block in xml_blocks:
        try:
            # Wrap in a root tag to make it valid XML
            xml_data = f"<root>{block}</root>"
            root = ET.fromstring(xml_data)
            
            for invoke in root.findall('.//invoke'):
                tool_name = invoke.get('name')
                args = {}
                for param in invoke.findall('.//parameter'):
                    param_name = param.get('name')
                    param_value = param.text
                    args[param_name] = param_value
                
                if tool_name in tool_map:
                    logger.info(f"Executing fallback tool: {tool_name} with args: {args}")
                    try:
                        res = tool_map[tool_name](**args)
                        results.append(f"Tool {tool_name} output: {res}")
                    except Exception as e:
                        results.append(f"Tool {tool_name} failed: {str(e)}")
                else:
                    results.append(f"Tool {tool_name} not found in available skills.")
                    
        except Exception as e:
            logger.error(f"Failed to parse tool call block: {e}")
            results.append(f"Parse error in tool call block.")

    return results

def clean_response_text(text):
    """Removes tool call tags and any residual empty xml blocks from the final text response to the user."""
    # Strip tool_call blocks
    text = re.sub(r'<(?:minimax:)?tool_call>.*?</(?:minimax:)?tool_call>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Strip any standalone <invoke> tags that might have leaked outside
    text = re.sub(r'<invoke.*?</invoke>', '', text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()
