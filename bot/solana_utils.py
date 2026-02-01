import httpx
import re
from typing import Optional
from dataclasses import dataclass
import logging

from .config import JUPITER_API_URL

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
    Fetch token metadata from Jupiter API.
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

    url = f"{JUPITER_API_URL}/tokens/v1/strict"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            tokens = response.json()

            # Find the token in the list
            for token_data in tokens:
                if token_data.get("address") == mint_address:
                    token = TokenInfo(
                        address=mint_address,
                        symbol=token_data.get("symbol", "UNKNOWN"),
                        name=token_data.get("name", "Unknown Token"),
                        decimals=token_data.get("decimals", 9),
                        logo_uri=token_data.get("logoURI"),
                    )
                    _token_cache[mint_address] = token
                    return token

            # Token not in strict list, try all tokens endpoint
            return await _get_token_from_all(mint_address)

        except Exception as e:
            logger.error(f"Error fetching token info: {e}")
            return None


async def _get_token_from_all(mint_address: str) -> Optional[TokenInfo]:
    """Fetch token info from the all tokens endpoint."""
    url = f"{JUPITER_API_URL}/tokens/v1/token/{mint_address}"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            token_data = response.json()

            token = TokenInfo(
                address=mint_address,
                symbol=token_data.get("symbol", "UNKNOWN"),
                name=token_data.get("name", "Unknown Token"),
                decimals=token_data.get("decimals", 9),
                logo_uri=token_data.get("logoURI"),
            )
            _token_cache[mint_address] = token
            return token

        except Exception as e:
            logger.error(f"Error fetching token from all endpoint: {e}")
            return None


async def get_token_price(mint_address: str) -> Optional[float]:
    """
    Get token price in USD from Jupiter Price API.
    """
    url = f"{JUPITER_API_URL}/price/v2"
    params = {"ids": mint_address}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()

            price_data = data.get("data", {}).get(mint_address)
            if price_data:
                return float(price_data.get("price", 0))
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
