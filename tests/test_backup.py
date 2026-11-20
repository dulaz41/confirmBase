from __future__ import annotations

import os
import time
import tempfile
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import WaitlistEntry
from app.services.backup_service import BackupService
from tests.conftest import TestingSessionLocal


@pytest.mark.asyncio
async def test_csv_snapshot_creation(db_session: AsyncSession, monkeypatch):
    """BackupService creates a valid timestamped CSV snapshot."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "BACKUP_ENCRYPTION_KEY", None)
    # Seed entry
    entry = WaitlistEntry(
        email="snapshot@example.com",
        email_normalized="snapshot@example.com",
    )
    db_session.add(entry)
    await db_session.commit()

    with tempfile.TemporaryDirectory() as temp_dir:
        service = BackupService(base_dir=temp_dir, session_factory=TestingSessionLocal)
        csv_file = await service.create_csv_snapshot()

        assert csv_file.exists()
        assert csv_file.stat().st_size > 0
        assert "waitlist_" in csv_file.name
        assert csv_file.name.endswith(".csv")

        content = csv_file.read_text(encoding="utf-8")
        assert "snapshot@example.com" in content
        assert "email" in content and "created_at" in content


def test_backup_retention_policy():
    """
    Retention policy deletes expired backups but NEVER deletes the newest valid backup.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        p_dir = Path(temp_dir) / "csv"
        p_dir.mkdir(parents=True)

        # Create three dummy files: 40 days old, 35 days old, and 31 days old
        now = time.time()
        file1 = p_dir / "backup_old_1.csv"
        file1.write_text("dummy")
        os.utime(file1, (now - 40 * 86400, now - 40 * 86400))

        file2 = p_dir / "backup_old_2.csv"
        file2.write_text("dummy")
        os.utime(file2, (now - 35 * 86400, now - 35 * 86400))

        # This is the newest file, but still older than 30 days
        file3 = p_dir / "backup_newest.csv"
        file3.write_text("dummy")
        os.utime(file3, (now - 31 * 86400, now - 31 * 86400))

        service = BackupService(base_dir=temp_dir)
        deleted = service.enforce_retention(p_dir, retention_days=30)

        # file1 and file2 should be deleted
        assert file1 in deleted
        assert file2 in deleted
        assert not file1.exists()
        assert not file2.exists()

        # Crucial safety check: file3 MUST survive because it is the newest valid backup!
        assert file3 not in deleted
        assert file3.exists()


def test_backup_encryption_and_decryption():
    """Fernet encryption and decryption roundtrip."""
    with tempfile.TemporaryDirectory() as temp_dir:
        service = BackupService(base_dir=temp_dir)
        key = Fernet.generate_key().decode()

        test_file = Path(temp_dir) / "test.csv"
        test_file.write_text("email,created_at\nuser@example.com,2026-10-07T00:00:00Z\n")

        # Encrypt
        enc_file = service.encrypt_file(test_file, key)
        assert enc_file.exists()
        assert enc_file.name == "test.csv.enc"
        assert not test_file.exists()

        # Decrypt
        dec_file = service.decrypt_file(enc_file, key)
        assert dec_file.exists()
        assert dec_file.read_text() == "email,created_at\nuser@example.com,2026-10-07T00:00:00Z\n"


def test_restore_sqlite_database():
    """Tests the restore logic against a test SQLite database."""
    from scripts.restore import restore_backup
    import sqlite3
    import gzip

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a source sqlite db
        src_db = Path(temp_dir) / "source.db"
        conn = sqlite3.connect(src_db)
        conn.execute("CREATE TABLE waitlist_entries (id TEXT, email TEXT);")
        conn.execute("INSERT INTO waitlist_entries VALUES ('1', 'restored@example.com');")
        conn.commit()
        conn.close()

        # Compress to .sqlite.gz
        backup_file = Path(temp_dir) / "waitlist_backup.sqlite.gz"
        with open(src_db, "rb") as f_in, gzip.open(backup_file, "wb") as f_out:
            f_out.write(f_in.read())

        # Target database to restore to
        target_db = Path(temp_dir) / "restored_target.db"
        target_db_url = f"sqlite:///{target_db}"

        # Restore
        success = restore_backup(backup_file, target_db_url)
        assert success is True
        assert target_db.exists()

        # Verify content
        t_conn = sqlite3.connect(target_db)
        cur = t_conn.cursor()
        cur.execute("SELECT email FROM waitlist_entries;")
        row = cur.fetchone()
        t_conn.close()
        assert row[0] == "restored@example.com"


def test_upload_to_s3_mocked(monkeypatch):
    """Verifies upload_to_s3 properly formats S3 client kwargs and calls upload_file."""
    import sys
    from unittest.mock import MagicMock
    from app.core.config import settings

    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "my-test-bucket")
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-key-id")
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret-key")
    monkeypatch.setattr(settings, "S3_ENDPOINT_URL", "https://xyz.r2.cloudflarestorage.com")

    mock_s3_client = MagicMock()
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)
    monkeypatch.setitem(sys.modules, "botocore", MagicMock())
    monkeypatch.setitem(sys.modules, "botocore.config", MagicMock())

    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / "dummy.csv"
        test_file.write_text("test")

        service = BackupService(base_dir=temp_dir)
        s3_key = service.upload_to_s3(test_file, subfolder="csv")

        assert s3_key == "csv/dummy.csv"
        mock_s3_client.upload_file.assert_called_once_with(
            str(test_file), "my-test-bucket", "csv/dummy.csv"
        )


def test_upload_to_s3_endpoint_sanitization(monkeypatch):
    """Verifies that trailing bucket name or slash in endpoint URL is automatically stripped."""
    import sys
    from unittest.mock import MagicMock
    from app.core.config import settings

    monkeypatch.setattr(settings, "S3_BUCKET_NAME", "confirmbase-backups")
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-key-id")
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret-key")
    monkeypatch.setattr(
        settings, "S3_ENDPOINT_URL", "https://xyz.r2.cloudflarestorage.com/confirmbase-backups/"
    )

    mock_s3_client = MagicMock()
    mock_boto3 = MagicMock()
    mock_boto3.client.return_value = mock_s3_client
    monkeypatch.setitem(sys.modules, "boto3", mock_boto3)
    monkeypatch.setitem(sys.modules, "botocore", MagicMock())
    monkeypatch.setitem(sys.modules, "botocore.config", MagicMock())

    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / "dummy.csv"
        test_file.write_text("test")

        service = BackupService(base_dir=temp_dir)
        service.upload_to_s3(test_file, subfolder="csv")

        _, kwargs = mock_boto3.client.call_args
        assert kwargs["endpoint_url"] == "https://xyz.r2.cloudflarestorage.com"


