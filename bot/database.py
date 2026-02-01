import aiosqlite
from pathlib import Path
from datetime import datetime
from typing import Optional

from .config import DATABASE_PATH


class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Initialize database connection and create tables."""
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._create_tables()

    async def close(self):
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def _create_tables(self):
        """Create database tables if they don't exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                helius_webhook_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                signature TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                token_address TEXT,
                token_symbol TEXT,
                amount REAL,
                usd_value REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_wallets_address ON wallets(address);
            CREATE INDEX IF NOT EXISTS idx_transactions_wallet ON transactions(wallet_address);
            CREATE INDEX IF NOT EXISTS idx_transactions_signature ON transactions(signature);
        """)
        await self._connection.commit()

    async def add_wallet(
        self, address: str, name: str, webhook_id: Optional[str] = None
    ) -> bool:
        """Add a wallet to track. Returns True if added, False if already exists."""
        try:
            await self._connection.execute(
                "INSERT INTO wallets (address, name, helius_webhook_id) VALUES (?, ?, ?)",
                (address, name, webhook_id),
            )
            await self._connection.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def remove_wallet(self, address: str) -> Optional[str]:
        """Remove a wallet. Returns the webhook_id if it existed."""
        cursor = await self._connection.execute(
            "SELECT helius_webhook_id FROM wallets WHERE address = ?", (address,)
        )
        row = await cursor.fetchone()

        if row:
            webhook_id = row["helius_webhook_id"]
            await self._connection.execute(
                "DELETE FROM wallets WHERE address = ?", (address,)
            )
            await self._connection.commit()
            return webhook_id
        return None

    async def get_wallet(self, address: str) -> Optional[dict]:
        """Get a single wallet by address."""
        cursor = await self._connection.execute(
            "SELECT * FROM wallets WHERE address = ?", (address,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_wallets(self) -> list[dict]:
        """Get all tracked wallets."""
        cursor = await self._connection.execute(
            "SELECT * FROM wallets ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def rename_wallet(self, address: str, new_name: str) -> bool:
        """Rename a wallet. Returns True if updated, False if not found."""
        cursor = await self._connection.execute(
            "UPDATE wallets SET name = ? WHERE address = ?", (new_name, address)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def update_wallet_webhook_id(self, address: str, webhook_id: str) -> bool:
        """Update the webhook ID for a wallet."""
        cursor = await self._connection.execute(
            "UPDATE wallets SET helius_webhook_id = ? WHERE address = ?",
            (webhook_id, address),
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def add_transaction(
        self,
        wallet_address: str,
        signature: str,
        tx_type: str,
        token_address: Optional[str] = None,
        token_symbol: Optional[str] = None,
        amount: Optional[float] = None,
        usd_value: Optional[float] = None,
    ) -> bool:
        """Add a transaction record. Returns True if added, False if duplicate."""
        try:
            await self._connection.execute(
                """INSERT INTO transactions
                   (wallet_address, signature, type, token_address, token_symbol, amount, usd_value)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (wallet_address, signature, tx_type, token_address, token_symbol, amount, usd_value),
            )
            await self._connection.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def get_transactions(
        self, wallet_address: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """Get recent transactions, optionally filtered by wallet."""
        if wallet_address:
            cursor = await self._connection.execute(
                """SELECT * FROM transactions
                   WHERE wallet_address = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (wallet_address, limit),
            )
        else:
            cursor = await self._connection.execute(
                "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def transaction_exists(self, signature: str) -> bool:
        """Check if a transaction has already been processed."""
        cursor = await self._connection.execute(
            "SELECT 1 FROM transactions WHERE signature = ?", (signature,)
        )
        return await cursor.fetchone() is not None


# Global database instance
db = Database()
