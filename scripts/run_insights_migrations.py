"""Run all insights_*.sql migrations against the shared metadata DB.

Usage:
    docker exec jeen-insights-api python scripts/run_insights_migrations.py

The script is safe to run repeatedly: every migration uses
`CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, or
`CREATE OR REPLACE`.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is importable when the script runs as a CLI
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.metadata import get_metadata_pool, close_metadata_pool  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations" / "insights"


async def run() -> None:
    if not MIGRATIONS_DIR.is_dir():
        raise FileNotFoundError(f"Migrations directory not found: {MIGRATIONS_DIR}")

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not files:
        logger.warning("No migration files found in %s", MIGRATIONS_DIR)
        return

    pool = await get_metadata_pool()
    try:
        async with pool.acquire() as conn:
            for path in files:
                logger.info("→ Applying %s", path.name)
                sql = path.read_text(encoding="utf-8")
                async with conn.transaction():
                    await conn.execute(sql)
                logger.info("  ✅ %s applied", path.name)
    finally:
        await close_metadata_pool()

    logger.info("All Jeen Insights migrations applied successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(130)
    except Exception:  # noqa: BLE001
        logger.exception("Migration run failed")
        sys.exit(1)
