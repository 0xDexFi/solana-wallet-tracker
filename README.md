# Solana Wallet Tracker Telegram Bot

A Python Telegram bot that tracks Solana wallets and sends real-time alerts when tracked wallets buy or sell tokens.

## Features

- Track multiple Solana wallets
- Real-time buy/sell alerts via Telegram
- Token metadata and USD prices from Jupiter API
- Persistent storage with SQLite

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Telegram Bot   │────▶│   SQLite DB     │◀────│  FastAPI Server │
│  (Commands)     │     │  (Wallets)      │     │  (Webhooks)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        ▲
                                                        │
                                               ┌─────────────────┐
                                               │  Helius API     │
                                               │  (Monitoring)   │
                                               └─────────────────┘
```

## Prerequisites

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Helius API Key (from [helius.dev](https://helius.dev))
- Public URL for webhook (use ngrok for local development)

## Installation

1. Clone the repository and navigate to the project directory:

```bash
cd "TG BOT"
```

2. Create a virtual environment and activate it:

```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

5. Edit `.env` with your configuration:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
HELIUS_API_KEY=your_helius_api_key_here
WEBHOOK_URL=https://your-domain.com
TELEGRAM_CHAT_ID=your_chat_id_here
```

## Getting Your Telegram Chat ID

1. Start a chat with [@userinfobot](https://t.me/userinfobot) on Telegram
2. It will reply with your user ID - use this as `TELEGRAM_CHAT_ID`

## Local Development with ngrok

For local development, you need a public URL for Helius webhooks:

1. Install [ngrok](https://ngrok.com/download)
2. Run ngrok to expose port 8000:

```bash
ngrok http 8000
```

3. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`) and set it as `WEBHOOK_URL` in your `.env` file

## Running the Bot

```bash
python -m bot.main
```

The bot will start both the Telegram bot and the webhook server on port 8000.

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and instructions |
| `/add <address> <name>` | Add a wallet to track |
| `/remove <address>` | Stop tracking a wallet |
| `/list` | Show all tracked wallets |
| `/rename <address> <new_name>` | Rename a tracked wallet |

## Alert Format

When a tracked wallet makes a swap, you'll receive an alert like this:

```
🟢 BUY ALERT

Wallet: Smart Money #1
Address: 7xKX...4nPq

Token: $BONK
Amount: 1,500,000 BONK
Value: $1,234.56

🔗 View Transaction
🔗 View Token
```

## Project Structure

```
TG BOT/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Entry point
│   ├── config.py            # Configuration
│   ├── database.py          # SQLite operations
│   ├── telegram_bot.py      # Telegram handlers
│   ├── webhook_server.py    # FastAPI server
│   ├── helius_client.py     # Helius API client
│   ├── solana_utils.py      # Token utilities
│   └── formatters.py        # Message formatting
├── requirements.txt
├── .env.example
└── README.md
```

## Deployment

For production deployment:

1. Deploy to a VPS or cloud server (e.g., AWS, DigitalOcean, Railway)
2. Set up a reverse proxy (nginx) with SSL
3. Configure the public URL as `WEBHOOK_URL`
4. Run with a process manager (e.g., systemd, PM2)

Example systemd service:

```ini
[Unit]
Description=Solana Wallet Tracker Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/TG BOT
Environment=PATH=/path/to/venv/bin
ExecStart=/path/to/venv/bin/python -m bot.main
Restart=always

[Install]
WantedBy=multi-user.target
```

## API Keys

### Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the token provided

### Helius API Key

1. Go to [helius.dev](https://helius.dev)
2. Create a free account
3. Copy your API key from the dashboard

Free tier includes 100,000 credits/month which is sufficient for most use cases.

## License

MIT
