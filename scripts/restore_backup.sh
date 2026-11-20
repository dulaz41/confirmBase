#!/usr/bin/env bash
# ==============================================================================
# Database Backup Restore & Verification Script
# Usage: ./scripts/restore_backup.sh <path_to_backup.sql.gz> [target_database_url]
# ==============================================================================

set -euo pipefail

BACKUP_FILE="${1:-}"
TARGET_DB="${2:-${SYNC_DATABASE_URL:-postgresql://waitlist_user:waitlist_secure_pass@localhost:5432/waitlist_db}}"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <path_to_backup.sql.gz> [target_database_url]"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file '$BACKUP_FILE' not found."
    exit 1
fi

echo "==> Starting database restore from '$BACKUP_FILE'..."
echo "==> Target Database: '$TARGET_DB'"

# Call the Python restore script which handles decryption, gunzip, and record verification
python3 scripts/restore.py --backup-file "$BACKUP_FILE" --target-db "$TARGET_DB"

echo "==> Restore procedure verified successfully."
