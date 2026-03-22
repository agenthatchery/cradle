import asyncio
import logging
import os
from typing import Optional, Callable
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = logging.getLogger(__name__)

class TelegramBot:
    """Telegram interface for the Cradle agent."""

    def __init__(self, config):
        self.config = config
        self.application = None
        self._running = False
        self._last_chat_id = None

        
        # Callbacks to be set by the agent
        self.on_task: Optional[Callable[[str], asyncio.Future[str]]] = None
        self.on_status: Optional[Callable[[], asyncio.Future[str]]] = None
        self.on_evolve: Optional[Callable[[], asyncio.Future[str]]] = None
        self.on_cost: Optional[Callable[[], asyncio.Future[str]]] = None

    @property
    def is_active(self) -> bool:
        """Check if the bot is running."""
        return self._running


    async def start(self):
        """Start the bot in a background task."""
        if not self.config.telegram_bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set, bot disabled.")
            return

        self.application = Application.builder().token(self.config.telegram_bot_token).build()

        # Add handlers
        self.application.add_handler(CommandHandler("start", self._start_command))
        self.application.add_handler(CommandHandler("help", self._help_command))
        self.application.add_handler(CommandHandler("plan", self._plan_command))
        self.application.add_handler(CommandHandler("status", self._status_command))
        self.application.add_handler(CommandHandler("evolve", self._evolve_command))
        self.application.add_handler(CommandHandler("cost", self._cost_command))

        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        self._running = True
        logger.info("Telegram bot started.")

    async def stop(self):
        """Stop the bot gracefully."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
        self._running = False
        logger.info("Telegram bot stopped.")

    async def send_message(self, text: str):
        """Send a message to the last active chat."""
        if not self.application or not self._last_chat_id:
            logger.info(f"Bot message (no chat_id): {text[:50]}...")
            return
        try:
            await self.application.bot.send_message(chat_id=self._last_chat_id, text=text)
            logger.info(f"Bot sent message to {self._last_chat_id}")
        except Exception as e:
            logger.error(f"Failed to send bot message: {e}")

    async def _update_chat_id(self, update: Update):
        """Helper to track latest user interaction."""
        if update.effective_chat:
            self._last_chat_id = update.effective_chat.id


    # --- Handlers ---

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._update_chat_id(update)
        await update.message.reply_text("🐣 Cradle Agent online. Use /plan, /status, or /evolve.")


    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._update_chat_id(update)
        help_text = (

            "/plan - View current task tree\n"
            "/status - System health and stats\n"
            "/evolve - Trigger self-evolution cycle\n"
            "/cost - LLM usage stats"
        )
        await update.message.reply_text(help_text)

    async def _plan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._update_chat_id(update)
        await update.message.reply_text("Recieving task plan...")

        if self.on_task: # Re-using on_task callback logic as placeholder for status summary
             msg = await self.on_status()
             await update.message.reply_text(msg)
        else:
             await update.message.reply_text("Task engine not connected.")

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._update_chat_id(update)
        if self.on_status:

            msg = await self.on_status()
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("Status unavailable.")

    async def _evolve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._update_chat_id(update)
        if self.on_evolve:

            await update.message.reply_text("🧬 Evolution cycle starting...")
            msg = await self.on_evolve()
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("Evolution engine unavailable.")

    async def _cost_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._update_chat_id(update)
        if self.on_cost:

            msg = await self.on_cost()
            await update.message.reply_text(msg)
        else:
            await update.message.reply_text("Cost stats unavailable.")


