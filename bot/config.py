import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Telegram configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Helius configuration
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
HELIUS_API_URL = "https://api.helius.xyz/v0"

# Webhook configuration
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://localhost:8000")
WEBHOOK_PORT = int(os.getenv("PORT", os.getenv("WEBHOOK_PORT", "8000")))

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "wallets.db"))

# Jupiter API for token data
JUPITER_API_URL = "https://api.jup.ag"

# Solscan base URL for transaction links
SOLSCAN_TX_URL = "https://solscan.io/tx"
SOLSCAN_TOKEN_URL = "https://solscan.io/token"


def validate_config() -> list[str]:
    """Validate that required configuration is present."""
    errors = []

    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN is required")

    if not HELIUS_API_KEY:
        errors.append("HELIUS_API_KEY is required")

    if not TELEGRAM_CHAT_ID:
        errors.append("TELEGRAM_CHAT_ID is required")

    return errors
