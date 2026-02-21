import os
import re
import logging
import subprocess
from google import genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("self-healer")

FILES_TO_PATCH = [
    "/root/cradle/model_router.py",
    "/root/cradle/agent.py"
]

def get_available_models():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        return []
    
    client = genai.Client(api_key=api_key)
    try:
        models = [m.name.replace("models/", "") for m in client.models.list()]
        logger.info(f"Available Google models: {models}")
        return models
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        return []

def find_best_match(base_name, available):
    # If the base name (e.g. gemini-3.1-pro) is not in available,
    # look for gemini-3.1-pro-preview or similar.
    if base_name in available:
        return base_name
    
    candidates = [m for m in available if m.startswith(base_name)]
    if candidates:
        # Sort by length, usually shorter is better, but here we probably want a specific one
        # For now, just take the first one that exists
        logger.info(f"Found match for {base_name}: {candidates[0]}")
        return candidates[0]
    return None

def patch_files(mapping):
    patched = False
    for filepath in FILES_TO_PATCH:
        if not os.path.exists(filepath):
            continue
            
        with open(filepath, 'r') as f:
            content = f.read()
            
        original_content = content
        for old, new in mapping.items():
            if not new: continue
            # Handle both JSON endpoints and plain list strings
            # Match gemini-3.1-pro:generateContent
            content = content.replace(f"{old}:generateContent", f"{new}:generateContent")
            # Match "gemini-3.1-pro"
            content = content.replace(f'"{old}"', f'"{new}"')
            content = content.replace(f"'{old}'", f"'{new}'")
            
        if content != original_content:
            with open(filepath, 'w') as f:
                f.write(content)
            logger.info(f"Patched {filepath}")
            patched = True
            
    return patched

def main():
    available = get_available_models()
    if not available:
        return

    # Targeting the primary models we want to keep healed
    targets = ["gemini-3.1-pro", "gemini-3-pro", "gemini-3-flash"]
    mapping = {t: find_best_match(t, available) for t in targets}
    
    logger.info(f"Healing mapping: {mapping}")
    
    if patch_files(mapping):
        logger.info("Self-healing complete. Committing changes...")
        try:
            subprocess.run(["git", "add", "."], check=True, cwd="/root/cradle")
            subprocess.run(["git", "commit", "-m", "chore(self-heal): automated API model string resolution"], check=True, cwd="/root/cradle")
            subprocess.run(["git", "push", "origin", "main"], check=True, cwd="/root/cradle")
            logger.info("Changes pushed to GitHub. Triggering restart...")
            # We assume Docker Compose restart policy or an external watchdog handles the restart
            # Or we can just exit and let the monitor restart us.
        except Exception as e:
            logger.error(f"Failed to commit/push healed code: {e}")
    else:
        logger.info("No healing required. All models aligned.")

if __name__ == "__main__":
    main()
