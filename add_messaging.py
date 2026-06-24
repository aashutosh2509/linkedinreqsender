import re
import os

MESSAGING_CODE = """
def run_messaging_worker_sync(account_id="default", config=None):
    from datetime import datetime
    import random
    import time
    acc_state = get_account_state(account_id)
    acc_state.update_status(action="Starting messaging sequence...", progress=5)
    update_account_status_in_registry(account_id, status="Running", current_action="Starting messaging sequence...", progress_percent=5)
    acc_state.add_log("Starting LinkedIn Messaging Sequence...", "info")
    
    if not config:
        config = {}
        
    template = config.get("template", "Hi {first_name}, thanks for connecting!")
    delay_min = int(config.get("delay_min", 30))
    delay_max = int(config.get("delay_max", 60))
    
    db_data = load_db(account_id)
    contacts_to_message = [c for c in db_data if c.get("status") == "Connected" and not c.get("message_sent")]
    
    if not contacts_to_message:
        acc_state.add_log("No contacts found with status 'Connected' that haven't been messaged.", "warning")
        acc_state.update_status(action="Idle", progress=100)
        update_account_status_in_registry(account_id, status="Idle", current_action="Idle", progress_percent=100)
        acc_state.stop_running()
        return
        
    acc_state.add_log(f"Found {len(contacts_to_message)} connected profiles to message.", "info")
    
    proxy_cfg = None
    accounts = load_accounts_registry()
    for acc in accounts:
        if acc.get("id") == account_id:
            proxy_cfg = acc.get("proxy")
            break

    playwright, context = launch_browser(account_id=account_id, headed=True, proxy_config=proxy_cfg)
    page = context.new_page()
    
    if not check_login_status(page):
        acc_state.add_log("Not logged in. Auto-login might be required.", "error")
        acc_state.update_status(action="Idle", progress=100)
        update_account_status_in_registry(account_id, status="Idle", current_action="Idle", progress_percent=100)
        acc_state.stop_running()
        return
        
    for idx, contact in enumerate(contacts_to_message):
        if acc_state.stop_requested:
            acc_state.add_log("Messaging paused/stopped by user.", "warning")
            break
            
        progress = int((idx / len(contacts_to_message)) * 100)
        acc_state.update_status(action=f"Messaging {contact.get('name')}", progress=progress)
        
        profile_url = contact.get("profile_url", "").strip()
        if not profile_url:
            continue
            
        acc_state.add_log(f"[{idx+1}/{len(contacts_to_message)}] Navigating to {contact.get('name')}...", "info")
        try:
            page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(random.uniform(3, 5))
            
            msg_btn = page.locator("button:has-text('Message'), button[aria-label*='Message'], a[href*='/messaging/thread/']").first
            if msg_btn.is_visible():
                msg_btn.click()
                time.sleep(3)
                
                message_box = page.locator(".msg-form__contenteditable")
                message_box.wait_for(state="visible", timeout=10000)
                
                final_msg = resolve_template(template, contact)
                message_box.fill(final_msg)
                time.sleep(2)
                
                send_btn = page.locator(".msg-form__send-button")
                if send_btn.is_enabled():
                    send_btn.click()
                    acc_state.add_log(f"Message sent to {contact.get('name')}!", "success")
                    contact["message_sent"] = True
                    contact["date_messaged"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    save_db(db_data, account_id)
                else:
                    acc_state.add_log("Send button disabled. (Maybe it requires a premium inmail?)", "warning")
            else:
                acc_state.add_log("Message button not found on profile.", "warning")
        except Exception as e:
            acc_state.add_log(f"Failed to message {contact.get('name')}: {str(e)}", "warning")
            
        if idx < len(contacts_to_message) - 1 and not acc_state.stop_requested:
            delay = random.randint(delay_min, delay_max)
            acc_state.add_log(f"Waiting {delay} seconds before next message...", "info")
            time.sleep(delay)
            
    acc_state.update_status(action="Idle", progress=100)
    update_account_status_in_registry(account_id, status="Idle", current_action="Idle", progress_percent=100)
    acc_state.stop_running()


def start_messaging_worker(account_id="default", config=None):
    acc_state = get_account_state(account_id)
    if acc_state.get_state()["status"] == "Running":
        return {"error": "Another task is already running."}
    acc_state.start_running()
    worker_queue.add_to_queue("MESSAGING", account_id, lambda: run_messaging_worker_sync(account_id, config))
    return {"message": "Messaging started"}
"""

# Append to automation.py
with open("automation.py", "a", encoding="utf-8") as f:
    f.write("\n\n" + MESSAGING_CODE)

# Update app.py
with open("app.py", "r", encoding="utf-8") as f:
    app_content = f.read()

# Add import for start_messaging_worker
app_content = app_content.replace(
    "from automation import (", 
    "from automation import (\n    start_messaging_worker,"
)

API_ENDPOINT = """
@app.route("/api/start-messaging", methods=["POST"])
def start_messaging():
    data = request.json or {}
    account_id = data.get("account_id", "default")
    config = {
        "template": data.get("template", "Hi {first_name}, thanks for connecting!"),
        "delay_min": int(data.get("delay_min", 30)),
        "delay_max": int(data.get("delay_max", 70))
    }
    res = start_messaging_worker(account_id=account_id, config=config)
    if "error" in res:
        return jsonify(res), 400
    return jsonify(res)
"""

# Insert API endpoint before @app.route("/api/stop")
app_content = app_content.replace('@app.route("/api/stop", methods=["POST"])', API_ENDPOINT + '\n@app.route("/api/stop", methods=["POST"])')

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_content)

print("Backend updated.")
