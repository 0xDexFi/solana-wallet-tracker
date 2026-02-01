import asyncio
import logging
import sys
import uvicorn
from contextlib import asynccontextmanager

from .config import validate_config, WEBHOOK_PORT
from .database import db
from .telegram_bot import create_bot_application
from .webhook_server import app as fastapi_app

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def run_telegram_bot():
    """Run the Telegram bot."""
    application = create_bot_application()

    # Initialize and start the bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

    logger.info("Telegram bot started")

    # Keep running until cancelled
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("Telegram bot stopped")


async def run_webhook_server():
    """Run the FastAPI webhook server."""
    config = uvicorn.Config(
        fastapi_app,
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)

    logger.info(f"Webhook server starting on port {WEBHOOK_PORT}")

    try:
        await server.serve()
    except asyncio.CancelledError:
        pass
    finally:
        logger.info("Webhook server stopped")


async def main():
    """Main entry point - runs both bot and webhook server concurrently."""
    # Validate configuration
    errors = validate_config()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        sys.exit(1)

    # Initialize database
    await db.connect()
    logger.info("Database initialized")

    try:
        # Run both services concurrently
        bot_task = asyncio.create_task(run_telegram_bot())
        server_task = asyncio.create_task(run_webhook_server())

        logger.info("All services started")

        # Wait for both tasks (or until one fails)
        done, pending = await asyncio.wait(
            [bot_task, server_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        # If one task completed (likely due to error), cancel the other
        for task in pending:
            task.cancel()

        # Check for exceptions
        for task in done:
            if task.exception():
                logger.error(f"Task failed with exception: {task.exception()}")

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await db.close()
        logger.info("Shutdown complete")


def run():
    """Entry point for running the application."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
