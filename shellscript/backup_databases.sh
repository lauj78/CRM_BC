#!/bin/bash
# Database backup script

BACKUP_DIR="/home/lauj/database_backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup main database
pg_dump -U crm_user -d crm_db -h localhost > "$BACKUP_DIR/crm_db_$DATE.sql"

# Backup tenant databases
pg_dump -U crm_user -d crm_db_pukul_com -h localhost > "$BACKUP_DIR/crm_db_pukul_com_$DATE.sql"
pg_dump -U crm_user -d crm_db_solo_com -h localhost > "$BACKUP_DIR/crm_db_solo_com_$DATE.sql"
pg_dump -U crm_user -d crm_db_cafe_com -h localhost > "$BACKUP_DIR/crm_db_cafe_com_$DATE.sql"
pg_dump -U crm_user -d crm_db_money_com -h localhost > "$BACKUP_DIR/crm_db_money_com_$DATE.sql"

# Delete backups older than 7 days
find $BACKUP_DIR -name "*.sql" -type f -mtime +10 -delete

echo "Backup completed: $DATE"
