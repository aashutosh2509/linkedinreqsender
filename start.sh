#!/usr/bin/env bash

# Setup directories on the persistent disk if it is writable
DATA_WRITABLE=false
if touch /data/.write_test 2>/dev/null; then
    rm -f /data/.write_test
    DATA_WRITABLE=true
fi

if [ "$DATA_WRITABLE" = true ]; then
    echo "[STARTUP] Persistent disk /data is mounted and writable. Using persistent path symlinks."
    export PLAYWRIGHT_BROWSERS_PATH=/data/pw-browsers
    mkdir -p /data/linkedin_user_data
    mkdir -p /data/accounts_db
    
    # Copy initial data to persistent disk if it hasn't been initialized
    if [ ! -f /data/.initialized ]; then
        echo "Initializing persistent disk..."
        cp -r ./linkedin_user_data/* /data/linkedin_user_data/ 2>/dev/null || true
        cp -r ./accounts_db/* /data/accounts_db/ 2>/dev/null || true
        cp ./accounts.json /data/accounts.json 2>/dev/null || true
        touch /data/.initialized
    fi
    
    # Ensure accounts.json exists on persistent disk even if initialized before this fix
    if [ ! -f /data/accounts.json ]; then
        cp ./accounts.json /data/accounts.json 2>/dev/null || true
    fi
    
    # Remove local folders to replace them with symlinks to the persistent disk
    rm -rf ./linkedin_user_data
    rm -rf ./accounts_db
    rm -f ./accounts.json
    
    # Create symlinks
    ln -s /data/linkedin_user_data ./linkedin_user_data
    ln -s /data/accounts_db ./accounts_db
    ln -s /data/accounts.json ./accounts.json
else
    echo "[STARTUP] Persistent disk /data is NOT writable (Free Tier or permission block). Falling back to local workspace directories."
    export PLAYWRIGHT_BROWSERS_PATH=$(pwd)/pw-browsers
    # Ensure directories exist locally
    mkdir -p ./linkedin_user_data
    mkdir -p ./accounts_db
fi

# Run the gunicorn server with a long timeout for playwright
gunicorn app:app --timeout 120
