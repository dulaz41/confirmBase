#!/usr/bin/env python3
"""
Database Backup Restore and Verification Script
Restores a PostgreSQL backup archive (or SQLite dump in test mode) to a target database,
and verifies schema and records.
"""
from __future__ import annotations

import argparse
import gzip
import logging
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.services.backup_service import BackupService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("restore_script")


def restore_backup(backup_path: Path, target_db_url: str, encryption_key: str | None = None) -> bool:
    """
    Restores the specified backup file to target_db_url.
    Returns True if successfully restored and verified.
    """
    if not backup_path.exists():
        logger.error(f"Backup file not found: {backup_path}")
        return False

    temp_decompressed: Path | None = None
    service = BackupService(base_dir=str(backup_path.parent))

    try:
        # 1. Handle decryption if needed
        work_file = backup_path
        if backup_path.name.endswith(".enc"):
            if not encryption_key:
                raise ValueError("Backup is encrypted but no encryption key was provided.")
            logger.info("Decrypting backup archive...")
            work_file = service.decrypt_file(backup_path, encryption_key)

        # 2. Decompress gzip
        if work_file.name.endswith(".gz"):
            temp_decompressed = work_file.with_suffix("")
            logger.info(f"Decompressing {work_file.name} to {temp_decompressed.name}...")
            with gzip.open(work_file, "rb") as f_in:
                with open(temp_decompressed, "wb") as f_out:
                    f_out.write(f_in.read())
            sql_file = temp_decompressed
        else:
            sql_file = work_file

        # 3. Restore to target database
        logger.info(f"Restoring SQL contents to target database: {target_db_url}...")
        if target_db_url.startswith("sqlite"):
            sqlite_path = target_db_url.replace("sqlite:///", "").replace("sqlite://", "")
            import sqlite3
            conn = sqlite3.connect(sqlite_path)
            try:
                # If sql_file is binary sqlite db file
                if sql_file.name.endswith(".sqlite"):
                    import shutil
                    conn.close()
                    shutil.copyfile(sql_file, sqlite_path)
                else:
                    conn.executescript(sql_file.read_text(encoding="utf-8"))
                    conn.commit()
                    conn.close()
            except Exception as exc:
                logger.error(f"SQLite restore failed: {exc}")
                return False
        else:
            # PostgreSQL restore via psql
            parsed = urlparse(target_db_url)
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password

            cmd = [
                "psql",
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres",
                "-d", parsed.path.lstrip("/"),
                "-f", str(sql_file),
            ]

            process = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            if process.returncode != 0:
                err_msg = process.stderr.decode(errors="replace")
                logger.error(f"psql restore failed (code {process.returncode}): {err_msg}")
                return False

        # 4. Verify restore integrity
        logger.info("Verifying restored database integrity...")
        if target_db_url.startswith("sqlite"):
            sqlite_path = target_db_url.replace("sqlite:///", "").replace("sqlite://", "")
            import sqlite3
            conn = sqlite3.connect(sqlite_path)
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM waitlist_entries;")
            count = cur.fetchone()[0]
            conn.close()
            logger.info(f"Verification successful! 'waitlist_entries' exists and contains {count} records.")
        else:
            import psycopg2
            parsed = urlparse(target_db_url)
            conn = psycopg2.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                user=parsed.username or "postgres",
                password=parsed.password,
                dbname=parsed.path.lstrip("/"),
            )
            cur = conn.cursor()
            cur.execute("SELECT count(*) FROM waitlist_entries;")
            count = cur.fetchone()[0]
            conn.close()
            logger.info(f"Verification successful! 'waitlist_entries' exists and contains {count} records.")

        return True

    except Exception as exc:
        logger.error(f"Restore failed with exception: {exc}", exc_info=True)
        return False
    finally:
        # Cleanup temporary uncompressed file
        if temp_decompressed and temp_decompressed.exists():
            try:
                temp_decompressed.unlink()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Restore PostgreSQL Waitlist Backup")
    parser.add_argument(
        "--backup-file",
        required=True,
        type=Path,
        help="Path to the backup file (.sql.gz or .sql.gz.enc)",
    )
    parser.add_argument(
        "--target-db",
        default=settings.sync_db_url,
        help="Target database connection string (default: current settings.SYNC_DATABASE_URL)",
    )
    parser.add_argument(
        "--encryption-key",
        default=settings.BACKUP_ENCRYPTION_KEY,
        help="Fernet decryption key (if backup is encrypted)",
    )
    args = parser.parse_args()

    success = restore_backup(
        backup_path=args.backup_file,
        target_db_url=args.target_db,
        encryption_key=args.encryption_key,
    )

    if not success:
        sys.exit(1)
    logger.info("Database restore completed and verified successfully.")


if __name__ == "__main__":
    main()
