from __future__ import annotations

import os
import sys
import gzip
import shutil
import logging
import asyncio
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, List, Optional, Tuple
from urllib.parse import urlparse

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.services.csv_service import CSVExportService

logger = logging.getLogger("waitlist.backup")
audit_logger = logging.getLogger("waitlist.audit")


class BackupService:
    def __init__(self, base_dir: Optional[str] = None, session_factory: Optional[Any] = None):
        self.base_dir = Path(base_dir or settings.BACKUP_DIRECTORY)
        self.postgres_dir = self.base_dir / "postgres"
        self.csv_dir = self.base_dir / "csv"
        self.session_factory = session_factory or AsyncSessionLocal
        self._ensure_directories()

    def _ensure_directories(self):
        """Creates backup directories if they don't exist."""
        self.postgres_dir.mkdir(parents=True, exist_ok=True)
        self.csv_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_timestamp_str() -> str:
        """Returns standard UTC timestamp string for backup filenames."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")

    async def create_csv_snapshot(self) -> Path:
        """
        Exports a complete snapshot of waitlist emails to a timestamped CSV file.
        Verifies file existence and integrity.
        """
        timestamp = self.get_timestamp_str()
        target_file = self.csv_dir / f"waitlist_{timestamp}.csv"

        try:
            async with self.session_factory() as session:
                csv_content = await CSVExportService.export_to_string(session)

            # Write file using UTF-8
            target_file.write_text(csv_content, encoding="utf-8")

            # Verify file was written and is not empty
            if not target_file.exists() or target_file.stat().st_size == 0:
                raise RuntimeError(f"CSV snapshot generated empty file: {target_file}")

            # Optional encryption
            if settings.BACKUP_ENCRYPTION_KEY:
                target_file = self.encrypt_file(target_file, settings.BACKUP_ENCRYPTION_KEY)

            logger.info(f"CSV snapshot created: {target_file.name} ({target_file.stat().st_size} bytes)")
            return target_file
        except Exception as exc:
            logger.error(f"Failed to create CSV snapshot: {exc}", exc_info=True)
            raise

    async def create_database_backup(self) -> Path:
        """
        Creates a compressed database dump using pg_dump.
        If running with SQLite (e.g., test environment), creates a SQLite dump.
        Verifies file existence and integrity.
        """
        timestamp = self.get_timestamp_str()
        db_url = settings.sync_db_url

        if db_url.startswith("sqlite"):
            target_file = self.postgres_dir / f"waitlist_db_{timestamp}.sqlite.gz"
            sqlite_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
            # Dump SQLite file into gzip
            with open(sqlite_path, "rb") as f_in:
                with gzip.open(target_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            # PostgreSQL dump via pg_dump
            target_file = self.postgres_dir / f"waitlist_db_{timestamp}.sql.gz"
            parsed = urlparse(db_url)
            env = os.environ.copy()
            if parsed.password:
                env["PGPASSWORD"] = parsed.password
            if "sslmode=require" in (parsed.query or ""):
                env["PGSSLMODE"] = "require"

            cmd = [
                "pg_dump",
                "-h", parsed.hostname or "localhost",
                "-p", str(parsed.port or 5432),
                "-U", parsed.username or "postgres",
                "-d", parsed.path.lstrip("/"),
                "--no-owner",
                "--no-acl",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                err_msg = stderr.decode(errors="replace")
                raise RuntimeError(f"pg_dump failed (exit code {process.returncode}): {err_msg}")

            # Compress output with gzip
            with gzip.open(target_file, "wb") as f_out:
                f_out.write(stdout)

        # Verify dump file
        if not target_file.exists() or target_file.stat().st_size == 0:
            raise RuntimeError(f"Database backup generated empty file: {target_file}")

        # Verify gzip integrity
        with gzip.open(target_file, "rb") as f_check:
            f_check.read(1024)

        # Optional encryption
        if settings.BACKUP_ENCRYPTION_KEY:
            target_file = self.encrypt_file(target_file, settings.BACKUP_ENCRYPTION_KEY)

        logger.info(f"Database backup created: {target_file.name} ({target_file.stat().st_size} bytes)")
        return target_file

    def encrypt_file(self, file_path: Path, key: str) -> Path:
        """Encrypts a backup file using Fernet symmetric encryption."""
        from cryptography.fernet import Fernet
        fernet = Fernet(key.encode() if isinstance(key, str) else key)

        data = file_path.read_bytes()
        encrypted = fernet.encrypt(data)

        enc_path = file_path.with_suffix(file_path.suffix + ".enc")
        enc_path.write_bytes(encrypted)
        file_path.unlink()  # Remove unencrypted original
        return enc_path

    def decrypt_file(self, enc_file_path: Path, key: str) -> Path:
        """Decrypts a backup file previously encrypted with Fernet."""
        from cryptography.fernet import Fernet
        fernet = Fernet(key.encode() if isinstance(key, str) else key)

        encrypted = enc_file_path.read_bytes()
        decrypted = fernet.decrypt(encrypted)

        # Remove .enc suffix
        orig_name = enc_file_path.name
        if orig_name.endswith(".enc"):
            orig_name = orig_name[:-4]
        dec_path = enc_file_path.parent / orig_name
        dec_path.write_bytes(decrypted)
        return dec_path

    def enforce_retention(self, directory: Path, retention_days: int) -> List[Path]:
        """
        Deletes backups older than retention_days.
        SAFETY RULE: Never deletes the newest valid backup, even if older than retention_days.
        Returns list of deleted file paths.
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        files = [p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")]

        if not files:
            return []

        # Sort files by modification time ascending (oldest first)
        files.sort(key=lambda p: p.stat().st_mtime)

        # Safety rule: Keep at least the newest backup
        newest_file = files[-1]
        deleted_files = []

        for p in files[:-1]:
            mtime = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
            if mtime < cutoff_date:
                try:
                    p.unlink()
                    deleted_files.append(p)
                    logger.info(f"Deleted expired backup: {p.name}")
                except Exception as exc:
                    logger.warning(f"Could not delete expired backup {p.name}: {exc}")

        return deleted_files

    def upload_to_s3(self, file_path: Path, subfolder: str = "backups") -> str:
        """
        Uploads a local backup file to AWS S3 or Cloudflare R2 bucket.
        Returns the object key within the bucket.
        """
        if not settings.S3_BUCKET_NAME:
            raise ValueError("S3_BUCKET_NAME must be configured when BACKUP_STORAGE is 's3'")

        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise RuntimeError(
                "boto3 is required for S3/R2 backup uploads. Please ensure boto3 is installed."
            )

        client_kwargs: dict[str, Any] = {
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "region_name": settings.AWS_REGION or "us-east-1",
            "config": Config(signature_version="s3v4"),
        }
        if settings.S3_ENDPOINT_URL:
            endpoint = settings.S3_ENDPOINT_URL.strip().rstrip("/")
            if settings.S3_BUCKET_NAME and endpoint.endswith(f"/{settings.S3_BUCKET_NAME}"):
                endpoint = endpoint[:-len(f"/{settings.S3_BUCKET_NAME}")].rstrip("/")
            client_kwargs["endpoint_url"] = endpoint

        s3_client = boto3.client("s3", **client_kwargs)
        s3_key = f"{subfolder}/{file_path.name}"

        logger.info(
            f"Uploading {file_path.name} to s3://{settings.S3_BUCKET_NAME}/{s3_key}..."
        )
        s3_client.upload_file(str(file_path), settings.S3_BUCKET_NAME, s3_key)
        logger.info(f"Successfully uploaded {file_path.name} to S3/R2 ({s3_key})")
        return s3_key

    async def run_full_backup(self) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Executes full 24-hour backup cycle:
        1. CSV snapshot
        2. Database dump
        3. Retention policy enforcement
        4. Optional offsite S3 / Cloudflare R2 upload
        5. Structured audit logging
        """
        csv_file: Optional[Path] = None
        db_file: Optional[Path] = None
        s3_csv_key: Optional[str] = None
        s3_db_key: Optional[str] = None

        try:
            # 1. CSV snapshot
            csv_file = await self.create_csv_snapshot()

            # 2. Database backup
            db_file = await self.create_database_backup()

            # 3. Retention policy
            self.enforce_retention(self.csv_dir, settings.BACKUP_RETENTION_DAYS)
            self.enforce_retention(self.postgres_dir, settings.BACKUP_RETENTION_DAYS)

            # 4. Offsite S3/R2 upload if enabled
            if settings.BACKUP_STORAGE == "s3" and settings.S3_BUCKET_NAME:
                try:
                    if csv_file:
                        s3_csv_key = await asyncio.to_thread(self.upload_to_s3, csv_file, "csv")
                    if db_file:
                        s3_db_key = await asyncio.to_thread(self.upload_to_s3, db_file, "postgres")
                except Exception as s3_exc:
                    logger.error(f"Failed to upload backup to S3/R2: {s3_exc}", exc_info=True)
                    audit_logger.error(
                        "Offsite backup upload failed",
                        extra={"event": "s3_upload_failed", "error": str(s3_exc)},
                    )

            audit_logger.info(
                "Automated backup completed successfully",
                extra={
                    "event": "backup_created",
                    "status": "success",
                    "csv_file": csv_file.name if csv_file else None,
                    "db_file": db_file.name if db_file else None,
                    "s3_csv_key": s3_csv_key,
                    "s3_db_key": s3_db_key,
                },
            )
            return csv_file, db_file
        except Exception as exc:
            audit_logger.error(
                "Automated backup failed",
                extra={
                    "event": "backup_failed",
                    "status": "failure",
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            raise
