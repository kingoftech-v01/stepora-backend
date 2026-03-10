#!/bin/bash
# ─── Stepora PostgreSQL Backup Script ────────────────────────
# Runs daily via cron. Retains 7 days of backups.
# Usage: ./scripts/backup.sh
# Cron:  0 3 * * * /root/stepora/scripts/backup.sh >> /var/log/stepora-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="/root/stepora/backups"
CONTAINER_NAME="stepora_db"
DB_NAME="stepora"
DB_USER="stepora"
RETENTION_DAYS=7
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/stepora_${DATE}.sql.gz"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting backup..."

# Dump PostgreSQL via Docker exec, compress with gzip
docker exec "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${BACKUP_FILE}"

# Verify backup is not empty
if [ ! -s "${BACKUP_FILE}" ]; then
    echo "[$(date)] ERROR: Backup file is empty!"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date)] Backup complete: ${BACKUP_FILE} (${BACKUP_SIZE})"

# Remove old backups (older than RETENTION_DAYS)
DELETED=$(find "${BACKUP_DIR}" -name "stepora_*.sql.gz" -mtime +${RETENTION_DAYS} -print -delete | wc -l)
echo "[$(date)] Removed ${DELETED} old backup(s)"

# List current backups
echo "[$(date)] Current backups:"
ls -lh "${BACKUP_DIR}"/stepora_*.sql.gz 2>/dev/null || echo "  (none)"
