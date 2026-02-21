"""
Cradle Dynamic Skills Loader
==============================
Loads tools from the `skills/` directory at runtime.
This replaces the hardcoded list of tools in agent.py and allows
the agent to self-expand by writing new python files in `skills/`.
"""

import os
import sys
import importlib
import inspect
import logging

logger = logging.getLogger(__name__)

def load_skills():
    """
    Scans the `skills/` directory (or legacy root tools) and imports callable functions.
    For now, we'll keep the monolithic tools in the root but load them dynamically.
    Later, the agent can organize them into proper SKILL folders.
    """
    tools_list = []
    
    # 1. Base tools: load them individually so a single missing module doesn't break everything
    base_imports = [
        ('sandbox', 'execute_python_in_sandbox'),
        ('search_web', 'search_web'),
        ('read_webpage', 'read_webpage'),
        ('tools_system', 'execute_shell_command'),
        ('memory', ['update_memory', 'read_file', 'log_reflection', 'read_reflections', 'commit_and_push_to_github']),
        ('github_tools', ['create_github_repo', 'create_github_pr']),
        ('agentplaybooks_tools', ['manage_playbooks', 'playbook_memory']),
        ('tasks_skill', ['enqueue_task', 'list_tasks']),
        ('agent', 'check_model_router'),
        ('benchmark', 'benchmark_models'),
        ('headless_browser', 'headless_browse'),
        ('mcp_discovery', 'search_mcp_servers')
    ]
    
    for module_name, func_names in base_imports:
        try:
            module = importlib.import_module(module_name)
            if isinstance(func_names, str):
                func_names = [func_names]
            for func_name in func_names:
                if hasattr(module, func_name):
                    tools_list.append(getattr(module, func_name))
        except ImportError as e:
            logger.warning(f"Skipping base tool(s) from {module_name}: {e}")
        except Exception as e:
            logger.error(f"Error loading base tool from {module_name}: {e}")

    # 2. Dynamic 'skills' directory loading
    skills_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")
    if os.path.exists(skills_dir) and os.path.isdir(skills_dir):
        if skills_dir not in sys.path:
            sys.path.insert(0, skills_dir)
            
        for item in os.listdir(skills_dir):
            item_path = os.path.join(skills_dir, item)
            
            # Load Python files directly in skills/ (e.g., skills/aws_deploy.py)
            if os.path.isfile(item_path) and item.endswith('.py') and not item.startswith('__'):
                module_name = item[:-3]
                try:
                    module = importlib.import_module(module_name)
                    # Find all functions defined in that module (not imported)
                    for name, func in inspect.getmembers(module, inspect.isfunction):
                        if func.__module__ == module_name and not name.startswith('_'):
                            tools_list.append(func)
                            logger.info(f"Loaded dynamic skill block: {name} from {module_name}.py")
                except Exception as e:
                    logger.error(f"Failed to load skill module {module_name}: {e}")
                    
            # Load OpenClaw style folders (e.g., skills/code_reviewer/code_reviewer.py)
            elif os.path.isdir(item_path) and not item.startswith('__'):
                module_name = item
                # Check if there's a py file matching the folder name or __init__.py
                target_py = os.path.join(item_path, f"{item}.py")
                init_py = os.path.join(item_path, "__init__.py")
                
                mod_file = None
                if os.path.exists(target_py):
                    mod_file = target_py
                elif os.path.exists(init_py):
                    mod_file = init_py
                    
                if mod_file:
                    try:
                        # Dynamic import from path
                        spec = importlib.util.spec_from_file_location(module_name, mod_file)
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        
                        for name, func in inspect.getmembers(module, inspect.isfunction):
                            if func.__module__ == module_name and not name.startswith('_'):
                                tools_list.append(func)
                                logger.info(f"Loaded dynamic skill block: {name} from folder {item}")
                    except Exception as e:
                        logger.error(f"Failed to load skill folder {item}: {e}")

    # 3. Deduplicate tools by function name
    unique_tools = []
    seen_names = set()
    for tool in tools_list:
        if tool.__name__ not in seen_names:
            unique_tools.append(tool)
            seen_names.add(tool.__name__)
        else:
            logger.info(f"Skipping duplicate tool: {tool.__name__}")
            
    return unique_tools
