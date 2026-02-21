import os
import logging
import asyncio
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import agent
import concurrent.futures

# Dedicated thread pool for heavy LLM / Sandbox executions
agent_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Verify user
ALLOWED_USER = os.environ.get("ALLOWED_TELEGRAM_USER", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Strip @ sign if user provided it
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
    
    # Process message via agent. We run in an executor because google.genai is synchronous 
    # and we don't want to block the Telegram async event loop.
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

async def autonomous_loop():
    """
    Runs in the background indefinitely.
    Triggers the agent's autonomous reflection/action cycle.
    """
    await asyncio.sleep(10) # Wait for startup
    logger.info("Autonomous Loop Started.")
    while True:
        try:
            loop = asyncio.get_running_loop()
            logger.info("Triggering autonomous tick...")
            
            # Run the synchronous agent tick in a dedicated executor
            result = await loop.run_in_executor(agent_executor, agent.autonomous_tick)
            
            if result and str(result).strip():
                logger.info(f"Autonomous Tick Result: {result[:500]}...")
                
                # Optionally send this result to the Telegram allowed user
                # but we'd need to know their chat_id. For now, just logging is fine.
            
        except Exception as e:
             logger.error(f"Autonomous loop error: {e}")
             
        # Evolve once every 10 minutes (600 seconds)
        await asyncio.sleep(600)

if __name__ == '__main__':
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables.")
        exit(1)
        
    app = ApplicationBuilder().token(token).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Start the autonomous background loop via the event loop that PTB creates
    import threading
    def start_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(autonomous_loop())

    background_loop = asyncio.new_event_loop()
    t = threading.Thread(target=start_loop, args=(background_loop,), daemon=True)
    t.start()
    
    logger.info("Cradle Telegram Bot spinning up...")
    app.run_polling()
