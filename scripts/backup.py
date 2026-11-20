#!/usr/bin/env python3
"""
Automated Backup Script
Can be run via cron, Docker scheduled container, or manually.
Executes both PostgreSQL pg_dump backup and CSV email snapshot.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.backup_service import BackupService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("backup_script")


async def main():
    parser = argparse.ArgumentParser(description="Waitlist Database & CSV Backup Utility")
    parser.add_argument(
        "--csv-only", action="store_true", help="Generate only CSV snapshot"
    )
    parser.add_argument(
        "--db-only", action="store_true", help="Generate only PostgreSQL database dump"
    )
    args = parser.parse_args()

    service = BackupService()
    logger.info("Starting waitlist backup execution...")

    try:
        if args.csv_only:
            csv_path = await service.create_csv_snapshot()
            service.enforce_retention(service.csv_dir, settings.BACKUP_RETENTION_DAYS)
            logger.info(f"CSV snapshot completed successfully: {csv_path}")
        elif args.db_only:
            db_path = await service.create_database_backup()
            service.enforce_retention(service.postgres_dir, settings.BACKUP_RETENTION_DAYS)
            logger.info(f"Database backup completed successfully: {db_path}")
        else:
            csv_path, db_path = await service.run_full_backup()
            logger.info("Full backup cycle (CSV + DB) completed successfully.")
            if csv_path:
                logger.info(f" - CSV snapshot: {csv_path}")
            if db_path:
                logger.info(f" - Database backup: {db_path}")
    except Exception as exc:
        logger.error(f"Backup execution failed: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
