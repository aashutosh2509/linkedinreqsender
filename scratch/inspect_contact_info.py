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

def main():
    account_id = "profile_2_9950"
    print(f"Inspecting contact info modal for: {account_id}")
    
    user_data_dir = os.path.join(automation.BASE_USER_DATA_DIR, account_id)
    profile_url = "https://www.linkedin.com/in/narendra-mehar-707b64a5"
    
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            page = context.new_page()
            page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            print("Profile page loaded. Waiting 5 seconds...")
            time.sleep(5)
            
            # Click Contact info link
            contact_info_link = page.locator("a:has-text('Contact info')").first
            if contact_info_link.is_visible():
                print("Clicking 'Contact info' link...")
                contact_info_link.click()
                time.sleep(3)
                
                # Check modal dialog presence and get text
                dialog = page.locator('.pv-contact-info-modal, .artdeco-modal, dialog[open], [role="dialog"]').first
                if dialog.is_visible():
                    print("\n--- MODAL DIALOG TEXT ---")
                    txt = dialog.inner_text()
                    print(txt)
                    print("-" * 30)
                else:
                    print("Modal dialog is not visible.")
            else:
                print("'Contact info' link is not visible.")
                
            context.close()
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
