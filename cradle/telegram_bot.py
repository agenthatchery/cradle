
import asyncio
import task_engine
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

# Placeholder for task_engine integration
class TaskEngine:
    def get_task_tree(self):
        # Simulate a hierarchical task tree for demonstration
        return {
            "title": "Overall Project",
            "description": "Develop a new feature",
            "subtasks": [
                {
                    "title": "Research phase",
                    "description": "Gather requirements and explore options",
                    "subtasks": [
                        {"title": "Market analysis", "description": "Analyze competitor features"},
                        {"title": "User interviews", "description": "Collect user feedback"}
                    ]
                },
                {
                    "title": "Development phase",
                    "description": "Implement the core functionality",
                    "subtasks": [
                        {"title": "Design UI/UX", "description": "Create wireframes and mockups"},
                        {
                            "title": "Backend implementation",
                            "description": "Develop API endpoints",
                            "subtasks": [
                                {"title": "Database schema", "description": "Define database tables"},
                                {"title": "API development", "description": "Implement REST endpoints"}
                            ]
                        },
                        {"title": "Frontend development", "description": "Build user interface"}
                    ]
                },
                {"title": "Testing phase", "description": "Ensure quality and stability"}
            ]
        }

task_engine = TaskEngine() # Instantiate a placeholder TaskEngine


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a formatted task tree as a response to the /plan command."""
    task_tree = task_engine.get_current_task_tree() # Assuming this function exists in task_engine
    if task_tree:
        formatted_tree = format_task_tree(task_tree)
        await update.message.reply_text(f"Current Task Plan:
```
{formatted_tree}
```", parse_mode='MarkdownV2')
    else:
        await update.message.reply_text("No active task plan found.")

def format_task_tree(task_node, indent=0):
    """Recursively formats the task tree into a human-readable string."""
    prefix = '  ' * indent
    status = task_node.get('status', 'UNKNOWN')
    description = task_node.get('description', 'No Description')
    output = f"{prefix}- [{status}] {description}
"

    subtasks = task_node.get('subtasks', [])
    for subtask in subtasks:
        output += format_task_tree(subtask, indent + 1)
    return output

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message on /start"""
    await update.message.reply_text('Hi! Use /plan to see the current task tree.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message on /help"""
    await update.message.reply_text('Help!')

def format_task_tree(task_node, indent=0):
    """Recursively formats the task tree into a human-readable string."""
    if not task_node:
        return ""

    prefix = "  " * indent
    tree_str = f"{prefix}- {task_node['title']}"
    if 'description' in task_node and task_node['description']:
        tree_str += f" ({task_node['description']})"
    tree_str += "
"

    if 'subtasks' in task_node and task_node['subtasks']:
        for subtask in task_node['subtasks']:
            tree_str += format_task_tree(subtask, indent + 1)
    return tree_str

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the current task tree on /plan"""
    task_tree = task_engine.get_task_tree()
    if task_tree:
        formatted_tree = format_task_tree(task_tree)
        await update.message.reply_text(f"Current Task Plan:
{formatted_tree}")
    else:
        await update.message.reply_text("No active plan found.")

def main() -> None:
    """Start the bot."""
    telegram_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    if not telegram_token:
        print("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(telegram_token).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("plan", plan_command)
    application.add_handler(CommandHandler("plan", plan_command))) # Add the new /plan command handler

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

@bot.message_handler(commands=['plan'])
def send_plan(message):
    try:
        task_tree = task_engine.get_task_tree_string()
        if task_tree:
            bot.reply_to(message, f"Current Task Plan:
{task_tree}")
        else:
            bot.reply_to(message, "No active tasks found.")
    except Exception as e:
        bot.reply_to(message, f"Error retrieving task plan: {e}")

