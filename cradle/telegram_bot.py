"""Telegram bot interface — filtered to @matebenyovszky only.

Provides commands:
  /status  — Current system status
  /task    — Submit a new task
  /plan    — Show current task tree
  /cost    — Show LLM usage stats
  /evolve  — Trigger self-evolution cycle
"""

import asyncio
import logging
from typing import Optional, Callable, Awaitable

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from cradle.config import Config

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram bot filtered to a single authorized user."""

    def __init__(self, config: Config):
        self.config = config
        self.allowed_user = config.allowed_telegram_user.lstrip("@")
        self._app: Optional[Application] = None
        self._chat_id: Optional[int] = None

        # Callbacks set by the orchestrator
        self.on_task: Optional[Callable[[str], Awaitable[str]]] = None
        self.on_status: Optional[Callable[[], Awaitable[str]]] = None
        self.on_evolve: Optional[Callable[[], Awaitable[str]]] = None
        self.on_cost: Optional[Callable[[], Awaitable[str]]] = None

    def _is_authorized(self, update: Update) -> bool:
        """Check if the message is from the authorized user."""
        user = update.effective_user
        if not user:
            logger.debug("Telegram update with no user")
            return False
            
        logger.info(f"Incoming Telegram message from: @{user.username} (allowed: @{self.allowed_user})")
        return user.username == self.allowed_user

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        self._chat_id = update.effective_chat.id
        await update.message.reply_text(
            "🐣 Cradle Agent online.\n\n"
            "Commands:\n"
            "/status — System status\n"
            "/task <description> — Submit a task\n"
            "/plan — Current task tree\n"
            "/cost — LLM usage stats\n"
            "/evolve — Trigger self-evolution\n\n"
            "Or just send me a message with a task."
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        self._chat_id = update.effective_chat.id
        if self.on_status:
            status = await self.on_status()
            await update.message.reply_text(status)
        else:
            await update.message.reply_text("Status callback not configured.")

    async def _cmd_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        self._chat_id = update.effective_chat.id
        task_text = " ".join(context.args) if context.args else ""
        if not task_text:
            await update.message.reply_text("Usage: /task <description>")
            return

        if self.on_task:
            await update.message.reply_text(f"⏳ Task received: {task_text}")
            result = await self.on_task(task_text)
            await self.send_message(result)
        else:
            await update.message.reply_text("Task engine not configured.")

    async def _cmd_cost(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        self._chat_id = update.effective_chat.id
        if self.on_cost:
            stats = await self.on_cost()
            await update.message.reply_text(stats)
        else:
            await update.message.reply_text("Cost tracking not configured.")

    async def _cmd_evolve(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._is_authorized(update):
            return
        self._chat_id = update.effective_chat.id
        if self.on_evolve:
            await update.message.reply_text("🧬 Starting self-evolution cycle...")
            result = await self.on_evolve()
            await self.send_message(result)
        else:
            await update.message.reply_text("Evolution engine not configured.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle free-text messages as tasks."""
        if not self._is_authorized(update):
            return
        self._chat_id = update.effective_chat.id
        text = update.message.text
        if not text:
            return

        if self.on_task:
            await update.message.reply_text(f"⏳ Processing: {text[:100]}...")
            result = await self.on_task(text)
            await self.send_message(result)
        else:
            await update.message.reply_text("I'm online but the task engine isn't ready yet.")

    async def send_message(self, text: str, chat_id: Optional[int] = None):
        """Send a message to the authorized user, splitting if needed."""
        target = chat_id or self._chat_id
        if not target or not self._app:
            logger.warning("Cannot send message — no chat_id or app")
            return

        # Telegram max message length is 4096
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            try:
                await self._app.bot.send_message(chat_id=target, text=chunk)
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}")

    async def start(self):
        """Start the Telegram bot (polling mode)."""
        if not self.config.telegram_bot_token:
            logger.warning("No Telegram bot token configured — bot disabled")
            return

        self._app = (
            Application.builder()
            .token(self.config.telegram_bot_token)
            .build()
        )

        # Register handlers
        self._app.add_handler(CommandHandler("start", self._cmd_start))
        self._app.add_handler(CommandHandler("status", self._cmd_status))
        self._app.add_handler(CommandHandler("task", self._cmd_task))
        self._app.add_handler(CommandHandler("cost", self._cmd_cost))
        self._app.add_handler(CommandHandler("evolve", self._cmd_evolve))
        self._app.add_handler(CommandHandler("plan", self._cmd_status))  # alias
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )

        logger.info(f"Telegram bot starting (allowed user: @{self.allowed_user})")

        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

    async def stop(self):
        """Stop the Telegram bot."""
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
