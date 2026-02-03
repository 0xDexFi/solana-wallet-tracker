import httpx
import asyncio
from typing import Optional
from dataclasses import dataclass
import logging

from .config import HELIUS_API_KEY, HELIUS_API_URL, WEBHOOK_URL

logger = logging.getLogger(__name__)

# Rate limiting: max concurrent requests to avoid hitting API limits
MAX_CONCURRENT_REQUESTS = 10


@dataclass
class TokenBalance:
    """Token balance for a wallet."""
    wallet_address: str
    wallet_name: str
    mint: str
    amount: float  # Human-readable amount
    decimals: int

# Store the shared webhook ID
_shared_webhook_id: Optional[str] = None


class HeliusClient:
    """Client for managing Helius webhooks."""

    def __init__(self, api_key: str = HELIUS_API_KEY):
        self.api_key = api_key
        self.base_url = HELIUS_API_URL

    async def get_or_create_shared_webhook(self) -> Optional[str]:
        """
        Get existing webhook or create a new one.
        Uses a single webhook for all tracked wallets.
        """
        global _shared_webhook_id

        if _shared_webhook_id:
            return _shared_webhook_id

        # Check for existing webhooks
        webhooks = await self.list_webhooks()
        for webhook in webhooks:
            if webhook.get("webhookURL", "").endswith("/helius"):
                _shared_webhook_id = webhook.get("webhookID")
                logger.info(f"Using existing webhook: {_shared_webhook_id}")
                return _shared_webhook_id

        # Create new webhook with empty address list (will be updated when wallets added)
        webhook_id = await self._create_webhook([])
        if webhook_id:
            _shared_webhook_id = webhook_id
        return webhook_id

    async def _create_webhook(self, wallet_addresses: list[str]) -> Optional[str]:
        """Create a new Helius webhook."""
        url = f"{self.base_url}/webhooks?api-key={self.api_key}"

        payload = {
            "webhookURL": f"{WEBHOOK_URL}/helius",
            "transactionTypes": ["SWAP"],
            "accountAddresses": wallet_addresses if wallet_addresses else ["11111111111111111111111111111111"],  # Placeholder if empty
            "webhookType": "enhanced",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                webhook_id = data.get("webhookID")
                logger.info(f"Created webhook {webhook_id}")
                return webhook_id
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to create webhook: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Error creating webhook: {e}")
                return None

    async def add_wallet_to_webhook(self, wallet_address: str, all_addresses: list[str]) -> bool:
        """
        Add a wallet address to the shared webhook.
        all_addresses should include the new wallet.
        """
        global _shared_webhook_id

        webhook_id = await self.get_or_create_shared_webhook()
        if not webhook_id:
            return False

        return await self.update_webhook(webhook_id, all_addresses)

    async def remove_wallet_from_webhook(self, remaining_addresses: list[str]) -> bool:
        """
        Update webhook with remaining addresses after removal.
        """
        global _shared_webhook_id

        if not _shared_webhook_id:
            return True  # No webhook to update

        if not remaining_addresses:
            # No wallets left, use placeholder
            remaining_addresses = ["11111111111111111111111111111111"]

        return await self.update_webhook(_shared_webhook_id, remaining_addresses)

    async def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a Helius webhook by ID."""
        url = f"{self.base_url}/webhooks/{webhook_id}?api-key={self.api_key}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(url, timeout=30.0)
                response.raise_for_status()
                logger.info(f"Deleted webhook {webhook_id}")
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to delete webhook: {e.response.status_code} - {e.response.text}")
                return False
            except Exception as e:
                logger.error(f"Error deleting webhook: {e}")
                return False

    async def list_webhooks(self) -> list[dict]:
        """List all webhooks for this API key."""
        url = f"{self.base_url}/webhooks?api-key={self.api_key}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                webhooks = response.json()
                return webhooks if isinstance(webhooks, list) else []
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to list webhooks: {e.response.status_code} - {e.response.text}")
                return []
            except Exception as e:
                logger.error(f"Error listing webhooks: {e}")
                return []

    async def update_webhook(self, webhook_id: str, wallet_addresses: list[str]) -> bool:
        """Update a webhook with new wallet addresses."""
        url = f"{self.base_url}/webhooks/{webhook_id}?api-key={self.api_key}"

        payload = {
            "webhookURL": f"{WEBHOOK_URL}/helius",
            "transactionTypes": ["SWAP"],
            "accountAddresses": wallet_addresses,
            "webhookType": "enhanced",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.put(url, json=payload, timeout=30.0)
                response.raise_for_status()
                logger.info(f"Updated webhook {webhook_id} with {len(wallet_addresses)} addresses")
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to update webhook: {e.response.status_code} - {e.response.text}")
                return False
            except Exception as e:
                logger.error(f"Error updating webhook: {e}")
                return False

    async def get_wallet_balances(self, wallet_address: str) -> list[dict]:
        """
        Get all token balances for a wallet using Helius RPC.
        Returns list of {mint, amount, decimals} for each token held.
        """
        # Use Helius RPC endpoint for more reliable results
        rpc_url = f"https://mainnet.helius-rpc.com/?api-key={self.api_key}"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                wallet_address,
                {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                {"encoding": "jsonParsed"}
            ]
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(rpc_url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()

                if "error" in data:
                    logger.error(f"RPC error for {wallet_address}: {data['error']}")
                    return []

                balances = []
                accounts = data.get("result", {}).get("value", [])
                for account in accounts:
                    parsed = account.get("account", {}).get("data", {}).get("parsed", {})
                    info = parsed.get("info", {})
                    token_amount = info.get("tokenAmount", {})

                    mint = info.get("mint")
                    amount = int(token_amount.get("amount", "0"))
                    decimals = token_amount.get("decimals", 6)

                    if mint and amount > 0:
                        balances.append({
                            "mint": mint,
                            "amount": amount,
                            "decimals": decimals,
                        })
                return balances

            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to get balances for {wallet_address}: {e.response.status_code}")
                return []
            except Exception as e:
                logger.error(f"Error getting balances for {wallet_address}: {e}")
                return []

    async def get_token_holders(
        self,
        token_mint: str,
        wallets: list[dict],  # List of {address, name}
    ) -> list[TokenBalance]:
        """
        Check which wallets from the list hold a specific token.
        Uses parallel requests with rate limiting.

        Args:
            token_mint: The token mint address to check
            wallets: List of wallet dicts with 'address' and 'name' keys

        Returns:
            List of TokenBalance for wallets that hold the token
        """
        holders = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        async def check_wallet(wallet: dict) -> Optional[TokenBalance]:
            async with semaphore:
                balances = await self.get_wallet_balances(wallet["address"])
                logger.info(f"Wallet {wallet['name']} has {len(balances)} token accounts")
                for bal in balances:
                    if bal["mint"] == token_mint:
                        # Convert raw amount to human-readable
                        decimals = bal["decimals"]
                        human_amount = bal["amount"] / (10 ** decimals)
                        logger.info(f"Found token in {wallet['name']}: {human_amount} (raw={bal['amount']})")
                        return TokenBalance(
                            wallet_address=wallet["address"],
                            wallet_name=wallet["name"],
                            mint=token_mint,
                            amount=human_amount,
                            decimals=decimals,
                        )
                return None

        # Run all checks in parallel with rate limiting
        tasks = [check_wallet(w) for w in wallets]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, TokenBalance):
                holders.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Error checking wallet: {result}")

        # Sort by amount descending
        holders.sort(key=lambda x: x.amount, reverse=True)
        return holders


# Global client instance
helius_client = HeliusClient()
