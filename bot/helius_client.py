import httpx
from typing import Optional
import logging

from .config import HELIUS_API_KEY, HELIUS_API_URL, WEBHOOK_URL

logger = logging.getLogger(__name__)


class HeliusClient:
    """Client for managing Helius webhooks."""

    def __init__(self, api_key: str = HELIUS_API_KEY):
        self.api_key = api_key
        self.base_url = HELIUS_API_URL

    async def create_webhook(self, wallet_address: str) -> Optional[str]:
        """
        Create a Helius webhook to monitor a wallet address.
        Returns the webhook ID if successful, None otherwise.
        """
        url = f"{self.base_url}/webhooks?api-key={self.api_key}"

        payload = {
            "webhookURL": f"{WEBHOOK_URL}/helius",
            "transactionTypes": ["SWAP"],
            "accountAddresses": [wallet_address],
            "webhookType": "enhanced",
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()
                data = response.json()
                webhook_id = data.get("webhookID")
                logger.info(f"Created webhook {webhook_id} for wallet {wallet_address}")
                return webhook_id
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to create webhook: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Error creating webhook: {e}")
                return None

    async def delete_webhook(self, webhook_id: str) -> bool:
        """
        Delete a Helius webhook by ID.
        Returns True if successful, False otherwise.
        """
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
        """
        List all webhooks for this API key.
        Returns a list of webhook objects.
        """
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

    async def get_webhook(self, webhook_id: str) -> Optional[dict]:
        """
        Get details of a specific webhook.
        Returns the webhook object if found, None otherwise.
        """
        url = f"{self.base_url}/webhooks/{webhook_id}?api-key={self.api_key}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    return None
                logger.error(f"Failed to get webhook: {e.response.status_code} - {e.response.text}")
                return None
            except Exception as e:
                logger.error(f"Error getting webhook: {e}")
                return None

    async def update_webhook(
        self, webhook_id: str, wallet_addresses: list[str]
    ) -> bool:
        """
        Update a webhook with new wallet addresses.
        Returns True if successful, False otherwise.
        """
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
                logger.info(f"Updated webhook {webhook_id}")
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to update webhook: {e.response.status_code} - {e.response.text}")
                return False
            except Exception as e:
                logger.error(f"Error updating webhook: {e}")
                return False


# Global client instance
helius_client = HeliusClient()
