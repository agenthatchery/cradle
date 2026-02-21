import os
import sys
import logging
import asyncio
import threading
import subprocess
import time
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import agent
import heartbeat
import concurrent.futures

# Dedicated thread pool for heavy LLM / Sandbox executions
agent_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/data/cradle_debug.log')
    ]
)
logger = logging.getLogger(__name__)

# Verify user
ALLOWED_USER = os.environ.get("ALLOWED_TELEGRAM_USER", "")


# ===== SELF-UPDATE MECHANISM =====
def self_update():
    """Pull latest code from GitHub. If files changed, restart the process."""
    try:
        # Prevent 'dubious ownership' errors inside the Docker container
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/app"], check=False)
        
        old_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd="/app"
        ).decode().strip()
        
        subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            cwd="/app", capture_output=True, timeout=30
        )
        
        new_hash = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd="/app"
        ).decode().strip()
        
        if old_hash != new_hash:
            logger.info(f"Self-update: Code changed ({old_hash[:7]} -> {new_hash[:7]}). Restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        else:
            logger.info("Self-update: Already up-to-date.")
    except Exception as e:
        logger.warning(f"Self-update check failed (non-fatal): {e}")


def auto_commit_changes():
    """Commit and push any local changes the agent made."""
    try:
        # Check if there are changes
        status = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd="/app"
        ).decode().strip()
        
        if not status:
            return  # Nothing to commit
        
        subprocess.run(["git", "add", "-A"], cwd="/app", capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"auto: self-improvement tick {time.strftime('%Y-%m-%d %H:%M')}"],
            cwd="/app", capture_output=True
        )
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd="/app", capture_output=True, timeout=30
        )
        if result.returncode == 0:
            logger.info("Auto-commit: Pushed changes to GitHub.")
        else:
            logger.warning(f"Auto-commit: Push failed: {result.stderr.decode()[:200]}")
    except Exception as e:
        logger.warning(f"Auto-commit failed (non-fatal): {e}")


# ===== TELEGRAM HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    allowed = ALLOWED_USER.replace('@', '')
    if update.effective_user.username != allowed:
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text("Cradle initialized. I am listening.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username or "unknown"
    allowed = ALLOWED_USER.replace('@', '')
    
    logger.info(f"Incoming message from: {username}. Text: {update.message.text[:50]}")
    if username != allowed:
        logger.warning(f"Message dropped from unauthorized user: {username}")
        return

    user_text = update.message.text
    
    # Send temporary processing message
    processing_msg = await update.message.reply_text("Thinking...")
    
    loop = asyncio.get_running_loop()
    try:
        reply_text = await loop.run_in_executor(agent_executor, agent.process_message, user_text)
    except Exception as e:
        reply_text = f"Agent internal crash: {str(e)}"
    
    if not reply_text:
        reply_text = "Done (no output generated)."
        
    # Telegram has a 4096 char limit
    if len(reply_text) > 4000:
        reply_text = reply_text[:4000] + "\n...[truncated]"
        
    await context.bot.edit_message_text(
        chat_id=update.effective_chat.id, 
        message_id=processing_msg.message_id, 
        text=reply_text
    )


# ===== BACKGROUND LOOPS =====
async def autonomous_loop():
    """
    Self-improvement loop: runs every 10 minutes.
    1. Pull latest code from GitHub
    2. Run autonomous tick (AI self-improvement)
    3. Commit any changes the agent made
    """
    await asyncio.sleep(10)  # Wait for startup
    logger.info("Autonomous Self-Improvement Loop ACTIVE.")
    
    while True:
        try:
            # Step 1: Pull latest code
            self_update()
            
            # Step 2: Run autonomous tick
            loop = asyncio.get_running_loop()
            logger.info("Triggering autonomous tick...")
            result = await loop.run_in_executor(agent_executor, agent.autonomous_tick)
            
            if result and str(result).strip():
                logger.info(f"Autonomous Tick Result: {str(result)[:500]}...")
            
            # Step 3: Auto-commit any changes the agent made
            auto_commit_changes()
            
        except Exception as e:
            logger.error(f"Autonomous loop error: {e}")
             
        # Evolve every 10 minutes (600 seconds)
        await asyncio.sleep(600)


if __name__ == '__main__':
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables.")
        exit(1)
    
    # Self-update on startup
    self_update()
    
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Thread 1: Autonomous self-improvement loop (every 10 min)
    def start_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(autonomous_loop())

    background_loop = asyncio.new_event_loop()
    t_auto = threading.Thread(target=start_loop, args=(background_loop,), daemon=True)
    t_auto.start()
    
    # Thread 2: Heartbeat task queue processor (every 60s)
    t_heart = threading.Thread(target=heartbeat.run_heartbeat_loop, kwargs={'interval': 60}, daemon=True)
    t_heart.start()
    
    logger.info("Cradle Telegram Bot spinning up with Self-Update + Heartbeat + Autonomous Tick ✓")
    app.run_polling()
