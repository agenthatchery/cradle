import re
import json
import logging
import xml.etree.ElementTree as ET

import inspect

logger = logging.getLogger(__name__)

# Global mapping for common model hallucinations to correct tool parameters
PARAMS_MAPPING = {
    "read_tiered_memory": {"query": "tier", "lookback": "limit"},
    "store_tiered_memory": {"msg": "value", "content": "value", "text": "value"},
    "update_memory": {"text": "content", "data": "content", "val": "content"},
    "log_reflection": {"msg": "content", "text": "content", "thought": "content"},
    "search_web": {"search": "query", "q": "query"},
    "read_webpage": {"link": "url"},
    "read_file": {"path": "filename", "file": "filename"},
}

def filter_args(func, args):
    """Filters args to only include those accepted by the function signature."""
    sig = inspect.signature(func)
    valid_params = sig.parameters.keys()
    
    # 1. Apply mapping
    mapped_args = {}
    func_mappings = PARAMS_MAPPING.get(func.__name__, {})
    for k, v in args.items():
        correct_k = func_mappings.get(k, k)
        mapped_args[correct_k] = v
        
    # 2. Filter to valid signature
    return {k: v for k, v in mapped_args.items() if k in valid_params}

def parse_and_execute_tools(text, tools_list):
    """
    Parses tool calls from text and executes them.
    Supports <minimax:tool_call> or <tool_call> blocks.
    Now more resilient to markdown and unescaped characters.
    """
    results = []
    tool_map = {f.__name__: f for f in tools_list}
    
    # 1. Strip markdown code blocks that often wrap XML
    text = re.sub(r'```(?:xml)?(.*?)```', r'\1', text, flags=re.DOTALL)
    
    # 2. Extract tool_call blocks
    xml_blocks = re.findall(r'<(?:minimax:)?tool_call>(.*?)</(?:minimax:)?tool_call>', text, re.DOTALL | re.IGNORECASE)
    
    for block in xml_blocks:
        try:
            # Pre-processing: escape & if they aren't entities (common in URLs)
            processed_block = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', block)
            
            # Wrap and parse
            xml_data = f"<root>{processed_block}</root>"
            root = ET.fromstring(xml_data)
            
            for invoke in root.findall('.//invoke'):
                tool_name = invoke.get('name')
                args = {}
                for param in invoke.findall('.//parameter'):
                    param_name = param.get('name')
                    param_value = param.text
                    if param_value:
                        args[param_name] = param_value.strip()
                
                if tool_name in tool_map:
                    target_func = tool_map[tool_name]
                    # Apply parameter mapping and filtering
                    clean_args = filter_args(target_func, args)
                    
                    logger.info(f"Executing tool call: {tool_name} with args: {clean_args}")
                    try:
                        res = target_func(**clean_args)
                        results.append(f"Tool {tool_name} output: {res}")
                    except Exception as e:
                        results.append(f"Tool {tool_name} failed: {str(e)}")
                else:
                    results.append(f"Tool {tool_name} not found.")
                    
        except ET.ParseError as pe:
            # Ultra-fallback: Regex search for single-invoke blocks if XML fails
            logger.warning(f"XML parse failed, trying regex fallback: {pe}")
            invoke_matches = re.findall(r'<invoke\s+name=["\'](.*?)["\']>(.*?)</invoke>', block, re.DOTALL)
            for name, content in invoke_matches:
                if name in tool_map:
                    target_func = tool_map[name]
                    params = re.findall(r'<parameter\s+name=["\'](.*?)["\']>(.*?)</parameter>', content, re.DOTALL)
                    raw_args = {k: v.strip() for k, v in params}
                    clean_args = filter_args(target_func, raw_args)
                    try:
                        res = target_func(**clean_args)
                        results.append(f"Tool {name} output: {res}")
                    except Exception as e:
                        results.append(f"Tool {name} failed: {str(e)}")
        except Exception as e:
            logger.error(f"Critical parse error: {e}")
            results.append(f"Parse error in tool call block.")

    return results

    return results

def clean_response_text(text):
    """Removes tool call tags and any residual empty xml blocks from the final text response to the user."""
    # Strip tool_call blocks
    text = re.sub(r'<(?:minimax:)?tool_call>.*?</(?:minimax:)?tool_call>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Strip any standalone <invoke> tags that might have leaked outside
    text = re.sub(r'<invoke.*?</invoke>', '', text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()
