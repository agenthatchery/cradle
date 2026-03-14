
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio

# Assume task_engine is in the same directory or accessible
# For simplicity in this isolated environment, we'll mock it if not present
try:
    from task_engine import TaskEngine
    task_engine = TaskEngine() # Initialize your TaskEngine instance
except ImportError:
    logging.warning("task_engine.py not found or TaskEngine class not available. Mocking TaskEngine.")
    class MockTaskEngine:
        def get_task_tree(self):
            return {
                "id": "root",
                "title": "Root Task (Mock)",
                "status": "active",
                "subtasks": [
                    {
                        "id": "sub1",
                        "title": "Subtask 1 (Mock)",
                        "status": "pending",
                        "subtasks": []
                    },
                    {
                        "id": "sub2",
                        "title": "Subtask 2 (Mock)",
                        "status": "completed",
                        "subtasks": [
                            {
                                "id": "sub2_1",
                                "title": "Subtask 2.1 (Mock)",
                                "status": "in_progress",
                                "subtasks": []
                            }
                        ]
                    }
                ]
            }
    task_engine = MockTaskEngine()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Hi! I'm your task bot. Use /plan to see your task tree.")

async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the current task tree to the user."""
    task_tree = task_engine.get_task_tree()
    tree_str = format_task_tree(task_tree)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"```
{tree_str}
```", parse_mode='MarkdownV2')

def format_task_tree(node, level=0, prefix=""):
    """Recursively formats the task tree into a human-readable string."""
    indent = "  " * level
    status_icon = {
        "pending": "⚪",
        "in_progress": "🟠",
        "active": "🟢",
        "completed": "✅",
        "failed": "❌"
    }.get(node.get("status", "unknown"), "❓")
    
    # Escape special MarkdownV2 characters
    title = node.get("title", "Untitled").replace("-", "\-").replace("_", "\_").replace(".", "\.").replace("(", "\").replace(")", "\")
    status = node.get("status", "unknown").replace("-", "\-").replace("_", "\_").replace(".", "\.").replace("(", "\").replace(")", "\")

    tree_string = f"{indent}{prefix}{status_icon} {title} \[{status}\]
"
    for i, subtask in enumerate(node.get("subtasks", [])):
        new_prefix = "├── " if i < len(node["subtasks"]) - 1 else "└── "
        tree_string += format_task_tree(subtask, level + 1, new_prefix)
    return tree_string


async def main():
    # Replace with your actual bot token
    application = ApplicationBuilder().token(os.environ.get("TELEGRAM_BOT_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("plan", plan))

    await application.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
