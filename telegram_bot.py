
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from task_engine import TaskEngine

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str, task_engine: TaskEngine):
        self.token = token
        self.task_engine = task_engine
        self.application = Application.builder().token(self.token).build()

        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("plan", self.plan_command)) # Add new handler

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text('Hi! I am your task management bot. Use /help to see available commands.')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = (
            "Available Commands:
"
            "/start - Start the bot
"
            "/help - Show this help message
"
            "/plan - Display the current hierarchical task tree"
        )
        await update.message.reply_text(help_text)

    async def plan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.info("Received /plan command")
        try:
            task_tree_str = self.task_engine.get_task_tree_visualization()
            if task_tree_str:
                await update.message.reply_text(f"Current Task Plan:
{task_tree_str}")
            else:
                await update.message.reply_text("No active tasks or plan found.")
        except Exception as e:
            logger.error(f"Error generating task plan: {e}")
            await update.message.reply_text(f"Failed to retrieve task plan: {e}")


    def run(self):
        logger.info("Bot started polling...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

