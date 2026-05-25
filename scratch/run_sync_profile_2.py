import os
import sys
import time

# Add workspace to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import automation

def main():
    account_id = "profile_2_9950"
    print(f"Running Acceptance Sync for account: {account_id}")
    
    # 1. Reset target profiles back to 'Pending' to trigger sync & date enrichment
    db_data = automation.load_db(account_id)
    target_names = ["narendra mehar", "dr. abhishek jain"]
    
    print("\nResetting target statuses to 'Pending' in DB for testing...")
    for contact in db_data:
        name_lower = contact.get("name", "").lower()
        if any(t in name_lower for t in target_names):
            contact["status"] = "Pending"
            contact["date_accepted"] = None
            # Leave email/phone intact or reset them to force scrape
            contact["email"] = None
            contact["phone"] = None
            print(f"  Reset contact: {contact.get('name')}")
    automation.save_db(db_data, account_id)
    
    try:
        # 2. Run sync synchronously
        automation.sync_acceptance_task_sync(account_id)
        print("\n--- SYNC COMPLETED ---")
        
        # 3. Load and print updated statuses
        db_data = automation.load_db(account_id)
        
        print("\n--- UPDATED DATABASE RECORDS ---")
        for contact in db_data:
            name_lower = contact.get("name", "").lower()
            if any(t in name_lower for t in target_names):
                print(f"Name: {contact.get('name')}")
                print(f"  Status: {contact.get('status')}")
                print(f"  Date Sent: {contact.get('date_sent')}")
                print(f"  Date Accepted: {contact.get('date_accepted')}")
                print(f"  Email: {contact.get('email')}")
                print(f"  Phone: {contact.get('phone')}")
                print("-" * 40)
                
    except Exception as e:
        print(f"Error occurred during sync: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
