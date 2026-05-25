#!/usr/bin/env bash

# Setup directories on the persistent disk
mkdir -p /data/linkedin_user_data
mkdir -p /data/accounts_db

# Copy initial data to persistent disk if it hasn't been initialized
if [ ! -f /data/.initialized ]; then
    echo "Initializing persistent disk..."
    cp -r ./linkedin_user_data/* /data/linkedin_user_data/ 2>/dev/null || true
    cp -r ./accounts_db/* /data/accounts_db/ 2>/dev/null || true
    touch /data/.initialized
fi

# Remove local folders to replace them with symlinks to the persistent disk
rm -rf ./linkedin_user_data
rm -rf ./accounts_db

# Create symlinks
ln -s /data/linkedin_user_data ./linkedin_user_data
ln -s /data/accounts_db ./accounts_db

# Run the gunicorn server with a long timeout for playwright
gunicorn app:app --timeout 120
