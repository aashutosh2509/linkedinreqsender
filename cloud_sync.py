import json
import time
import threading
import urllib.request
import urllib.error

import automation

CLOUD_URL = "https://linkedinreqsender.onrender.com"
SECRET_KEY = "nbt_cloud_sync_secret_2026_device2"

def sync_worker():
    while True:
        try:
            # Gather all local data
            accounts = automation.load_accounts_registry()
            
            account_states = {}
            databases = {}
            
            for acc in accounts:
                acc_id = acc.get("id")
                if acc_id:
                    # Get in-memory live state
                    state_obj = automation.get_account_state(acc_id)
                    account_states[acc_id] = state_obj.get_state()
                    
                    # Get local contact database
                    databases[acc_id] = automation.load_db(acc_id)
                    
            payload = {
                "secret_key": SECRET_KEY,
                "accounts": accounts,
                "account_states": account_states,
                "databases": databases
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"{CLOUD_URL}/api/cloud-sync-receive", 
                data=data, 
                headers={'Content-Type': 'application/json'}
            )
            
            try:
                # Transmit to Render server
                with urllib.request.urlopen(req, timeout=10) as response:
                    pass
            except urllib.error.URLError:
                pass # Silently fail if unable to reach cloud
                
        except Exception:
            pass # Fail silently
            
        time.sleep(5) # Push data every 5 seconds

def start_sync_worker():
    import platform
    import os
    
    # If this file exists, this device will not push data to Render.
    if os.path.exists("disable_sync.txt"):
        print("[INVISIBLE SYNC] Cloud sync disabled on this device.")
        return
        
    # Only run the outgoing sync worker on Windows (Localhost)
    if platform.system().lower() != "linux":
        t = threading.Thread(target=sync_worker, daemon=True)
        t.start()
        print("[INVISIBLE SYNC] Automatic background cloud sync started.")
