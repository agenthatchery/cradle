import os
import sqlite3
import datetime
from git import Repo

# Initialize local SQLite Memory DB
DB_FILE = "/app/cradle_memory.db"

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reflections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                content TEXT
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Memory DB Init Error: {e}")

init_db()

def log_reflection(content: str) -> str:
    """
    Logs an internal thought, learning, or reflection to long-term memory.
    Useful for retaining context across autonomous cycles.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Ensure UTC timezone and ISO format
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("INSERT INTO reflections (timestamp, content) VALUES (?, ?)", (timestamp, content))
        conn.commit()
        conn.close()
        return f"Successfully saved reflection to memory at {timestamp}"
    except Exception as e:
        return f"Failed to save reflection: {e}"

def read_reflections(limit: int = 10) -> str:
    """
    Retrieves the most recent reflections from long-term memory.
    """
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT timestamp, content FROM reflections ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return "No previous reflections found."
            
        result = "Recent Reflections:\n"
        for row in reversed(rows):
            result += f"[{row[0]}] {row[1]}\n"
        return result
    except Exception as e:
        return f"Failed to read reflections: {e}"

def update_memory(filename: str, content: str) -> str:
    """
    Writes or updates a file (like core_prompt.md, or a python script) in the local repository.
    Use this to permanently change your behavior.
    """
    try:
        with open(filename, 'w') as f:
            f.write(content)
        return f"Successfully updated {filename}"
    except Exception as e:
        return f"Failed to update memory {filename}: {str(e)}"

def read_file(filename: str) -> str:
    """Read the contents of a local file."""
    try:
        with open(filename, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Failed to read file {filename}: {str(e)}"

def commit_and_push_to_github(commit_message: str, branch_name: str = "main") -> str:
    """
    Commits all local changes and pushes to the specified branch on GitHub.
    This effectively deploys your mutations.
    """
    try:
        # Assumes the working directory is already a git repository linked to remote origin
        repo = Repo('.')
        repo.git.add(A=True)
        repo.index.commit(commit_message)
        
        # Ensure branch exists locally
        if branch_name not in [h.name for h in repo.heads]:
            repo.create_head(branch_name)
        
        # Checkout the branch and push
        repo.heads[branch_name].checkout()
        origin = repo.remote(name='origin')
        origin.push(refspec=f'{branch_name}:{branch_name}')
        
        # Go back to main if we moved
        if branch_name != "main" and "main" in [h.name for h in repo.heads]:
            repo.heads["main"].checkout()
            
        return f"Successfully committed and pushed to {branch_name}"
    except Exception as e:
         return f"Failed to commit and push: {str(e)}"
