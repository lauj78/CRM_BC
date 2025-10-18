#!/bin/bash
echo "=== GUNICORN STATUS ==="
sudo systemctl status gunicorn --no-pager -l

echo -e "\n=== RECENT ERRORS ==="
sudo journalctl -u gunicorn --since "10 minutes ago" --no-pager | grep -i error

echo -e "\n=== DJANGO APP ERRORS ==="
tail -20 ~/crm_project/logs/app.log | grep -i error

echo -e "\n=== CELERY STATUS ==="
sudo systemctl status celery --no-pager -l
