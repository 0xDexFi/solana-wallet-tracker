import httpx
import re
from typing import Optional
from dataclasses import dataclass
import logging

# DexScreener API is used for token info and pricing

logger = logging.getLogger(__name__)

# SOL mint address
SOL_MINT = "So11111111111111111111111111111111111111112"

# Common token cache to avoid repeated API calls
_token_cache: dict[str, "TokenInfo"] = {}


@dataclass
class TokenInfo:
    address: str
    symbol: str
    name: str
    decimals: int
    logo_uri: Optional[str] = None


async def get_token_info(mint_address: str) -> Optional[TokenInfo]:
    """
    Fetch token metadata from DexScreener API.
    Results are cached in memory.
    """
    # Check cache first
    if mint_address in _token_cache:
        return _token_cache[mint_address]

    # Handle native SOL
    if mint_address == SOL_MINT:
        token = TokenInfo(
            address=SOL_MINT,
            symbol="SOL",
            name="Solana",
            decimals=9,
        )
        _token_cache[mint_address] = token
        return token

    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            pairs = data.get("pairs", [])
            # Find Solana pair
            solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
            if solana_pairs:
                base_token = solana_pairs[0].get("baseToken", {})
                if base_token.get("address") == mint_address:
                    token = TokenInfo(
                        address=mint_address,
                        symbol=base_token.get("symbol", "UNKNOWN"),
                        name=base_token.get("name", "Unknown Token"),
                        decimals=6,  # Default for most SPL tokens
                    )
                    _token_cache[mint_address] = token
                    return token

            # If not found, return a basic token info
            return TokenInfo(
                address=mint_address,
                symbol="UNKNOWN",
                name="Unknown Token",
                decimals=6,
            )

        except Exception as e:
            logger.error(f"Error fetching token info: {e}")
            return None


async def get_token_price(mint_address: str) -> Optional[float]:
    """
    Get token price in USD from DexScreener API.
    """
    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint_address}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            pairs = data.get("pairs", [])
            # Find Solana pair with highest liquidity
            solana_pairs = [p for p in pairs if p.get("chainId") == "solana"]
            if solana_pairs:
                # Sort by liquidity and get the best one
                solana_pairs.sort(key=lambda x: x.get("liquidity", {}).get("usd", 0), reverse=True)
                price_str = solana_pairs[0].get("priceUsd")
                if price_str:
                    return float(price_str)
            return None

        except Exception as e:
            logger.error(f"Error fetching token price: {e}")
            return None


def format_amount(amount: float, decimals: int = 2) -> str:
    """
    Format a number with commas and specified decimal places.
    Handles large numbers nicely.
    """
    if amount >= 1_000_000_000:
        return f"{amount / 1_000_000_000:,.{decimals}f}B"
    elif amount >= 1_000_000:
        return f"{amount / 1_000_000:,.{decimals}f}M"
    elif amount >= 1_000:
        return f"{amount:,.{decimals}f}"
    elif amount >= 1:
        return f"{amount:,.{decimals}f}"
    else:
        # For very small numbers, show more decimals
        return f"{amount:,.6f}"


def format_usd(amount: float) -> str:
    """Format a USD amount."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:,.2f}M"
    elif amount >= 1_000:
        return f"${amount:,.2f}"
    elif amount >= 0.01:
        return f"${amount:,.2f}"
    else:
        return f"${amount:,.6f}"


def is_valid_solana_address(address: str) -> bool:
    """
    Validate a Solana address format.
    Solana addresses are base58 encoded and 32-44 characters long.
    """
    if not address or not isinstance(address, str):
        return False

    # Check length (32-44 characters)
    if len(address) < 32 or len(address) > 44:
        return False

    # Check for valid base58 characters (no 0, O, I, l)
    base58_pattern = re.compile(r"^[1-9A-HJ-NP-Za-km-z]+$")
    return bool(base58_pattern.match(address))


def shorten_address(address: str, chars: int = 4) -> str:
    """Shorten a Solana address for display."""
    if len(address) <= chars * 2 + 3:
        return address
    return f"{address[:chars]}...{address[-chars:]}"


def calculate_token_amount(raw_amount: int, decimals: int) -> float:
    """Convert raw token amount to human-readable amount."""
    return raw_amount / (10 ** decimals)

