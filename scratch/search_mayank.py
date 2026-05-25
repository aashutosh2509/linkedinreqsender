import os
import json

db_dir = "accounts_db"
for filename in os.listdir(db_dir):
    if filename.endswith(".json"):
        filepath = os.path.join(db_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for idx, contact in enumerate(data):
            if "mayank" in contact.get("name", "").lower() or "pandey" in contact.get("name", "").lower():
                print(f"File: {filename} | Sr. No: {idx+1} | Name: {contact['name']} | Status: {contact['status']} | Date Sent: {contact.get('date_sent')} | Date Accepted: {contact.get('date_accepted')} | Email: {contact.get('email')} | Phone: {contact.get('phone')} | Logs: {contact.get('logs')}")
