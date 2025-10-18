#!/bin/bash
echo "=== System Load ==="
uptime

echo -e "\n=== Memory Usage ==="
free -h

echo -e "\n=== CPU Cores ==="
nproc

echo -e "\n=== Service Status ==="
systemctl is-active gunicorn celery celerybeat nginx

echo -e "\n=== Worker Count ==="
echo "Gunicorn workers: $(pgrep -c -f 'gunicorn.*worker')"
echo "Celery workers: $(pgrep -c -f 'celery.*worker')"

echo -e "\n=== Redis Queue Size ==="
redis-cli LLEN celery

echo -e "\n=== Disk Usage ==="
df -h | grep -E 'Filesystem|/$'

echo -e "\n=== Recent Errors ==="
grep -c ERROR ~/crm_project/logs/app.log
