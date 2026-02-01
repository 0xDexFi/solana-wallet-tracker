import httpx
from typing import Optional
import logging

from .config import HELIUS_API_KEY, HELIUS_API_URL, WEBHOOK_URL

logger = logging.getLogger(__name__)

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


# Global client instance
helius_client = HeliusClient()
