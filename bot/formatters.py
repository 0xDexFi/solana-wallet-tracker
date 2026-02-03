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
        f"*Address:* `{wallet_address}`",
        "",
        f"*Token:* ${_escape_markdown(token_symbol)}",
        f"*Amount:* {_escape_markdown(format_amount(amount))} {_escape_markdown(token_symbol)}",
    ]

    if usd_value is not None and usd_value > 0:
        lines.append(f"*Value:* {_escape_markdown(format_usd(usd_value))}")

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
        f"*Address:* `{wallet_address}`",
        "",
        f"*Token:* ${_escape_markdown(token_symbol)}",
        f"*Amount:* {_escape_markdown(format_amount(amount))} {_escape_markdown(token_symbol)}",
    ]

    if usd_value is not None and usd_value > 0:
        lines.append(f"*Value:* {_escape_markdown(format_usd(usd_value))}")

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
        lines.append(f"{i}\\. *{name}*")
        lines.append(f"`{address}`")
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
        "• `/rename <address> <new_name>` \\- Rename a wallet\n"
        "• `/whosinit <token>` \\- See who holds a token\n\n"
        "_Get started by adding a wallet to track\\!_"
    )


def format_whosinit(
    token_symbol: str,
    token_address: str,
    holders: list[dict],  # List of {name, amount, usd_value}
    total_wallets: int,
) -> str:
    """Format the whosinit response showing which wallets hold a token."""
    if not holders:
        return (
            f"📊 *Who's holding {_escape_markdown(token_symbol)}*\n\n"
            f"_No tracked wallets currently hold this token\\._\n\n"
            f"Token: `{token_address[:8]}...{token_address[-4:]}`"
        )

    lines = [
        f"📊 *Who's holding {_escape_markdown(token_symbol)}*",
        "",
    ]

    total_usd = 0
    for holder in holders:
        amount_str = _escape_markdown(holder["amount_formatted"])
        line = f"💰 *{_escape_markdown(holder['name'])}* — {amount_str}"

        if holder.get("usd_value") and holder["usd_value"] > 0:
            usd_str = _escape_markdown(holder["usd_formatted"])
            line += f" \\({usd_str}\\)"
            total_usd += holder["usd_value"]

        lines.append(line)

    lines.append("")

    # Summary line
    holder_count = len(holders)
    summary = f"{holder_count} of {total_wallets} tracked wallet{'s' if total_wallets != 1 else ''}"

    if total_usd > 0:
        total_usd_str = _escape_markdown(f"${total_usd:,.2f}")
        summary += f" • {total_usd_str} total"

    lines.append(f"_{summary}_")

    # Add token link
    lines.append("")
    lines.append(f"[View Token]({SOLSCAN_TOKEN_URL}/{token_address})")

    return "\n".join(lines)


def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2."""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
