import os
import urllib.request
import urllib.parse
import json

def create_github_repo(name: str, description: str) -> str:
    """
    Creates a new GitHub repository in the 'agenthatchery' organization. Use this to spawn new sub-agent repos.
    Returns the clone URL of the new repository on success.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return "Failed: GITHUB_TOKEN environment variable is not set."
        
    org = "agenthatchery"
    url = f"https://api.github.com/orgs/{org}/repos"
    
    data = json.dumps({
        "name": name,
        "description": description,
        "private": False
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                resp_data = json.loads(response.read().decode('utf-8'))
                return f"Successfully created repository: {resp_data['clone_url']}"
            else:
                return f"Failed to create repo. Status code: {response.status}"
    except Exception as e:
        return f"Failed to create repo due to an error: {e}"

def create_github_pr(title: str, body: str, head_branch: str, base_branch: str = "main") -> str:
    """
    Creates a Pull Request on GitHub for a branch you just pushed.
     ALWAYS use this after using commit_and_push_to_github() with a new branch, 
    so the operator can review and merge your self-modifications.
    """
    token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("GITHUB_REPO", "agenthatchery/cradle") # Fallback to default
    
    if not token:
        return "Failed: GITHUB_TOKEN environment variable is not set."
        
    url = f"https://api.github.com/repos/{repo_name}/pulls"
    
    data = json.dumps({
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch
    }).encode('utf-8')
    
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 201:
                resp_data = json.loads(response.read().decode('utf-8'))
                return f"Successfully created PR: {resp_data['html_url']}"
            else:
                return f"Failed to create PR. Status code: {response.status}"
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode('utf-8')
        return f"Failed to create PR (HTTP {e.code}): {error_msg}"
    except Exception as e:
        return f"Failed to create PR due to an error: {e}"
