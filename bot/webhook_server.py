import logging
from typing import Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from .database import db
from .solana_utils import (
    get_token_info,
    get_token_price,
    calculate_token_amount,
    SOL_MINT,
)
from .formatters import format_buy_alert, format_sell_alert
from .telegram_bot import send_alert

logger = logging.getLogger(__name__)

app = FastAPI(title="Solana Wallet Tracker Webhook Server")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/helius")
async def helius_webhook(request: Request):
    """
    Handle incoming Helius webhook notifications.
    Helius sends an array of enhanced transaction objects.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Helius sends an array of transactions
    if not isinstance(payload, list):
        payload = [payload]

    for tx in payload:
        await process_transaction(tx)

    return JSONResponse(content={"status": "ok"})


async def process_transaction(tx: dict[str, Any]) -> None:
    """Process a single enhanced transaction from Helius."""
    try:
        signature = tx.get("signature")
        if not signature:
            logger.warning("Transaction missing signature")
            return

        # Check if we've already processed this transaction
        if await db.transaction_exists(signature):
            logger.debug(f"Transaction {signature} already processed")
            return

        # Get transaction type and details
        tx_type = tx.get("type")
        if tx_type != "SWAP":
            logger.debug(f"Ignoring non-swap transaction: {tx_type}")
            return

        # Extract swap details from the transaction
        await process_swap_transaction(tx)

    except Exception as e:
        logger.error(f"Error processing transaction: {e}", exc_info=True)


async def process_swap_transaction(tx: dict[str, Any]) -> None:
    """Process a swap transaction and send alerts."""
    signature = tx.get("signature")
    fee_payer = tx.get("feePayer")

    # Check if we're tracking this wallet
    wallet = await db.get_wallet(fee_payer)
    if not wallet:
        # Also check account keys for the tracked wallet
        account_data = tx.get("accountData", [])
        for account in account_data:
            account_addr = account.get("account")
            if account_addr:
                wallet = await db.get_wallet(account_addr)
                if wallet:
                    fee_payer = account_addr
                    break

    if not wallet:
        logger.debug(f"Transaction from untracked wallet")
        return

    # Extract swap info from token transfers
    token_transfers = tx.get("tokenTransfers", [])
    native_transfers = tx.get("nativeTransfers", [])

    # Analyze the swap direction
    swap_info = analyze_swap(fee_payer, token_transfers, native_transfers)

    if not swap_info:
        logger.warning(f"Could not analyze swap for tx {signature}")
        return

    tx_type = swap_info["type"]
    token_address = swap_info["token_address"]
    amount = swap_info["amount"]

    # Get token info
    token_info = await get_token_info(token_address)
    token_symbol = token_info.symbol if token_info else "UNKNOWN"
    decimals = token_info.decimals if token_info else 9

    # Calculate human-readable amount
    if swap_info.get("raw_amount"):
        amount = calculate_token_amount(swap_info["raw_amount"], decimals)

    # Get USD value
    usd_value = None
    price = await get_token_price(token_address)
    if price:
        usd_value = amount * price

    # Record transaction
    await db.add_transaction(
        wallet_address=fee_payer,
        signature=signature,
        tx_type=tx_type,
        token_address=token_address,
        token_symbol=token_symbol,
        amount=amount,
        usd_value=usd_value,
    )

    # Format and send alert
    if tx_type == "buy":
        message = format_buy_alert(
            wallet_name=wallet["name"],
            wallet_address=fee_payer,
            token_symbol=token_symbol,
            token_address=token_address,
            amount=amount,
            usd_value=usd_value,
            signature=signature,
        )
    else:
        message = format_sell_alert(
            wallet_name=wallet["name"],
            wallet_address=fee_payer,
            token_symbol=token_symbol,
            token_address=token_address,
            amount=amount,
            usd_value=usd_value,
            signature=signature,
        )

    await send_alert(message)
    logger.info(f"Sent {tx_type} alert for {wallet['name']}: {token_symbol}")


def analyze_swap(
    wallet_address: str,
    token_transfers: list[dict],
    native_transfers: list[dict],
) -> dict[str, Any] | None:
    """
    Analyze token and native transfers to determine swap direction.

    Returns:
        dict with keys: type ('buy' or 'sell'), token_address, amount, raw_amount
        or None if cannot determine
    """
    # Track what the wallet sent and received
    tokens_sent = []
    tokens_received = []

    for transfer in token_transfers:
        mint = transfer.get("mint")
        from_addr = transfer.get("fromUserAccount")
        to_addr = transfer.get("toUserAccount")
        amount = transfer.get("tokenAmount", 0)

        if from_addr == wallet_address:
            tokens_sent.append({
                "mint": mint,
                "amount": amount,
            })
        elif to_addr == wallet_address:
            tokens_received.append({
                "mint": mint,
                "amount": amount,
            })

    # Check native SOL transfers
    sol_sent = 0
    sol_received = 0

    for transfer in native_transfers:
        from_addr = transfer.get("fromUserAccount")
        to_addr = transfer.get("toUserAccount")
        amount = transfer.get("amount", 0)

        if from_addr == wallet_address:
            sol_sent += amount
        elif to_addr == wallet_address:
            sol_received += amount

    # Determine swap type
    # Buy: wallet sends SOL (or stablecoin), receives token
    # Sell: wallet sends token, receives SOL (or stablecoin)

    # If received a non-SOL token and sent SOL/stablecoin -> BUY
    for received in tokens_received:
        if received["mint"] != SOL_MINT:
            return {
                "type": "buy",
                "token_address": received["mint"],
                "amount": received["amount"],
                "raw_amount": None,
            }

    # If sent a non-SOL token and received SOL/stablecoin -> SELL
    for sent in tokens_sent:
        if sent["mint"] != SOL_MINT:
            return {
                "type": "sell",
                "token_address": sent["mint"],
                "amount": sent["amount"],
                "raw_amount": None,
            }

    # If only SOL transfers, check direction
    if sol_received > sol_sent and tokens_sent:
        # Sold tokens for SOL
        return {
            "type": "sell",
            "token_address": tokens_sent[0]["mint"],
            "amount": tokens_sent[0]["amount"],
            "raw_amount": None,
        }
    elif sol_sent > sol_received and tokens_received:
        # Bought tokens with SOL
        return {
            "type": "buy",
            "token_address": tokens_received[0]["mint"],
            "amount": tokens_received[0]["amount"],
            "raw_amount": None,
        }

    return None
