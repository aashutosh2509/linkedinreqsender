import os
import sys
import time

# Ensure workspace is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import automation

account_id = "default"
print(f"Direct acceptance sync diagnostic starting for account: {account_id}")

try:
    # Check if user data directory is locked or exists
    profile_dir = os.path.join(automation.BASE_USER_DATA_DIR, account_id)
    print(f"Profile directory: {profile_dir}")
    if os.path.exists(profile_dir):
        print("Profile directory exists.")
        # Try to see if we can open it or if another browser process is using it
        lock_file = os.path.join(profile_dir, "SingletonLock")
        if os.path.exists(lock_file):
            print(f"SingletonLock file exists: {lock_file}")
            # Under Windows, if chrome is running it locks this folder or file.
            # We will see if launch_browser succeeds or throws an exception.
    
    # Run the sync task synchronously
    automation.sync_acceptance_task_sync(account_id)
    print("Direct sync task completed.")
    
    # Print the logs captured in acc_state
    state = automation.get_account_state(account_id)
    print("\nCaptured Logs:")
    for log in state.logs:
        print(f"[{log['time']}] [{log['type'].upper()}] {log['message']}")
        
except Exception as e:
    print(f"Critical diagnostic exception: {str(e)}")
    import traceback
    traceback.print_exc()
