import os
import json
import re
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
import openpyxl

import automation
from automation import (
    get_account_state,
    load_accounts_registry,
    save_accounts_registry,
    update_account_status_in_registry,
    load_db,
    save_db,
    open_linkedin_for_login,
    run_automation_worker,
    sync_acceptance_task,
    queue_runner,
    BROWSERS_PATH
)

def ensure_playwright_browsers():
    def run():
        import subprocess
        import sys
        
        pw_path = BROWSERS_PATH
        try:
            os.makedirs(pw_path, exist_ok=True)
        except Exception as e:
            print(f"[ERROR] Failed to create directories for Playwright: {str(e)}")
            return
            
        is_installed = False
        try:
            for root, dirs, files in os.walk(pw_path):
                if any(f == "chrome" or f == "chrome-headless-shell" for f in files):
                    is_installed = True
                    break
        except Exception:
            pass
            
        if not is_installed:
            print("--------------------------------------------------")
            print("Playwright browsers not found! Running background self-healing install...")
            print(f"Target path: {pw_path}")
            print("--------------------------------------------------")
            try:
                env = os.environ.copy()
                env["PLAYWRIGHT_BROWSERS_PATH"] = pw_path
                python_exe = sys.executable or "python"
                
                print("Installing Chromium browser in background...")
                result = subprocess.run(
                    [python_exe, "-m", "playwright", "install", "chromium"],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=True
                )
                print(f"Install stdout: {result.stdout}")
                print("Playwright Chromium installed successfully in background!")
            except Exception as e:
                print(f"[ERROR] Failed to install Playwright browsers in background: {str(e)}")
                if 'result' in locals() and 'result' in vars() and result:
                    print(f"Install stderr: {result.stderr}")
                    
    import threading
    import platform
    if platform.system().lower() == "linux":
        threading.Thread(target=run, daemon=True).start()

ensure_playwright_browsers()

app = Flask(__name__, static_folder="public")
CORS(app)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Standard response helper
def err_response(message, code=400):
    return jsonify({"error": message}), code

# LinkedIn URL Validator
LINKEDIN_URL_PATTERN = re.compile(
    r'^(https?://)?([a-z]{2,}\.)?linkedin\.com/in/[A-Za-z0-9\-\_\.%]+/?$',
    re.IGNORECASE
)

def validate_and_normalize_linkedin_url(url):
    """Validate and normalize a LinkedIn profile URL.
    Accepts www.linkedin.com and country-specific domains like in.linkedin.com.
    """
    url = url.strip()
    if not url:
        return None, "Profile URL is required."
    
    # Allow plain alphanumeric usernames — auto-convert
    if re.match(r'^[A-Za-z0-9\-\_\.]+$', url) and 'linkedin' not in url.lower():
        url = f"https://www.linkedin.com/in/{url}"
    
    clean_url = url.split('?')[0].rstrip('/')
    if not LINKEDIN_URL_PATTERN.match(clean_url):
        return None, (
            f"Invalid LinkedIn URL: '{url}'. "
            "URL must match the format: linkedin.com/in/username. "
        )
    
    if not clean_url.startswith('http'):
        clean_url = 'https://' + clean_url
    
    # Normalize country-specific domains (in.linkedin.com -> www.linkedin.com)
    clean_url = re.sub(
        r'https?://[a-z]{2,}\.linkedin\.com/in/',
        'https://www.linkedin.com/in/',
        clean_url,
        flags=re.IGNORECASE
    )
    
    return clean_url, None

# Serves frontend files
@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/<path:path>")
def serve_static(path):
    if path and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

# API - Manage Accounts Registry & Aggregate Stats
@app.route("/api/accounts", methods=["GET"])
def get_accounts():
    accounts = load_accounts_registry()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    status = request.args.get("status")
    
    for acc in accounts:
        acc_id = acc.get("id")
        acc_state = get_account_state(acc_id)
        state_dict = acc_state.get_state()
        
        acc["is_running"] = state_dict["is_running"]
        acc["current_action"] = state_dict["current_action"]
        acc["progress_percent"] = state_dict["progress_percent"]
        acc["logs"] = state_dict["logs"]
        
        # Pull stats from individual db
        contacts = load_db(acc_id)
        
        filtered_contacts = contacts
        if start_date or end_date:
            filtered_contacts = []
            for c in contacts:
                raw_date = c.get("date_accepted") or c.get("date_sent")
                if not raw_date:
                    continue
                try:
                    action_date = raw_date.split()[0]
                    if start_date and action_date < start_date:
                        continue
                    if end_date and action_date > end_date:
                        continue
                    filtered_contacts.append(c)
                except:
                    pass
        
        if status and status != "all":
            filtered_contacts = [c for c in filtered_contacts if c.get("status") == status]
            
        connected_count = sum(1 for c in filtered_contacts if c.get("status") == "Connected")
        pending_count = sum(1 for c in filtered_contacts if c.get("status") == "Pending")
        failed_count = sum(1 for c in filtered_contacts if c.get("status") == "Failed")
        sent_total = sum(1 for c in filtered_contacts if c.get("status") in ["Pending", "Connected"])
        
        # Calculate active days from date_sent
        days_active = set()
        for c in filtered_contacts:
            ds = c.get("date_sent")
            if ds:
                try:
                    days_active.add(ds.split()[0])
                except:
                    pass
                    
        acc["stats"] = {
            "total": len(filtered_contacts),
            "sent": sent_total,
            "connected": connected_count,
            "pending": pending_count,
            "failed": failed_count,
            "active_days_count": len(days_active) or 1,
            "avg_sent_per_day": round(sent_total / (len(days_active) or 1), 1),
            "acceptance_rate": round((connected_count / (connected_count + pending_count) * 100), 1) if (connected_count + pending_count) > 0 else 0.0
        }
    return jsonify(accounts)

@app.route("/api/accounts/add", methods=["POST"])
def add_account():
    req_data = request.json or {}
    acc_id = req_data.get("id", "").strip().lower()
    acc_name = req_data.get("name", "").strip()
    proxy = req_data.get("proxy") # server, username, password structure
    
    if not acc_id or not re.match(r"^[a-z0-9_\-]+$", acc_id):
        return err_response("Account ID must be alphanumeric, containing only lowercase letters, digits, dashes or underscores.")
        
    if not acc_name:
        return err_response("Account Name is required.")
        
    accounts = load_accounts_registry()
    if any(a.get("id") == acc_id for a in accounts):
        return err_response(f"Account ID '{acc_id}' is already registered.")
        
    new_acc = {
        "id": acc_id,
        "name": acc_name,
        "li_username": req_data.get("li_username", "").strip() or None,
        "li_password": req_data.get("li_password", "").strip() or None,
        "proxy": proxy if proxy and proxy.get("server") else None,
        "config": {
            "note_template": "Hi {FirstName}, let's connect!",
            "send_with_note": False,
            "delay_min": 30,
            "delay_max": 70,
            "daily_limit": 25,
            "weekly_limit": 150,
            "schedule": None
        },
        "status": "Idle",
        "current_action": "Idle",
        "progress_percent": 0
    }
    
    accounts.append(new_acc)
    save_accounts_registry(accounts)
    
    # Initialize empty db
    save_db([], acc_id)
    
    acc_state = get_account_state(acc_id)
    acc_state.add_log(f"Account '{acc_name}' ({acc_id}) registered successfully.", "success")
    return jsonify({"status": "success", "message": f"Account '{acc_name}' registered successfully."})

@app.route("/api/accounts/delete", methods=["POST"])
def delete_account():
    req_data = request.json or {}
    acc_id = req_data.get("id", "").strip()
    
    if acc_id == "default":
        return err_response("The primary default account cannot be deleted.")
        
    accounts = load_accounts_registry()
    acc_to_remove = None
    for acc in accounts:
        if acc.get("id") == acc_id:
            acc_to_remove = acc
            break
            
    if not acc_to_remove:
        return err_response("Account not found.")
        
    acc_state = get_account_state(acc_id)
    if acc_state.is_running:
        return err_response("Cannot delete an active running account. Stop it first.")
        
    accounts = [a for a in accounts if a.get("id") != acc_id]
    save_accounts_registry(accounts)
    
    # Remove db file
    db_path = automation.get_db_path(acc_id)
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass
            
    return jsonify({"status": "success", "message": f"Account '{acc_to_remove.get('name')}' removed successfully."})

@app.route("/api/accounts/reorder", methods=["POST"])
def reorder_accounts():
    req_data = request.json or {}
    ordered_ids = req_data.get("order", [])
    if not ordered_ids:
        return err_response("Order list is required.")
        
    accounts = load_accounts_registry()
    account_map = {a.get("id"): a for a in accounts}
    
    reordered_accounts = []
    for aid in ordered_ids:
        if aid in account_map:
            reordered_accounts.append(account_map[aid])
            
    # Add any missing accounts that weren't in ordered_ids
    for a in accounts:
        if a.get("id") not in ordered_ids:
            reordered_accounts.append(a)
            
    save_accounts_registry(reordered_accounts)
    return jsonify({"status": "success", "message": "Accounts registry order updated."})

@app.route("/api/accounts/update-config", methods=["POST"])
def update_account_config():
    req_data = request.json or {}
    acc_id = req_data.get("id", "default").strip()
    config = req_data.get("config", {})
    
    accounts = load_accounts_registry()
    acc_to_update = None
    for acc in accounts:
        if acc.get("id") == acc_id:
            acc_to_update = acc
            break
            
    if not acc_to_update:
        return err_response("Account not found.")
        
    acc_config = acc_to_update.setdefault("config", {})
    if "note_template" in config:
        acc_config["note_template"] = config["note_template"]
    if "send_with_note" in config:
        acc_config["send_with_note"] = bool(config["send_with_note"])
    if "delay_min" in config:
        acc_config["delay_min"] = int(config["delay_min"])
    if "delay_max" in config:
        acc_config["delay_max"] = int(config["delay_max"])
    if "daily_limit" in config:
        acc_config["daily_limit"] = int(config["daily_limit"])
    if "weekly_limit" in config:
        acc_config["weekly_limit"] = int(config["weekly_limit"])
    if "start_index" in config:
        val = config["start_index"]
        acc_config["start_index"] = int(val) if val is not None and str(val).strip() != "" else None
    if "end_index" in config:
        val = config["end_index"]
        acc_config["end_index"] = int(val) if val is not None and str(val).strip() != "" else None
    if "schedule" in config:
        sched = config["schedule"]
        if sched:
            acc_config["schedule"] = {
                "enabled": bool(sched.get("enabled", False)),
                "time": str(sched.get("time", "10:00")).strip(),
                "days": [int(d) for d in sched.get("days", [])],
                "last_run": sched.get("last_run")
            }
        else:
            acc_config["schedule"] = None
        
    if "proxy" in req_data:
        px = req_data["proxy"]
        acc_to_update["proxy"] = px if px and px.get("server") else None
        
    if "name" in req_data and req_data["name"].strip():
        acc_to_update["name"] = req_data["name"].strip()

    if "li_username" in req_data:
        acc_to_update["li_username"] = req_data["li_username"].strip() or None
    if "li_password" in req_data:
        acc_to_update["li_password"] = req_data["li_password"].strip() or None
        
    save_accounts_registry(accounts)
    
    acc_state = get_account_state(acc_id)
    acc_state.add_log("Account settings updated.", "info")
    return jsonify({"status": "success", "message": "Account configurations updated successfully."})

# API - Get Current Automation State
@app.route("/api/state", methods=["GET"])
def get_automation_state():
    acc_id = request.args.get("account_id", "default")
    acc_state = get_account_state(acc_id)
    return jsonify(acc_state.get_state())

# API - Check Login Session
@app.route("/api/accounts/check-login", methods=["POST"])
def check_account_login():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "").strip()
    
    if not acc_id:
        return err_response("Account ID is required.")
        
    acc_state = get_account_state(acc_id)
    if acc_state.is_running:
        return jsonify({
            "status": "success",
            "logged_in": False,
            "message": "Account is currently busy (another automation or browser task is active)."
        })
        
    acc_state.add_log("Testing login session status headlessly...", "info")
    logged_in = automation.test_login_session(acc_id)
    
    if logged_in:
        acc_state.add_log("Login session active and authenticated.", "success")
        return jsonify({"status": "success", "logged_in": True, "message": "Session is active."})
    else:
        acc_state.add_log("Login session expired or logged out.", "warning")
        return jsonify({"status": "success", "logged_in": False, "message": "Session is expired or logged out."})

# API - Get Contacts list
@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    acc_id = request.args.get("account_id", "default")
    return jsonify(load_db(acc_id))

# API - Add a single contact
@app.route("/api/contacts/add", methods=["POST"])
def add_contact():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "default")
    acc_state = get_account_state(acc_id)
    
    if acc_state.is_running:
        return err_response("Cannot add contacts while automation is running.")
        
    url = req_data.get("profile_url", "").strip()
    name = req_data.get("name", "").strip()
    
    norm_url, url_error = validate_and_normalize_linkedin_url(url)
    if url_error:
        return err_response(url_error)
    url = norm_url
    
    db_data = load_db(acc_id)
    existing_urls = {c.get("profile_url", "").strip().split('?')[0].rstrip('/') for c in db_data}
    if norm_url in existing_urls:
        return err_response("This profile URL already exists in this account's database.")
        
    if not name:
        username = url.split("/in/")[-1].split("/")[0].replace("-", " ")
        name = username.title()
        
    first_name = ""
    last_name = ""
    parts = name.split()
    first_name = parts[0] if parts else ""
    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
    
    new_contact = {
        "name": name,
        "first_name": first_name,
        "last_name": last_name,
        "profile_url": url,
        "company": req_data.get("company", "").strip(),
        "title": req_data.get("title", "").strip(),
        "status": "Not Started",
        "date_sent": None,
        "date_accepted": None,
        "email": None,
        "phone": None,
        "logs": None
    }
    
    db_data.append(new_contact)
    save_db(db_data, acc_id)
    
    acc_state.add_log(f"Added single profile: {name} ({url})", "success")
    return jsonify({"status": "success", "message": f"Successfully added {name} to list."})

# API - Clear all contacts
@app.route("/api/contacts/clear", methods=["POST"])
def clear_contacts():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "default")
    acc_state = get_account_state(acc_id)
    
    if acc_state.is_running:
        return err_response("Cannot clear contacts while automation is running.")
        
    save_db([], acc_id)
    acc_state.add_log("Database cleared by user.", "warning")
    return jsonify({"status": "success", "message": "Contacts list cleared."})

# API - Delete a single contact
@app.route("/api/contacts/delete", methods=["POST"])
def delete_contact():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "default")
    acc_state = get_account_state(acc_id)
    
    if acc_state.is_running:
        return err_response("Cannot delete contacts while automation is running.")
        
    url = req_data.get("profile_url", "").strip()
    if not url:
        return err_response("Profile URL is required to delete a contact.")
        
    db_data = load_db(acc_id)
    index_to_remove = -1
    for i, contact in enumerate(db_data):
        if contact.get("profile_url", "").strip() == url:
            index_to_remove = i
            break
            
    if index_to_remove == -1:
        return err_response("Contact not found.")
        
    removed = db_data.pop(index_to_remove)
    save_db(db_data, acc_id)
    
    acc_state.add_log(f"Deleted contact: {removed.get('name')} ({url})", "warning")
    return jsonify({"status": "success", "message": f"Successfully deleted {removed.get('name')}."})

# API - Reset specific or all statuses
@app.route("/api/contacts/reset", methods=["POST"])
def reset_contacts():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "default")
    scope = req_data.get("scope", "all") # "all", "failed", "pending"
    acc_state = get_account_state(acc_id)
    
    if acc_state.is_running:
        return err_response("Cannot reset contacts while automation is running.")
        
    db_data = load_db(acc_id)
    reset_count = 0
    for contact in db_data:
        status = contact.get("status", "Not Started")
        if scope == "all":
            contact["status"] = "Not Started"
            contact["date_sent"] = None
            contact["date_accepted"] = None
            contact["email"] = None
            contact["phone"] = None
            contact["logs"] = None
            reset_count += 1
        elif scope == "failed" and status == "Failed":
            contact["status"] = "Not Started"
            contact["logs"] = None
            reset_count += 1
        elif scope == "pending" and status == "Pending":
            contact["status"] = "Not Started"
            contact["date_sent"] = None
            reset_count += 1
            
    save_db(db_data, acc_id)
    acc_state.add_log(f"Reset {reset_count} contact(s) back to 'Not Started' ({scope} scope).", "info")
    return jsonify({"status": "success", "message": f"Successfully reset {reset_count} contacts.", "reset_count": reset_count})

@app.route("/api/launch-login", methods=["POST"])
def launch_login():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "default")
    
    acc_state = get_account_state(acc_id)
    
    if acc_state.is_running:
        return jsonify({
            "status": "success",
            "message": "A browser session or headless auto-login is already active or in progress for this account. Please check the logs below."
        })
    
    try:
        update_account_status_in_registry(acc_id, status="Login Setup", current_action="Awaiting manual login")
        open_linkedin_for_login(acc_id)
        return jsonify({"status": "success", "message": f"Browser launched for login to account '{acc_id}'. Please login to LinkedIn, then click 'Check Login Status'."})
    except Exception as e:
        update_account_status_in_registry(acc_id, status="Idle", current_action="Idle")
        return err_response(f"Failed to launch browser: {str(e)}")

# API - Submit 2FA / Verification code
@app.route("/api/accounts/submit-2fa", methods=["POST"])
def submit_2fa_code():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "").strip()
    code = req_data.get("code", "").strip()
    
    if not acc_id:
        return err_response("Account ID is required.")
    if not code:
        return err_response("Verification code is required.")
        
    acc_state = get_account_state(acc_id)
    if not acc_state.awaiting_2fa:
        return err_response("This account is not currently waiting for a 2FA/Verification code.")
        
    acc_state.two_factor_code = code
    acc_state.add_log(f"User entered verification code: {code}. Transmitting to Playwright...", "info")
    return jsonify({"status": "success", "message": "Verification code transmitted."})

# API - Diagnose Playwright installation in production
@app.route("/api/diagnose-pw", methods=["GET"])
def diagnose_pw():
    import sys
    import subprocess
    
    pw_version = "Unknown"
    try:
        import playwright
        pw_version = playwright.__version__
    except Exception as e:
        pw_version = f"Error: {str(e)}"
        
    pw_browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/data/pw-browsers")
    
    # Run dynamic write test to diagnose permissions
    write_test_result = "Not attempted"
    try:
        os.makedirs(pw_browsers_path, exist_ok=True)
        test_file = os.path.join(pw_browsers_path, "write_test.txt")
        with open(test_file, 'w') as f:
            f.write("OK")
        with open(test_file, 'r') as f:
            content = f.read()
        write_test_result = f"Success! Read: '{content}'"
        os.remove(test_file)
    except Exception as e:
        write_test_result = f"Error: {str(e)}"
        
    path_exists = os.path.exists(pw_browsers_path)
    contents = []
    if path_exists:
        try:
            for root, dirs, files in os.walk(pw_browsers_path):
                depth = root.replace(pw_browsers_path, "").count(os.sep)
                if depth < 3:
                    contents.append(f"{root} (dirs: {dirs}, files: {files[:10]})")
        except Exception as e:
            contents.append(f"Error listing: {str(e)}")
            
    # Also check what's in /data/
    data_contents = []
    try:
        if os.path.exists("/data"):
            data_contents = os.listdir("/data")
    except Exception as e:
        data_contents = [f"Error listing /data: {str(e)}"]

    return jsonify({
        "python_version": sys.version,
        "playwright_version": pw_version,
        "PLAYWRIGHT_BROWSERS_PATH": pw_browsers_path,
        "path_exists": path_exists,
        "write_test": write_test_result,
        "directory_contents": contents,
        "data_contents": data_contents
    })

# API - Start connection automation
@app.route("/api/start", methods=["POST"])
def start_automation():
    config = request.json or {}
    acc_id = config.get("account_id", "default")
    acc_state = get_account_state(acc_id)
    
    if acc_state.is_running:
        return err_response("Automation is already running for this account.")
        
    note_template = config.get("note_template", "Hi {FirstName}, let's connect!")
    send_with_note = config.get("send_with_note", False)
    delay_min = int(config.get("delay_min", 30))
    delay_max = int(config.get("delay_max", 70))
    daily_limit = int(config.get("daily_limit", 25))
    weekly_limit = int(config.get("weekly_limit", 150))
    start_index = config.get("start_index")
    end_index = config.get("end_index")
    
    # Enforce safe delay constraints
    if delay_min < 10:
        delay_min = 10
    if delay_max < delay_min:
        delay_max = delay_min + 10
        
    # Trigger sequential automated queue execution
    run_automation_worker(
        note_template=note_template,
        send_with_note=send_with_note,
        delay_min=delay_min,
        delay_max=delay_max,
        daily_limit=daily_limit,
        weekly_limit=weekly_limit,
        start_index=start_index,
        end_index=end_index,
        account_id=acc_id
    )
    return jsonify({"status": "success", "message": "Account added to automation queue."})

# API - Stop/Pause automation
@app.route("/api/stop", methods=["POST"])
def stop_automation():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "default")
    queue_runner.stop_account(acc_id)
    return jsonify({"status": "success", "message": "Stop signal sent."})

# API - Sync Acceptance
@app.route("/api/sync-acceptance", methods=["POST"])
def sync_acceptance():
    req_data = request.json or {}
    acc_id = req_data.get("account_id", "default")
    acc_state = get_account_state(acc_id)
    
    if acc_state.is_running:
        return err_response("Automation is currently running.")
        
    sync_acceptance_task(acc_id)
    return jsonify({"status": "success", "message": "Sync added to automation queue."})

# API - Upload Excel Sheet
@app.route("/api/upload", methods=["POST"])
def upload_file():
    acc_id = request.form.get("account_id", "default")
    acc_state = get_account_state(acc_id)
    
    if acc_state.is_running:
        return err_response("Cannot upload files while automation is running.")
        
    if 'file' not in request.files:
        return err_response("No file part in the request.")
        
    file = request.files['file']
    if file.filename == '':
        return err_response("No selected file.")
        
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        return err_response("Invalid file type. Please upload an Excel sheet (.xlsx or .xls).")
        
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    acc_state.add_log(f"Excel file uploaded: {filename}. Parsing contents...", "info")
    try:
        wb = openpyxl.load_workbook(filepath, data_only=True)
        sheet = wb.active
        
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return err_response("The uploaded Excel sheet is empty.")
            
        header = [str(cell).strip().lower() if cell is not None else "" for cell in rows[0]]
        
        def find_column(keywords):
            for idx, h in enumerate(header):
                if any(k in h for k in keywords):
                    return idx
            return -1
            
        url_idx = find_column(["linkedin", "url", "profile", "link", "href"])
        if url_idx == -1:
            found_idx = -1
            for row in rows[:5]:
                for idx, val in enumerate(row):
                    if val and "linkedin.com/in" in str(val):
                        found_idx = idx
                        break
                if found_idx != -1:
                    break
            url_idx = found_idx
            
        if url_idx == -1:
            return err_response("Could not find a LinkedIn URL column in your sheet. Please ensure it contains a column with 'LinkedIn' or profile URLs.")
            
        first_name_idx = find_column(["first name", "firstname", "first"])
        last_name_idx = find_column(["last name", "lastname", "last"])
        full_name_idx = find_column(["name", "full name", "fullname", "contact"])
        company_idx = find_column(["company", "organization", "firm", "employer"])
        title_idx = find_column(["title", "role", "designation", "position"])
        
        contacts_added = 0
        skipped_duplicates = 0
        skipped_invalid = 0
        existing_db = load_db(acc_id)
        existing_urls = {c.get("profile_url", "").strip().split('?')[0].rstrip('/') for c in existing_db}
        
        acc_state.add_log(f"Sheet has {len(rows)-1} data rows. Existing contacts in DB: {len(existing_db)}. Parsing now...", "info")
        
        new_contacts = []
        for row_idx, row in enumerate(rows[1:], start=2):
            if row_idx > len(rows):
                break
                
            url_val = row[url_idx] if url_idx < len(row) else None
            if not url_val:
                continue
                
            url = str(url_val).strip()
            norm_url, url_error = validate_and_normalize_linkedin_url(url)
            if url_error:
                acc_state.add_log(f"Row {row_idx}: Skipped - invalid URL '{url}': {url_error}", "warning")
                skipped_invalid += 1
                continue
            url = norm_url
            norm_url = url.split('?')[0].rstrip('/')
            if norm_url in existing_urls:
                acc_state.add_log(f"Row {row_idx}: Skipped - already in database: {norm_url}", "info")
                skipped_duplicates += 1
                continue
                
            first_name = ""
            last_name = ""
            full_name = ""
            
            if first_name_idx != -1 and first_name_idx < len(row) and row[first_name_idx]:
                first_name = str(row[first_name_idx]).strip()
            if last_name_idx != -1 and last_name_idx < len(row) and row[last_name_idx]:
                last_name = str(row[last_name_idx]).strip()
            if full_name_idx != -1 and full_name_idx < len(row) and row[full_name_idx]:
                full_name = str(row[full_name_idx]).strip()
                
            if not full_name:
                if first_name or last_name:
                    full_name = f"{first_name} {last_name}".strip()
                else:
                    username = url.split("/in/")[-1].split("/")[0].replace("-", " ")
                    full_name = username.title()
                    
            if not first_name and full_name:
                parts = full_name.split()
                first_name = parts[0] if parts else ""
                last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
                
            company = ""
            title = ""
            if company_idx != -1 and company_idx < len(row) and row[company_idx]:
                company = str(row[company_idx]).strip()
            if title_idx != -1 and title_idx < len(row) and row[title_idx]:
                title = str(row[title_idx]).strip()
                
            new_contact = {
                "name": full_name,
                "first_name": first_name,
                "last_name": last_name,
                "profile_url": url,
                "company": company,
                "title": title,
                "status": "Not Started",
                "date_sent": None,
                "date_accepted": None,
                "email": None,
                "phone": None,
                "logs": None
            }
            new_contacts.append(new_contact)
            existing_urls.add(norm_url)
            contacts_added += 1
            acc_state.add_log(f"Row {row_idx}: Added '{full_name}'", "success")
            
        merged_db = existing_db + new_contacts
        save_db(merged_db, acc_id)
        
        summary = f"Added: {contacts_added} | Duplicates skipped: {skipped_duplicates} | Invalid URLs: {skipped_invalid}"
        acc_state.add_log(f"Excel import complete. {summary}", "success")
        try: os.remove(filepath)
        except: pass
        return jsonify({
            "status": "success",
            "message": f"Successfully loaded {contacts_added} profiles from Excel.",
            "added_count": contacts_added,
            "skipped_duplicates": skipped_duplicates,
            "skipped_invalid": skipped_invalid
        })
    except Exception as e:
        acc_state.add_log(f"Error parsing Excel: {str(e)}", "error")
        return err_response(f"Failed to process Excel file: {str(e)}")

if __name__ == "__main__":
    # Create empty database structures if not present and reset stale statuses
    accounts = load_accounts_registry()
    dirty = False
    for acc in accounts:
        acc_id = acc.get("id")
        db_path = automation.get_db_path(acc_id)
        if not os.path.exists(db_path):
            save_db([], acc_id)
            
        # Reset stale active statuses (Running, Queued, Login Setup) back to Idle
        if acc.get("status") in ["Queued", "Running", "Login Setup"]:
            acc["status"] = "Idle"
            acc["current_action"] = "Idle"
            acc["progress_percent"] = 0
            dirty = True
            
    if dirty:
        save_accounts_registry(accounts)

    print("--------------------------------------------------")
    print("   LinkedIn Connection Automator Backend Active   ")
    print("--------------------------------------------------")
    app.run(host="0.0.0.0", port=5000, debug=False)
