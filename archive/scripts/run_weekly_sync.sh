#!/bin/bash

# Wrapper script for weekly sync of SQLite to Pickle cache
# Recommended cron schedule: Weekly (e.g., Sunday at 3 AM)

# 1. Navigate to project directory
cd /home/marcos/trade/momentum-v2

# 2. Activate virtual environment if it exists (adjust path if needed)
# if [ -d "venv" ]; then
#    source venv/bin/activate
# fi

# 3. Run the sync script
echo "Starting weekly cache synchronization: $(date)" >> logs/cron_sync.log
/usr/bin/python3 sync_sqlite_to_pkl.py >> logs/cron_sync.log 2>&1

echo "Sync completed: $(date)" >> logs/cron_sync.log
