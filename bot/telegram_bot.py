import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from .database import db
from .helius_client import helius_client
from .solana_utils import is_valid_solana_address
from .formatters import (
    format_welcome,
    format_wallet_list,
    format_wallet_added,
    format_wallet_removed,
    format_wallet_renamed,
    format_error,
)

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command."""
    await update.message.reply_text(
        format_welcome(),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /add <address> <name> command."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            format_error("Usage: /add <address> <name>"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    address = context.args[0]
    name = " ".join(context.args[1:])

    # Validate address
    if not is_valid_solana_address(address):
        await update.message.reply_text(
            format_error("Invalid Solana address format."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Check if wallet already exists
    existing = await db.get_wallet(address)
    if existing:
        await update.message.reply_text(
            format_error(f"Wallet is already being tracked as '{existing['name']}'."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Create Helius webhook
    webhook_id = await helius_client.create_webhook(address)
    if not webhook_id:
        await update.message.reply_text(
            format_error("Failed to create webhook. Please try again later."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Add to database
    success = await db.add_wallet(address, name, webhook_id)
    if success:
        await update.message.reply_text(
            format_wallet_added(name, address),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        logger.info(f"Added wallet: {name} ({address})")
    else:
        # Cleanup webhook if database insert failed
        await helius_client.delete_webhook(webhook_id)
        await update.message.reply_text(
            format_error("Failed to add wallet. Please try again."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /remove <address> command."""
    if not context.args:
        await update.message.reply_text(
            format_error("Usage: /remove <address>"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    address = context.args[0]

    # Get wallet info before removing
    wallet = await db.get_wallet(address)
    if not wallet:
        await update.message.reply_text(
            format_error("Wallet not found in tracked list."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Delete Helius webhook
    if wallet.get("helius_webhook_id"):
        await helius_client.delete_webhook(wallet["helius_webhook_id"])

    # Remove from database
    await db.remove_wallet(address)

    await update.message.reply_text(
        format_wallet_removed(wallet["name"], address),
        parse_mode=ParseMode.MARKDOWN_V2,
    )
    logger.info(f"Removed wallet: {wallet['name']} ({address})")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /list command."""
    wallets = await db.get_wallets()
    await update.message.reply_text(
        format_wallet_list(wallets),
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def rename_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /rename <address> <new_name> command."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            format_error("Usage: /rename <address> <new_name>"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    address = context.args[0]
    new_name = " ".join(context.args[1:])

    # Get current wallet info
    wallet = await db.get_wallet(address)
    if not wallet:
        await update.message.reply_text(
            format_error("Wallet not found in tracked list."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    old_name = wallet["name"]

    # Update name
    success = await db.rename_wallet(address, new_name)
    if success:
        await update.message.reply_text(
            format_wallet_renamed(old_name, new_name, address),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        logger.info(f"Renamed wallet: {old_name} -> {new_name} ({address})")
    else:
        await update.message.reply_text(
            format_error("Failed to rename wallet."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )


def create_bot_application() -> Application:
    """Create and configure the Telegram bot application."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("rename", rename_command))

    return application


async def send_alert(message: str) -> bool:
    """Send an alert message to the configured chat."""
    from telegram import Bot

    if not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not configured")
        return False

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False
