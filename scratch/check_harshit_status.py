import os
import json

db_dir = "accounts_db"
for filename in os.listdir(db_dir):
    if filename.endswith(".json"):
        filepath = os.path.join(db_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for contact in data:
            if "harshit" in contact.get("name", "").lower() or "saxena" in contact.get("name", "").lower():
                print(f"File: {filename} | Name: {contact['name']} | Status: {contact['status']} | Date Sent: {contact.get('date_sent')} | Date Accepted: {contact.get('date_accepted')}")
