import os
import sys
import time
from playwright.sync_api import sync_playwright

# Reconfigure stdout to support unicode on Windows terminal
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

# Add workspace to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import automation

class MockAccState:
    def __init__(self):
        self.stop_requested = False
    def add_log(self, msg, level="info"):
        print(f"[Mock Log] [{level.upper()}] {msg}")

def main():
    account_id = "profile_2_9950"
    print(f"Starting production verification for account: {account_id}")
    
    user_data_dir = os.path.join(automation.BASE_USER_DATA_DIR, account_id)
    profile_username = "narendra-mehar-707b64a5"
    
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            page = context.new_page()
            
            # Call the production verify_profile_status directly using the page
            acc_state = MockAccState()
            print(f"Calling automation.verify_profile_status for '{profile_username}'...")
            
            # This navigates and runs our brand new production JS status checker!
            result = automation.verify_profile_status(page, profile_username, acc_state)
            
            print(f"\n>>> PRODUCTION INTEGRATION TEST RESULT: {result}")
            assert result == "Connected", f"Failed! Expected 'Connected', but got '{result}'"
            print("SUCCESS! The connection status was perfectly and accurately detected as 'Connected'!")
            
            context.close()
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
