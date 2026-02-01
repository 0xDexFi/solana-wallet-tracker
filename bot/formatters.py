from typing import Optional
from .config import SOLSCAN_TX_URL, SOLSCAN_TOKEN_URL
from .solana_utils import format_amount, format_usd, shorten_address


def format_buy_alert(
    wallet_name: str,
    wallet_address: str,
    token_symbol: str,
    token_address: str,
    amount: float,
    usd_value: Optional[float],
    signature: str,
) -> str:
    """Format a buy alert message."""
    lines = [
        "🟢 *BUY ALERT*",
        "",
        f"*Wallet:* {_escape_markdown(wallet_name)}",
        f"*Address:* `{shorten_address(wallet_address)}`",
        "",
        f"*Token:* ${_escape_markdown(token_symbol)}",
        f"*Amount:* {format_amount(amount)} {_escape_markdown(token_symbol)}",
    ]

    if usd_value is not None and usd_value > 0:
        lines.append(f"*Value:* {format_usd(usd_value)}")

    lines.extend([
        "",
        f"[View Transaction]({SOLSCAN_TX_URL}/{signature})",
        f"[View Token]({SOLSCAN_TOKEN_URL}/{token_address})",
    ])

    return "\n".join(lines)


def format_sell_alert(
    wallet_name: str,
    wallet_address: str,
    token_symbol: str,
    token_address: str,
    amount: float,
    usd_value: Optional[float],
    signature: str,
) -> str:
    """Format a sell alert message."""
    lines = [
        "🔴 *SELL ALERT*",
        "",
        f"*Wallet:* {_escape_markdown(wallet_name)}",
        f"*Address:* `{shorten_address(wallet_address)}`",
        "",
        f"*Token:* ${_escape_markdown(token_symbol)}",
        f"*Amount:* {format_amount(amount)} {_escape_markdown(token_symbol)}",
    ]

    if usd_value is not None and usd_value > 0:
        lines.append(f"*Value:* {format_usd(usd_value)}")

    lines.extend([
        "",
        f"[View Transaction]({SOLSCAN_TX_URL}/{signature})",
        f"[View Token]({SOLSCAN_TOKEN_URL}/{token_address})",
    ])

    return "\n".join(lines)


def format_wallet_list(wallets: list[dict]) -> str:
    """Format the list of tracked wallets."""
    if not wallets:
        return "📋 *No wallets being tracked*\n\nUse `/add <address> <name>` to start tracking a wallet."

    lines = ["📋 *Tracked Wallets*", ""]

    for i, wallet in enumerate(wallets, 1):
        name = _escape_markdown(wallet["name"])
        address = wallet["address"]
        short_addr = shorten_address(address)
        lines.append(f"{i}\\. *{name}*")
        lines.append(f"   `{short_addr}`")
        lines.append("")

    lines.append(f"_Total: {len(wallets)} wallet{'s' if len(wallets) != 1 else ''}_")

    return "\n".join(lines)


def format_wallet_added(name: str, address: str) -> str:
    """Format wallet added confirmation."""
    return (
        f"✅ *Wallet Added*\n\n"
        f"*Name:* {_escape_markdown(name)}\n"
        f"*Address:* `{shorten_address(address)}`\n\n"
        f"You will receive alerts when this wallet makes token swaps\\."
    )


def format_wallet_removed(name: str, address: str) -> str:
    """Format wallet removed confirmation."""
    return (
        f"✅ *Wallet Removed*\n\n"
        f"*Name:* {_escape_markdown(name)}\n"
        f"*Address:* `{shorten_address(address)}`\n\n"
        f"You will no longer receive alerts for this wallet\\."
    )


def format_wallet_renamed(old_name: str, new_name: str, address: str) -> str:
    """Format wallet renamed confirmation."""
    return (
        f"✅ *Wallet Renamed*\n\n"
        f"*From:* {_escape_markdown(old_name)}\n"
        f"*To:* {_escape_markdown(new_name)}\n"
        f"*Address:* `{shorten_address(address)}`"
    )


def format_error(message: str) -> str:
    """Format an error message."""
    return f"❌ *Error*\n\n{_escape_markdown(message)}"


def format_welcome() -> str:
    """Format the welcome message."""
    return (
        "👋 *Welcome to Solana Wallet Tracker\\!*\n\n"
        "I'll send you alerts when tracked wallets buy or sell tokens\\.\n\n"
        "*Commands:*\n"
        "• `/add <address> <name>` \\- Track a wallet\n"
        "• `/remove <address>` \\- Stop tracking\n"
        "• `/list` \\- Show tracked wallets\n"
        "• `/rename <address> <new_name>` \\- Rename a wallet\n\n"
        "_Get started by adding a wallet to track\\!_"
    )


def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
