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
from .solana_utils import is_valid_solana_address, get_token_info, get_token_price, format_amount, format_usd
from .formatters import (
    format_welcome,
    format_wallet_list,
    format_wallet_added,
    format_wallet_removed,
    format_wallet_renamed,
    format_error,
    format_whosinit,
)

logger = logging.getLogger(__name__)


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /chatid command - shows the current chat's ID."""
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    await update.message.reply_text(
        f"Chat ID: `{chat_id}`\nChat type: {chat_type}\n\nUse this ID as your TELEGRAM\\_CHAT\\_ID in \\.env",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


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

    # Get all current wallet addresses and add the new one
    wallets = await db.get_wallets()
    all_addresses = [w["address"] for w in wallets] + [address]

    # Update the shared webhook with all addresses
    success = await helius_client.add_wallet_to_webhook(address, all_addresses)
    if not success:
        await update.message.reply_text(
            format_error("Failed to setup monitoring. Please try again later."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Add to database (no individual webhook ID needed anymore)
    success = await db.add_wallet(address, name, None)
    if success:
        await update.message.reply_text(
            format_wallet_added(name, address),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        logger.info(f"Added wallet: {name} ({address})")
    else:
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

    # Remove from database first
    await db.remove_wallet(address)

    # Get remaining addresses and update webhook
    wallets = await db.get_wallets()
    remaining_addresses = [w["address"] for w in wallets]
    await helius_client.remove_wallet_from_webhook(remaining_addresses)

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


async def whosinit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /whosinit <token_address> command."""
    if not context.args:
        await update.message.reply_text(
            format_error("Usage: /whosinit <token_address>"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    token_address = context.args[0]

    # Validate token address format
    if not is_valid_solana_address(token_address):
        await update.message.reply_text(
            format_error("Invalid token address format."),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Get all tracked wallets
    wallets = await db.get_wallets()
    if not wallets:
        await update.message.reply_text(
            format_error("No wallets being tracked. Add wallets first with /add"),
            parse_mode=ParseMode.MARKDOWN_V2,
        )
        return

    # Send "searching" message for better UX
    searching_msg = await update.message.reply_text(
        f"🔍 Checking {len(wallets)} wallet{'s' if len(wallets) != 1 else ''}\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    # Get token info for display
    token_info = await get_token_info(token_address)
    token_symbol = token_info.symbol if token_info else "UNKNOWN"

    # Get token price for USD values
    token_price = await get_token_price(token_address)

    # Check which wallets hold this token
    wallet_list = [{"address": w["address"], "name": w["name"]} for w in wallets]
    holders = await helius_client.get_token_holders(token_address, wallet_list)

    # Format holder data with USD values
    holder_data = []
    for h in holders:
        usd_value = h.amount * token_price if token_price else None
        holder_data.append({
            "name": h.wallet_name,
            "amount": h.amount,
            "amount_formatted": format_amount(h.amount),
            "usd_value": usd_value,
            "usd_formatted": format_usd(usd_value) if usd_value else None,
        })

    # Delete the searching message
    await searching_msg.delete()

    # Send results
    await update.message.reply_text(
        format_whosinit(token_symbol, token_address, holder_data, len(wallets)),
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )
    logger.info(f"Whosinit query for {token_symbol}: {len(holders)}/{len(wallets)} wallets holding")


def create_bot_application() -> Application:
    """Create and configure the Telegram bot application."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    application.add_handler(CommandHandler("chatid", chatid_command))
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("remove", remove_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("rename", rename_command))
    application.add_handler(CommandHandler("whosinit", whosinit_command))

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
