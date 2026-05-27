import os

# Dynamic Writable Paths Resolver
def resolve_base_paths():
    # Try writing to /data to verify mount permissions
    data_writable = False
    try:
        os.makedirs("/data", exist_ok=True)
        test_file = "/data/.write_test"
        with open(test_file, 'w') as f:
            f.write("OK")
        os.remove(test_file)
        data_writable = True
    except Exception:
        data_writable = False
        
    if data_writable:
        print("[PATH RESOLVER] Persistent /data disk is writable. Using persistent directories.")
        browsers_path = "/data/pw-browsers"
        user_data_path = "/data/linkedin_user_data"
        accounts_db_path = "/data/accounts_db"
        accounts_json_path = "/data/accounts.json"
    else:
        print("[PATH RESOLVER] Persistent /data disk is not writable. Falling back to local directories.")
        base_dir = os.path.dirname(os.path.abspath(__file__))
        browsers_path = os.path.join(base_dir, "pw-browsers")
        user_data_path = os.path.join(base_dir, "linkedin_user_data")
        accounts_db_path = os.path.join(base_dir, "accounts_db")
        accounts_json_path = os.path.join(base_dir, "accounts.json")
        
    return browsers_path, user_data_path, accounts_db_path, accounts_json_path

BROWSERS_PATH, USER_DATA_PATH, ACCOUNTS_DB_PATH, ACCOUNTS_REGISTRY_PATH = resolve_base_paths()

os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSERS_PATH
import json
import time
import random
import threading
from datetime import datetime
import re
from playwright.sync_api import sync_playwright

BASE_USER_DATA_DIR = os.path.join(USER_DATA_PATH, "profiles")
BASE_ACCOUNTS_DB_DIR = ACCOUNTS_DB_PATH
DB_PATH = os.path.join(BASE_ACCOUNTS_DB_DIR, "db_default.json")

class AutomationState:
    def __init__(self):
        self.is_running = False
        self.logs = []
        self.current_action = "Idle"
        self.progress_percent = 0
        self.stop_requested = False
        self.awaiting_2fa = False
        self.two_factor_code = None
        self._lock = threading.Lock()
        
    def start_running(self):
        with self._lock:
            if self.is_running:
                return False
            self.is_running = True
            self.stop_requested = False
            return True

    def stop_running(self):
        with self._lock:
            self.is_running = False
            
    def add_log(self, text, type="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {"time": timestamp, "message": text, "type": type}
        with self._lock:
            self.logs.append(log_entry)
            if len(self.logs) > 200:
                self.logs.pop(0)
        print(f"[{timestamp}] [{type.upper()}] {text}")

    def update_status(self, action=None, progress=None):
        with self._lock:
            if action is not None:
                self.current_action = action
            if progress is not None:
                self.progress_percent = progress

    def get_state(self):
        with self._lock:
            return {
                "is_running": self.is_running,
                "current_action": self.current_action,
                "progress_percent": self.progress_percent,
                "logs": self.logs,
                "awaiting_2fa": self.awaiting_2fa
            }

# Multi-account state management
account_states = {}
states_lock = threading.Lock()

def get_account_state(account_id="default"):
    with states_lock:
        if account_id not in account_states:
            account_states[account_id] = AutomationState()
        return account_states[account_id]

# Backward compatibility global state reference
state = get_account_state("default")

# Registry Access Helpers
def load_accounts_registry():
    if not os.path.exists(ACCOUNTS_REGISTRY_PATH):
        # Create a default registry if missing
        default_acc = {
            "id": "default",
            "name": "Primary Account",
            "proxy": None,
            "config": {
                "note_template": "Hi {FirstName}, let's connect!",
                "send_with_note": False,
                "delay_min": 30,
                "delay_max": 70,
                "daily_limit": 25,
                "weekly_limit": 150
            },
            "status": "Idle",
            "current_action": "Idle",
            "progress_percent": 0
        }
        try:
            with open(ACCOUNTS_REGISTRY_PATH, 'w', encoding='utf-8') as f:
                json.dump([default_acc], f, indent=4)
            return [default_acc]
        except Exception:
            return []
    try:
        with open(ACCOUNTS_REGISTRY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def save_accounts_registry(accounts):
    try:
        with open(ACCOUNTS_REGISTRY_PATH, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=4)
    except Exception as e:
        print(f"[ERROR] Registry save failed: {str(e)}")

def update_account_status_in_registry(account_id, status=None, current_action=None, progress_percent=None):
    accounts = load_accounts_registry()
    updated = False
    for acc in accounts:
        if acc.get("id") == account_id:
            if status is not None:
                acc["status"] = status
            if current_action is not None:
                acc["current_action"] = current_action
            if progress_percent is not None:
                acc["progress_percent"] = progress_percent
            updated = True
            break
    if updated:
        save_accounts_registry(accounts)

# Per-Account Database Helpers
def get_db_path(account_id):
    return os.path.join(BASE_ACCOUNTS_DB_DIR, f"db_{account_id}.json")

def load_db(account_id="default"):
    db_path = get_db_path(account_id)
    if not os.path.exists(db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        save_db([], account_id)
        return []
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        acc_state = get_account_state(account_id)
        acc_state.add_log(f"Error loading database: {str(e)}", "error")
        return []

def save_db(data, account_id="default"):
    db_path = get_db_path(account_id)
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        acc_state = get_account_state(account_id)
        acc_state.add_log(f"Error saving database: {str(e)}", "error")

def resolve_template(template, contact):
    """
    Replaces tags like {FirstName}, {LastName}, {Company} with values from the contact dictionary.
    """
    if not template:
        return ""
    full_name = contact.get("name", "")
    first_name = contact.get("first_name", "")
    last_name = contact.get("last_name", "")
    
    if not first_name and full_name:
        parts = full_name.split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    replacements = {
        "{FirstName}": first_name or full_name or "there",
        "{LastName}": last_name or "",
        "{FullName}": full_name or "there",
        "{Company}": contact.get("company", "") or "your company",
        "{Title}": contact.get("title", "") or "your role"
    }
    
    resolved = template
    for tag, value in replacements.items():
        resolved = resolved.replace(tag, value)
    return resolved

# Persistent browser launcher with proxy routing support
def launch_browser(account_id="default", headed=True, proxy_config=None):
    acc_state = get_account_state(account_id)
    
    import platform
    if platform.system().lower() == "linux":
        acc_state.add_log("Linux environment detected. Forcing browser to launch in headless mode.", "info")
        headed = False

    acc_state.add_log(f"Launching persistent browser for '{account_id}' ({'headed' if headed else 'headless'})...", "info")
    pw = sync_playwright().start()
    
    user_data_dir = os.path.join(BASE_USER_DATA_DIR, account_id)
    os.makedirs(user_data_dir, exist_ok=True)
    
    pw_proxy = None
    if proxy_config:
        pw_proxy = {
            "server": proxy_config["server"]
        }
        if proxy_config.get("username"):
            pw_proxy["username"] = proxy_config["username"]
            pw_proxy["password"] = proxy_config["password"]
            
    executable_path = None
    if platform.system().lower() == "linux":
        for root, dirs, files in os.walk(BROWSERS_PATH):
            for file in files:
                if file in ["chrome", "chrome-headless-shell", "chromium"]:
                    full_path = os.path.join(root, file)
                    # Verify it's executable
                    if os.access(full_path, os.X_OK):
                        executable_path = full_path
                        # Prefer chrome over headless shell if we find multiple
                        if file == "chrome":
                            break
            if executable_path and os.path.basename(executable_path) == "chrome":
                break
                
        if executable_path:
            acc_state.add_log(f"Dynamic Path Resolver: Located Chromium executable at '{executable_path}'", "info")
        else:
            acc_state.add_log("Standard Chromium executable not found in dynamic search. Letting Playwright auto-resolve...", "warning")
    else:
        executable_path = find_chrome_executable()
        
    try:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=executable_path,
            headless=not headed,
            viewport={"width": 1280, "height": 800},
            proxy=pw_proxy,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
    except Exception as e:
        acc_state.add_log(f"Browser launch failed (cache corrupted): {str(e)}. Self-healing by wiping profile cache...", "warning")
        import shutil
        shutil.rmtree(user_data_dir, ignore_errors=True)
        # Try launching again after wiping the corrupted cache
        context = pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=executable_path,
            headless=not headed,
            viewport={"width": 1280, "height": 800},
            proxy=pw_proxy,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        
    context.set_default_timeout(20000)
    
    # Inject secure session cookie from Render Environment Variables if available
    li_at_env = os.environ.get("LI_AT_COOKIE")
    if li_at_env and not headed:
        clean_cookie = li_at_env.strip().strip('"').strip("'")
        context.add_cookies([{
            "name": "li_at",
            "value": clean_cookie,
            "url": "https://www.linkedin.com",
            "path": "/",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None"
        }])
        acc_state.add_log("Successfully injected secure LI_AT_COOKIE from Render environment variables!", "success")
        
    return pw, context

def check_login_status(page):
    """
    Checks if user is logged into LinkedIn. If not, directs them to login.
    """
    try:
        # Use wait_until="commit" with a generous timeout to resolve instantly on server response, 
        # avoiding freezes from assets or trackers that could block domcontentloaded.
        page.goto("https://www.linkedin.com/feed/", wait_until="commit", timeout=30000)
        time.sleep(4)
        if "login" in page.url or "signup" in page.url or page.locator("a:has-text('Sign in')").is_visible():
            try:
                screenshot_dir = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c"
                os.makedirs(screenshot_dir, exist_ok=True)
                page.screenshot(path=os.path.join(screenshot_dir, "debug_login_status.png"))
                public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
                page.screenshot(path=os.path.join(public_dir, "debug_login_status.png"))
            except Exception:
                pass
            return False
        return True
    except Exception:
        return False

def test_login_session(account_id="default"):
    """
    Spawns a quick headless Playwright instance for this account_id to test if its session cookies are valid.
    Returns True if logged in, False if logged out or error.
    """
    acc_state = get_account_state(account_id)
    playwright = None
    context = None
    try:
        # Load proxy config if exists
        proxy_cfg = None
        accounts = load_accounts_registry()
        for acc in accounts:
            if acc.get("id") == account_id:
                proxy_cfg = acc.get("proxy")
                break
                
        playwright, context = launch_browser(account_id, headed=False, proxy_config=proxy_cfg)
        page = context.new_page()
        
        # Navigate to feed to see if we're authenticated (using wait_until="commit" for speed and reliability)
        page.goto("https://www.linkedin.com/feed/", wait_until="commit", timeout=25000)
        time.sleep(4)
        
        # If we redirect to log in or see sign-in, we are NOT logged in
        if "login" in page.url or "signup" in page.url or page.locator("a:has-text('Sign in')").is_visible():
            return False
            
        return True
    except Exception as e:
        acc_state.add_log(f"Session test exception: {str(e)}", "warning")
        return False
    finally:
        if context:
            try: context.close()
            except: pass
        if playwright:
            try: playwright.stop()
            except: pass

def perform_auto_login(page, account_id, acc_state):
    """
    Checks if credentials exist and fills them automatically on the login page.
    Handles verification challenges (2FA) interactively when running headlessly.
    """
    # Fetch credentials
    li_username = None
    li_password = None
    accounts = load_accounts_registry()
    for acc in accounts:
        if acc.get("id") == account_id:
            li_username = acc.get("li_username")
            li_password = acc.get("li_password")
            break
            
    if not li_username or not li_password:
        acc_state.add_log("No stored LinkedIn credentials found for auto-login. Please login manually.", "info")
        return False
        
    try:
        # First check if we are already authenticated (e.g. via injected LI_AT_COOKIE environment variable)
        acc_state.add_log("Checking current authentication state...", "info")
        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="commit", timeout=30000)
            time.sleep(4)
            if "login" not in page.url and "signup" not in page.url and not page.locator("a:has-text('Sign in')").is_visible():
                acc_state.add_log("Session already authenticated via secure cookies! Bypassing auto-login.", "success")
                return True
        except Exception as e:
            acc_state.add_log(f"Feed check warning: {str(e)}", "warning")
            
        # Check if we are on login page, if not, go there
        if "login" not in page.url:
            acc_state.add_log("Navigating to login page for auto-login...", "info")
            try:
                page.goto("https://www.linkedin.com/login", wait_until="commit", timeout=30000)
            except Exception as e:
                acc_state.add_log(f"Initial navigation warning: {str(e)}. Retrying...", "warning")
                page.goto("https://www.linkedin.com/login", wait_until="commit", timeout=30000)
            time.sleep(3)
            
        acc_state.add_log("Auto-filling LinkedIn login credentials...", "info")
        
        # Robust Username Selector Discovery
        username_sel = None
        # Use Playwright's :visible pseudo-class to prevent matching hidden honeypot/mobile inputs that come first in the DOM
        user_selectors = ["#username:visible", "input[name='session_key']:visible", "#session_key:visible", "input[autocomplete='username']:visible", "input[type='email']:visible"]
        
        # Wait up to 15 seconds for any of the username selectors to become visible
        combined_user_selector = ", ".join(user_selectors)
        try:
            page.wait_for_selector(combined_user_selector, timeout=15000)
            for sel in user_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible():
                        username_sel = sel
                        break
                except:
                    continue
        except Exception as e:
            current_url = page.url
            page_title = "Unknown"
            try: page_title = page.title()
            except: pass
            acc_state.add_log(f"Username selectors wait timed out on '{current_url}' (Title: '{page_title}'): {str(e)}", "warning")
            
        if not username_sel:
            current_url = page.url
            page_title = "Unknown"
            try: page_title = page.title()
            except: pass
            acc_state.add_log(f"Login failure diagnostics -> Current URL: '{current_url}', Page Title: '{page_title}'", "info")
            # Capture error screenshot to see if a CAPTCHA or blocking page was rendered
            try:
                public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
                os.makedirs(public_dir, exist_ok=True)
                scr_path = os.path.join(public_dir, f"login_failed_{account_id}.png")
                page.screenshot(path=scr_path)
                acc_state.add_log(f"Login fields missing. Captured debug screenshot. You can view the visual barrier at /login_failed_{account_id}.png", "error")
            except Exception as e:
                acc_state.add_log(f"Failed to capture debug screenshot: {str(e)}", "warning")
            raise Exception(f"LinkedIn login input fields not found on '{current_url}' (Title: '{page_title}'). The page might be showing a CAPTCHA, security challenge, or IP block.")
            
        # Fill Username
        page.fill(username_sel, li_username)
        time.sleep(random.uniform(0.5, 1.2))
        
        # Robust Password Selector Discovery
        password_sel = None
        pass_selectors = ["#password:visible", "input[name='session_password']:visible", "#session_password:visible", "input[autocomplete='current-password']:visible", "input[type='password']:visible"]
        
        # Wait up to 10 seconds for any password selectors to become visible
        combined_pass_selector = ", ".join(pass_selectors)
        try:
            page.wait_for_selector(combined_pass_selector, timeout=10000)
            for sel in pass_selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible():
                        password_sel = sel
                        break
                except:
                    continue
        except Exception as e:
            acc_state.add_log(f"Password selectors wait timed out: {str(e)}", "warning")
            
        if not password_sel:
            raise Exception("Password input field not found on page.")
            
        # Fill Password
        page.fill(password_sel, li_password)
        time.sleep(random.uniform(0.5, 1.2))
        
        # Click login button
        submit_btn = page.locator("button[type='submit']:visible, button:has-text('Sign in'):visible").first
        submit_btn.wait_for(state="visible", timeout=5000)
        submit_btn.click()
        
        acc_state.add_log("Submitted login credentials automatically.", "success")
        time.sleep(6) # Wait to let the redirect/session settle or security check render
        
        # Detect security verification challenge (2FA)
        is_checkpoint = "checkpoint" in page.url or "security" in page.url or page.locator("input[placeholder*='code']").is_visible() or page.locator("input#input-code").is_visible()
        
        if is_checkpoint:
            acc_state.add_log("LinkedIn Security Checkpoint / 2FA detected!", "warning")
            
            # Save visual challenge screenshot for the user
            try:
                public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
                os.makedirs(public_dir, exist_ok=True)
                screenshot_path = os.path.join(public_dir, f"checkpoint_{account_id}.png")
                page.screenshot(path=screenshot_path)
                acc_state.add_log(f"Saved visual challenge screenshot to dashboard directory.", "info")
            except Exception as e:
                acc_state.add_log(f"Failed to capture visual challenge screenshot: {str(e)}", "warning")
                
            acc_state.awaiting_2fa = True
            acc_state.two_factor_code = None
            update_account_status_in_registry(account_id, status="Awaiting 2FA", current_action="Enter 2FA/Verification Code")
            
            acc_state.add_log("Awaiting 2FA Verification Code from your dashboard Settings panel (Timeout: 3 minutes)...", "warning")
            
            # Poll state waiting for the user to submit their code from the frontend
            wait_timeout = 180
            code_received = False
            for i in range(wait_timeout):
                if acc_state.stop_requested:
                    acc_state.add_log("Login setup stopped by user request.", "warning")
                    break
                if acc_state.two_factor_code:
                    code_received = True
                    break
                time.sleep(1)
                if i % 15 == 0 and i > 0:
                    acc_state.add_log(f"Still waiting for verification code... ({wait_timeout - i}s left)", "info")
                    
            if code_received:
                code = acc_state.two_factor_code
                acc_state.add_log(f"Verification code received: {code}. Injecting into form...", "success")
                
                # Fill the OTP field
                code_filled = False
                otp_selectors = ["input#input-code", "input[name='pin']", "input[placeholder*='code']", "input[autocomplete='one-time-code']", "input[type='text']", "input[type='number']"]
                for selector in otp_selectors:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible():
                            el.fill(code)
                            code_filled = True
                            acc_state.add_log(f"Filled code using selector: '{selector}'", "info")
                            break
                    except:
                        continue
                        
                if not code_filled:
                    try:
                        page.keyboard.type(code)
                        code_filled = True
                        acc_state.add_log("Filled code using keyboard typing emulation.", "info")
                    except Exception as e:
                        acc_state.add_log(f"Could not fill code: {str(e)}", "error")
                        
                if code_filled:
                    time.sleep(random.uniform(0.6, 1.2))
                    # Submit the OTP code
                    submit_clicked = False
                    btn_selectors = ["button#submit-code", "button[type='submit']", "button:has-text('Submit')", "button:has-text('Verify')", "button:has-text('Next')"]
                    for b_sel in btn_selectors:
                        try:
                            btn = page.locator(b_sel).first
                            if btn.is_visible():
                                btn.click()
                                submit_clicked = True
                                acc_state.add_log(f"Clicked verify button using selector: '{b_sel}'", "info")
                                break
                        except:
                            continue
                            
                    if not submit_clicked:
                        try:
                            page.keyboard.press("Enter")
                            submit_clicked = True
                            acc_state.add_log("Submitted form using 'Enter' key emulation.", "info")
                        except:
                            pass
                            
                    acc_state.add_log("Verification submitted! Awaiting LinkedIn redirect...", "info")
                    time.sleep(6)
            else:
                acc_state.add_log("Timed out waiting for LinkedIn 2FA verification code.", "error")
                
            acc_state.awaiting_2fa = False
            acc_state.two_factor_code = None
            
        return True
    except Exception as ex:
        acc_state.add_log(f"Auto-fill login failed or bypassed: {str(ex)}", "warning")
        return False

import subprocess

def find_chrome_executable():
    """
    Locates the standard Google Chrome executable path on Windows.
    """
    paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def open_linkedin_for_login(account_id="default"):
    """
    Utility to open standard Google Chrome natively so user can perform their profile sync,
    install extensions, sign in to their Google/Chrome account, and log in to LinkedIn manually.
    """
    acc_state = get_account_state(account_id)
    if not acc_state.start_running():
        acc_state.add_log("System is currently busy (another automation or browser task is active).", "warning")
        return
        
    def run():
        acc_state.update_status(action="Opening login window...")
        update_account_status_in_registry(account_id, status="Login Setup", current_action="Opening login browser...")
        
        try:
            # Fetch proxy if configured
            proxy_cfg = None
            accounts = load_accounts_registry()
            for acc in accounts:
                if acc.get("id") == account_id:
                    proxy_cfg = acc.get("proxy")
                    break
                    
            import platform
            if platform.system().lower() == "linux":
                acc_state.add_log("Cloud environment detected. Switching 'Launch Browser' to Headless Auto-Login...", "info")
                playwright, context = launch_browser(account_id, headed=False, proxy_config=proxy_cfg)
                try:
                    page = context.new_page()
                    success = perform_auto_login(page, account_id, acc_state)
                    if success:
                        acc_state.add_log("Headless Auto-Login completed.", "success")
                    else:
                        acc_state.add_log("Headless Auto-Login failed. Please ensure credentials are saved in settings.", "error")
                except Exception as ex:
                    acc_state.add_log(f"Headless login exception: {str(ex)}", "error")
                finally:
                    try: context.close()
                    except: pass
                    try: playwright.stop()
                    except: pass
                return

            chrome_path = find_chrome_executable()
            if not chrome_path:
                raise Exception("Google Chrome executable not found on standard paths on Windows. Please install Google Chrome.")
                
            user_data_dir = os.path.join(BASE_USER_DATA_DIR, account_id)
            os.makedirs(user_data_dir, exist_ok=True)
            
            # Formulate arguments to open native Chrome, showing the profile setup/picker if first time
            # and routing to our custom onboarding page first so the user can sync their Chrome staff.
            # NO automation flags are used to guarantee 100% full sync/Google Sign-In support!
            cmd = [
                chrome_path,
                f"--user-data-dir={user_data_dir}",
                f"http://127.0.0.1:5000/setup_welcome.html?account_id={account_id}"
            ]
            
            if proxy_cfg and proxy_cfg.get("server"):
                srv = proxy_cfg["server"].strip()
                if srv:
                    cmd.append(f"--proxy-server={srv}")
                    acc_state.add_log(f"Routing browser setup through proxy: {srv}", "info")
            
            acc_state.add_log("Launching native Google Chrome. Please follow the instructions on the setup page to sync your profile first, then log in.", "success")
            
            proc = subprocess.Popen(cmd)
            
            # Poll process to wait for user to close browser window (up to 15 minutes)
            closed = False
            for _ in range(900): # Wait up to 15 minutes
                if acc_state.stop_requested:
                    try: proc.terminate()
                    except: pass
                    break
                
                if proc.poll() is not None:
                    acc_state.add_log("Chrome browser window closed by the user.", "info")
                    closed = True
                    break
                time.sleep(1)
                
            if not closed and proc.poll() is None:
                acc_state.add_log("Login window session timed out. Closing browser...", "warning")
                try: proc.terminate()
                except: pass
                
        except Exception as e:
            acc_state.add_log(f"Error during manual login setup: {str(e)}", "error")
        finally:
            acc_state.stop_running()
            acc_state.update_status(action="Idle")
            update_account_status_in_registry(account_id, status="Idle", current_action="Idle", progress_percent=0)

    threading.Thread(target=run, daemon=True).start()


def scrape_contact_info(page, username, account_id="default"):
    """
    Extracts email and phone from a connected LinkedIn profile's Contact Info overlay.
    Uses JavaScript evaluation for robust extraction. LinkedIn renders the overlay as
    <dialog data-testid="dialog" open>, NOT .artdeco-modal (as of 2025+).
    """
    email = None
    phone = None
    acc_state = get_account_state(account_id)
    try:
        # Check if we are already on this user's profile page to avoid duplicate navigation
        current_url = page.url
        target_in = f"/in/{username}"
        if target_in not in current_url:
            profile_url = f"https://www.linkedin.com/in/{username}/"
            acc_state.add_log(f"Enriching contact info: navigating to profile: {profile_url}...", "info")
            page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(random.uniform(3, 4.5))
        else:
            acc_state.add_log("Already on target profile page. Directly opening contact info...", "info")
            
        # Click Contact info link to trigger the overlay/section
        clicked = False
        contact_info_selectors = [
            "a:has-text('Contact info')",
            "#top-card-relationship-reveal-contact-info",
            "a[href*='contact-info']",
            "a[href*='/overlay/contact-info/']"
        ]
        
        # Wait a moment to ensure rendering is fully settled
        try:
            page.locator("a:has-text('Contact info'), #top-card-relationship-reveal-contact-info").first.wait_for(state="visible", timeout=4000)
        except:
            pass
            
        for selector in contact_info_selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    acc_state.add_log(f"Clicking Contact info link via selector: '{selector}'", "info")
                    el.click(force=True)
                    clicked = True
                    break
            except Exception:
                continue
                
        if not clicked:
            acc_state.add_log("Could not locate or open the Contact Info link.", "warning")
            return None, None
            
        time.sleep(random.uniform(2.5, 4))  # Wait for the dialog to render

        # Smart extraction
        try:
            username_for_js = re.sub(r'[^a-z0-9]', '', username.lower())
            email = page.evaluate("""(usernameClean) => {
                const dialog = document.querySelector('.pv-contact-info-modal') ||
                               document.querySelector('.artdeco-modal') ||
                               document.querySelector('dialog[open]') ||
                               document.querySelector('[data-testid="dialog"]') ||
                               document.querySelector('[role="dialog"].artdeco-modal') ||
                               document.querySelector('[role="dialog"]');
                let links = dialog ? Array.from(dialog.querySelectorAll('a[href^="mailto:"]')) : [];
                if (links.length === 0) {
                    links = Array.from(document.querySelectorAll('a[href^="mailto:"]'));
                }
                if (links.length === 0) return null;
                const byUsername = links.find(l => {
                    const addr = l.href.replace('mailto:', '').split('?')[0].trim();
                    const local = addr.split('@')[0].toLowerCase().replace(/[^a-z0-9]/g, '');
                    return usernameClean && (local.includes(usernameClean) || usernameClean.includes(local));
                });
                if (byUsername) return byUsername.href.replace('mailto:', '').split('?')[0].trim();
                if (dialog) {
                    const allEls = Array.from(dialog.querySelectorAll('*'));
                    for (const el of allEls) {
                        const txt = (el.textContent || '').trim();
                        if ((txt === 'Email address' || txt === 'Email') && el.children.length === 0) {
                            let cur = el.parentElement;
                            for (let i = 0; i < 6; i++) {
                                if (!cur) break;
                                const link = cur.querySelector('a[href^="mailto:"]');
                                if (link) {
                                    const addr = link.href.replace('mailto:', '').split('?')[0].trim();
                                    if (addr) return addr;
                                }
                                cur = cur.parentElement;
                            }
                        }
                    }
                }
                return links[links.length - 1].href.replace('mailto:', '').split('?')[0].trim();
            }""", username_for_js)
            if email:
                acc_state.add_log(f"Extracted email via JS: {email}", "info")
        except Exception as e:
            acc_state.add_log(f"JS email extraction failed: {str(e)}", "warning")

        try:
            phone_raw = page.evaluate(r"""() => {
                const dialog = document.querySelector('.pv-contact-info-modal') ||
                               document.querySelector('.artdeco-modal') ||
                               document.querySelector('dialog[open]') ||
                               document.querySelector('[data-testid="dialog"]') ||
                               document.querySelector('[role="dialog"].artdeco-modal') ||
                               document.querySelector('[role="dialog"]') ||
                               document.body;
                const telLink = dialog.querySelector('a[href^="tel:"]');
                if (telLink) return telLink.href.replace('tel:', '').trim();
                const allEls = Array.from(dialog.querySelectorAll('*'));
                for (const el of allEls) {
                    const txt = (el.textContent || '').trim();
                    if ((txt === 'Phone' || txt === 'Phone number') && el.children.length === 0) {
                        let cur = el.parentElement;
                        for (let i = 0; i < 6; i++) {
                            if (!cur) break;
                            const children = Array.from(cur.children);
                            for (const child of children) {
                                if (child === el) continue;
                                const childTxt = (child.innerText || child.textContent || '').trim();
                                if (/[+]?[\d][\d\s\-()+]{5,}/.test(childTxt)) return childTxt;
                            }
                            cur = cur.parentElement;
                        }
                    }
                }
                const dlgText = dialog.innerText || '';
                const lines = dlgText.split('\\n').map(l => l.trim()).filter(l => l);
                for (let i = 0; i < lines.length; i++) {
                    if (/^(Phone|Mobile|Telephone)$/i.test(lines[i]) && i + 1 < lines.length) {
                        const nxt = lines[i + 1];
                        if (/\d{5,}/.test(nxt)) return nxt;
                    }
                    const concatMatch = lines[i].match(/^(Phone|Mobile|Telephone)\s*([+]?[\d][\d\s\-()+]{5,})/i);
                    if (concatMatch) return concatMatch[2].trim();
                }
                return null;
            }""")
            if phone_raw:
                cleaned = re.sub(r'^(Phone|Mobile|Telephone|Work|Home)\s*', '', phone_raw.strip(), flags=re.IGNORECASE).strip()
                cleaned = re.sub(r'\s*\([^)]*\)\s*$', '', cleaned).strip()
                phone = cleaned if cleaned and any(c.isdigit() for c in cleaned) else phone_raw.strip()
                acc_state.add_log(f"Extracted phone via JS: {phone}", "info")
        except Exception as e:
            acc_state.add_log(f"JS phone extraction failed: {str(e)}", "warning")

        connection_date = None
        try:
            connection_date_raw = page.evaluate(r"""() => {
                const dialog = document.querySelector('.pv-contact-info-modal') ||
                               document.querySelector('.artdeco-modal') ||
                               document.querySelector('dialog[open]') ||
                               document.querySelector('[data-testid="dialog"]') ||
                               document.querySelector('[role="dialog"].artdeco-modal') ||
                               document.querySelector('[role="dialog"]');
                if (!dialog) return null;
                const allEls = Array.from(dialog.querySelectorAll('*'));
                for (const el of allEls) {
                    const txt = (el.textContent || '').trim();
                    if (/^Connected(\s+since)?$/i.test(txt) && el.children.length === 0) {
                        let cur = el.parentElement;
                        for (let i = 0; i < 4; i++) {
                            if (!cur) break;
                            const childTxts = Array.from(cur.childNodes)
                                .map(node => (node.textContent || '').trim())
                                .filter(t => t && !/^Connected(\s+since)?$/i.test(t));
                            for (const t of childTxts) {
                                if (/[A-Za-z]+\s+\d{1,2},\s+\d{4}/.test(t) || /[A-Za-z]+\s+\d{4}/.test(t)) {
                                    return t;
                                }
                            }
                            cur = cur.parentElement;
                        }
                    }
                }
                const dlgText = dialog.innerText || '';
                const lines = dlgText.split('\\n').map(l => l.trim()).filter(l => l);
                for (let i = 0; i < lines.length; i++) {
                    if (/^Connected(\s+since)?$/i.test(lines[i]) && i + 1 < lines.length) {
                        const nxt = lines[i + 1];
                        if (/[A-Za-z]+\s+\d{1,2},\s+\d{4}/.test(nxt) || /[A-Za-z]+\s+\d{4}/.test(nxt)) {
                            return nxt;
                        }
                    }
                    const concatMatch = lines[i].match(/^Connected(?:\s+since)?\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})/i) || 
                                        lines[i].match(/^Connected(?:\s+since)?\s+([A-Za-z]+\s+\d{4})/i);
                    if (concatMatch) return concatMatch[1].trim();
                }
                return null;
            }""")
            if connection_date_raw:
                acc_state.add_log(f"Extracted raw connection date: {connection_date_raw}", "info")
                # Clean prefix "Connected " or "Connected since " if present from the scraped date text
                ds = re.sub(r'^Connected(\s+since)?\s+', '', connection_date_raw.strip(), flags=re.IGNORECASE).strip()
                parsed_dt = None
                for fmt in ("%B %d, %Y", "%b %d, %Y"):
                    try:
                        parsed_dt = datetime.strptime(ds, fmt)
                        break
                    except:
                        pass
                if not parsed_dt:
                    for fmt in ("%B %Y", "%b %Y"):
                        try:
                            parsed_dt = datetime.strptime(ds, fmt)
                            break
                        except:
                            pass
                if parsed_dt:
                    connection_date = parsed_dt.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    connection_date = ds
                acc_state.add_log(f"Parsed connection date: {connection_date}", "info")
        except Exception as e:
            acc_state.add_log(f"JS connection date extraction failed: {str(e)}", "warning")

        acc_state.add_log(f"Scrape Complete -> Email: {email or 'Not Shared'}, Phone: {phone or 'Not Shared'}, Connected: {connection_date or 'Unknown'}", "success")
        try:
            page.keyboard.press("Escape")
            time.sleep(1.0)
        except:
            pass
    except Exception as ex:
        acc_state.add_log(f"Failed to scrape contact info overlay: {str(ex)}", "error")
    return email, phone, connection_date

def verify_profile_status(page, username, acc_state):
    """
    Navigates to a profile and checks if the user is 1st-degree connected, pending, or not connected.
    Returns: 'Connected', 'Pending', 'Not Started', or 'Error' (if page load/navigation fails).
    """
    try:
        profile_url = f"https://www.linkedin.com/in/{username}/"
        acc_state.add_log(f"Verifying status on profile: {profile_url}...", "info")
        
        # Navigate to the profile page
        max_nav_retries = 2
        nav_success = False
        for nav_attempt in range(max_nav_retries):
            try:
                page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
                nav_success = True
                break
            except Exception as nav_err:
                err_str = str(nav_err).lower()
                if username in page.url:
                    nav_success = True
                    break
                if nav_attempt < max_nav_retries - 1:
                    acc_state.add_log(f"Verification navigation failed. Retrying (Attempt {nav_attempt+2}/{max_nav_retries})...", "warning")
                    time.sleep(2)
                else:
                    raise nav_err
        
        if not nav_success:
            return "Error"

        time.sleep(random.uniform(3, 4.5))
        
        # Wait for page layout to settle
        try:
            page.locator("main section h1, main section h2").first.wait_for(state="visible", timeout=8000)
        except:
            pass
            
        # Robust JS-based connection status checker (scoped to profile top card & degree-aware)
        status_result = page.evaluate(r"""
            () => {
                const nameHeader = document.querySelector('main h1');
                const topCard = nameHeader ? (nameHeader.closest('.artdeco-card') || nameHeader.closest('section') || nameHeader.parentElement?.parentElement?.parentElement || document) : (document.querySelector('main section') || document);
                
                const actions = Array.from(topCard.querySelectorAll('button, a'));
                
                // 1. First check: Is there a visible "Connect" button in the top card?
                // If yes, the profile is 100% Not Started (Not Connected).
                const hasConnect = actions.some(el => {
                    if (!el.offsetHeight && !el.offsetWidth) return false;
                    const text = el.textContent.trim().toLowerCase();
                    const label = (el.getAttribute('aria-label') || '').toLowerCase();
                    return (text === 'connect' || (label.includes('invite') && label.includes('connect'))) && !text.includes('remove') && !label.includes('remove');
                });
                
                if (hasConnect) {
                    return { status: "Not Started" };
                }
                
                // 2. Second check: Is there a visible "Pending" / "Sent" / "Request sent" button in the top card?
                // If yes, the profile connection is Pending.
                const hasPending = actions.some(el => {
                    if (!el.offsetHeight && !el.offsetWidth) return false;
                    const text = el.textContent.trim().toLowerCase();
                    const label = (el.getAttribute('aria-label') || '').toLowerCase();
                    
                    if (text === 'pending' || text === 'sent' || label.includes('pending') || label.includes('sent connection')) {
                        return true;
                    }
                    if (text.includes('pending') || text.includes('invitation sent') || text.includes('request sent')) {
                        return true;
                    }
                    return false;
                });
                
                if (hasPending) {
                    return { status: "Pending" };
                }
                
                // 3. Third check: Scan for explicit connection degree badges in the top card
                const allSpans = Array.from(topCard.querySelectorAll('span, div, button, a'));
                let degree = null;
                for (const el of allSpans) {
                    if (!el.offsetHeight && !el.offsetWidth) continue;
                    const text = el.textContent.trim();
                    if (/\b1st\b/i.test(text)) {
                        if (text.length < 30 && !text.toLowerCase().includes("class") && !text.toLowerCase().includes("year") && !text.toLowerCase().includes("anniversary")) {
                            degree = "1st";
                            break;
                        }
                    }
                    if (/\b(2nd|3rd)\b/i.test(text)) {
                        if (text.length < 30 && !text.toLowerCase().includes("class") && !text.toLowerCase().includes("year") && !text.toLowerCase().includes("anniversary")) {
                            degree = "other";
                            break;
                        }
                    }
                }
                
                if (degree === "1st") {
                    return { status: "Connected" };
                }
                
                // 4. Fourth check: If degree is not other, verify if there's a Messaging thread link or valid Message button
                if (degree !== "other") {
                    for (const el of actions) {
                        if (!el.offsetHeight && !el.offsetWidth) continue;
                        const text = el.textContent.trim().toLowerCase();
                        const label = (el.getAttribute('aria-label') || '').toLowerCase();
                        const href = el.getAttribute('href') || '';
                        
                        if (href.includes('/messaging/thread/')) {
                            return { status: "Connected" };
                        }
                        
                        if (text === 'message' || label === 'message' || label.startsWith('message ') || text.startsWith('message ')) {
                            if (!text.includes('inmail') && !label.includes('inmail') && !label.includes('premium')) {
                                return { status: "Connected" };
                            }
                        }
                    }
                }
                
                return { status: "Not Started" };
            }
        """)
        
        detected_status = status_result.get("status", "Not Started")
        acc_state.add_log(f"Profile connection status detected: '{detected_status}'", "info")
        return detected_status
        
    except Exception as e:
        acc_state.add_log(f"Error verifying status on profile for {username}: {str(e)}", "warning")
        return "Error"

def sync_acceptance_task_sync(account_id="default"):
    """
    Goes to LinkedIn Sent Invitations and synchronizes statuses in DB synchronously for an account.
    """
    acc_state = get_account_state(account_id)
    acc_state.update_status(action="Checking sent requests...", progress=10)
    update_account_status_in_registry(account_id, status="Running", current_action="Checking sent requests...", progress_percent=10)
    acc_state.add_log("Starting Acceptance Synchronization...", "info")
    
    playwright = None
    context = None
    try:
        # Load account proxy configuration
        proxy_cfg = None
        accounts = load_accounts_registry()
        for acc in accounts:
            if acc.get("id") == account_id:
                proxy_cfg = acc.get("proxy")
                break

        playwright, context = launch_browser(account_id=account_id, headed=True, proxy_config=proxy_cfg)
        page = context.new_page()
        
        if not check_login_status(page):
            # Fetch credentials
            accounts = load_accounts_registry()
            li_username = None
            li_password = None
            for acc in accounts:
                if acc.get("id") == account_id:
                    li_username = acc.get("li_username")
                    li_password = acc.get("li_password")
                    break
            
            if li_username and li_password:
                acc_state.add_log("Not logged in. Attempting auto-login...", "info")
                perform_auto_login(page, account_id, acc_state)
                if not check_login_status(page):
                    acc_state.add_log("Auto-login failed or security verification required. Please click 'Launch Browser / Login' to complete manual verification.", "error")
                    return
            else:
                acc_state.add_log("Not logged in to LinkedIn and no stored credentials found! Please click 'Launch Browser / Login' first.", "error")
                return
            
        acc_state.add_log("Logged in. Navigating to Sent Invitations page...", "info")
        page.goto("https://www.linkedin.com/mynetwork/invitation-manager/sent/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)
        
        last_count = 0
        no_change_count = 0
        max_scroll_steps = 25
        
        acc_state.add_log("Scrolling through Sent invitations list dynamically to load all pending items...", "info")
        for scroll_step in range(1, max_scroll_steps + 1):
            if acc_state.stop_requested:
                break
            links = page.locator("a").all()
            in_links = [l.get_attribute("href") for l in links if l.get_attribute("href") and "/in/" in l.get_attribute("href")]
            current_count = len(in_links)
            
            withdraw_anchors = page.locator("a:has-text('Withdraw')").all()
            if not withdraw_anchors:
                acc_state.add_log("No Withdraw links visible or list is empty. Ending scroll loop.", "info")
                break
                
            last_anchor = withdraw_anchors[-1]
            try:
                last_anchor.scroll_into_view_if_needed(timeout=4000)
            except Exception as scroll_ex:
                acc_state.add_log(f"Scroll step {scroll_step} encountered an issue: {str(scroll_ex)}", "warning")
                
            time.sleep(2.5)
            acc_state.add_log(f"Scroll step {scroll_step} completed. Found {current_count} profile links so far.", "info")
            progress_pct = 10 + int((scroll_step / max_scroll_steps) * 40)
            acc_state.update_status(action=f"Scrolling invitations list ({current_count} loaded)", progress=progress_pct)
            update_account_status_in_registry(account_id, progress_percent=progress_pct)
            
            if current_count == last_count:
                no_change_count += 1
                if no_change_count >= 3:
                    acc_state.add_log("No new profile links loaded for 3 consecutive attempts. Finished loading list.", "info")
                    break
            else:
                no_change_count = 0
            last_count = current_count
            
        pending_usernames = set()
        links = page.locator("a").all()
        for link in links:
            try:
                href = link.get_attribute("href")
                if href and "/in/" in href:
                    url_clean = href.split("?")[0].rstrip("/")
                    username = url_clean.split("/in/")[-1].strip()
                    if username:
                        pending_usernames.add(username)
            except Exception:
                continue
                
        withdraw_count = len(page.locator("a:has-text('Withdraw')").all())
        empty_state_visible = False
        empty_selectors = [
            ".mn-invitation-manager__no-invitations",
            ":has-text('No sent invitations')",
            ":has-text('You don’t have any sent invitations')",
            ":has-text('No pending invitations')"
        ]
        for sel in empty_selectors:
            try:
                if page.locator(sel).first.is_visible():
                    empty_state_visible = True
                    break
            except:
                continue
                
        acc_state.add_log(f"Final Scrape Result: {len(pending_usernames)} unique pending usernames gathered. Withdraw links: {withdraw_count}.", "info")
        
        if len(pending_usernames) == 0 and not empty_state_visible:
            raise Exception("Page failed to load the invitation manager list (0 pending requests found, but no empty-state message detected). Sync aborted for safety to prevent status corruption.")
            
        db_data = load_db(account_id)
        updated_count = 0
        
        for contact in db_data:
            if acc_state.stop_requested:
                break
            status = contact.get("status", "Not Started")
            url = contact.get("profile_url", "").strip()
            url_clean = url.split("?")[0].rstrip("/")
            contact_username = url_clean.split("/in/")[-1].strip() if "/in/" in url_clean else ""
            contact_name = contact.get("name", "")
            
            # Strict skip rule for Harshit Saxena (Never touch under any sync context)
            if "harshit" in contact_name.lower() or "saxena" in contact_name.lower() or (contact_username and "harshit-saxena" in contact_username.lower()):
                continue
            
            if contact_username and contact_username in pending_usernames:
                if status != "Pending":
                    contact["status"] = "Pending"
                    contact["date_sent"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    acc_state.add_log(f"Status Updated: {contact.get('name', 'Unknown')} is Pending on LinkedIn (Auto-discovered).", "info")
                    updated_count += 1
            else:
                should_enrich = False
                if status in ["Sent", "Pending"]:
                    if contact_username:
                        verified_status = verify_profile_status(page, contact_username, acc_state)
                        if verified_status == "Connected":
                            contact["status"] = "Connected"
                            contact["date_accepted"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            acc_state.add_log(f"Verified connection: {contact_name} is Connected! Initiating contact enrichment...", "success")
                            should_enrich = True
                            updated_count += 1
                        elif verified_status == "Pending":
                            acc_state.add_log(f"Verified status: {contact_name} is still Pending on LinkedIn.", "info")
                        elif verified_status == "Not Started":
                            contact["status"] = "Not Started"
                            contact["date_sent"] = None
                            contact["date_accepted"] = None
                            acc_state.add_log(f"Verified status: {contact_name} has no active pending invitation (likely declined, expired, or withdrawn). Status reset to 'Not Started'.", "warning")
                            updated_count += 1
                        else:
                            acc_state.add_log(f"Verification failed or inconclusive for {contact_name}. Leaving status as Pending for safety.", "warning")
                elif status == "Connected" and (contact.get("email") is None or contact.get("phone") is None or contact.get("date_accepted") is None or contact.get("date_accepted") == ""):
                    acc_state.add_log(f"Profile {contact.get('name', 'Unknown')} is already Connected but lacks complete contact info or genuine connection date. Attempting enrichment...", "info")
                    should_enrich = True
                    
                if should_enrich:
                    if contact_username:
                        try:
                            email, phone, connection_date = scrape_contact_info(page, contact_username, account_id)
                            contact["email"] = email if email else "Not Shared"
                            contact["phone"] = phone if phone else "Not Shared"
                            if connection_date:
                                # If the scraped connection date is today's date, preserve today's precise acceptance time!
                                scraped_date = connection_date.split(" ")[0]
                                today_date = datetime.now().strftime("%Y-%m-%d")
                                if scraped_date == today_date and contact.get("date_accepted") and contact["date_accepted"].startswith(today_date):
                                    # Already has a precise today's timestamp, keep it!
                                    pass
                                else:
                                    contact["date_accepted"] = connection_date
                        except Exception as enrichment_err:
                            acc_state.add_log(f"Enrichment error for {contact.get('name', 'Unknown')}: {str(enrichment_err)}", "warning")
                        finally:
                            try:
                                acc_state.add_log("Returning to Sent Invitations page...", "info")
                                page.goto("https://www.linkedin.com/mynetwork/invitation-manager/sent/", wait_until="domcontentloaded", timeout=30000)
                                time.sleep(3)
                            except Exception as return_err:
                                acc_state.add_log(f"Failed to navigate back to Sent Invitations: {str(return_err)}", "warning")
                    if status == "Connected":
                        updated_count += 1
        
        if updated_count > 0:
            save_db(db_data, account_id)
            acc_state.add_log(f"Acceptance Sync Complete! {updated_count} contact statuses updated.", "success")
        else:
            acc_state.add_log("Acceptance Sync Complete! No status changes detected.", "info")
            
    except Exception as e:
        acc_state.add_log(f"Error during Acceptance Sync: {str(e)}", "error")
        update_account_status_in_registry(account_id, status="Error", current_action="Sync failed")
    finally:
        acc_state.stop_running()
        acc_state.update_status(action="Idle", progress=100)
        update_account_status_in_registry(account_id, status="Idle", current_action="Idle", progress_percent=0)
        if context:
            try: context.close()
            except: pass
        if playwright:
            try: playwright.stop()
            except: pass

def run_automation_worker_sync(account_id="default", config=None):
    """
    Synchronous implementation of the connection requester loop.
    """
    if config is None:
        config = {}
    
    note_template = config.get("note_template", "Hi {FirstName}, let's connect!")
    send_with_note = config.get("send_with_note", False)
    delay_min = int(config.get("delay_min", 30))
    delay_max = int(config.get("delay_max", 70))
    daily_limit = int(config.get("daily_limit", 25))
    weekly_limit = int(config.get("weekly_limit", 150))
    start_index = config.get("start_index")
    end_index = config.get("end_index")
    
    # Safely convert to integers if provided
    try: start_index = int(start_index) if start_index is not None else None
    except: start_index = None
    try: end_index = int(end_index) if end_index is not None else None
    except: end_index = None

    acc_state = get_account_state(account_id)
    acc_state.update_status(action="Starting connection worker...", progress=0)
    update_account_status_in_registry(account_id, status="Running", current_action="Starting connection worker...", progress_percent=0)
    acc_state.add_log("Starting LinkedIn Connection Automation...", "info")
    
    playwright = None
    context = None
    try:
        db_data = load_db(account_id)
        for original_idx, contact in enumerate(db_data, start=1):
            contact["_original_idx"] = original_idx
            
        if start_index is not None or end_index is not None:
            s_idx = start_index if start_index is not None else 1
            e_idx = end_index if end_index is not None else len(db_data)
            s_idx = max(1, s_idx)
            e_idx = min(len(db_data), e_idx)
            
            if s_idx <= e_idx:
                acc_state.add_log(f"Range filter active: targeting profiles from Sr. No. {s_idx} to {e_idx}.", "info")
                db_data_slice = db_data[s_idx - 1 : e_idx]
            else:
                acc_state.add_log(f"Invalid range {s_idx} to {e_idx}. Processing full list.", "warning")
                db_data_slice = db_data
        else:
            db_data_slice = db_data
            
        pending_contacts = [c for c in db_data_slice if c.get("status", "Not Started") == "Not Started"]
        if not pending_contacts:
            acc_state.add_log("No profiles found with 'Not Started' status in the specified range. Please add new contacts, clear the Selective Range inputs, or use the Reset button.", "warning")
            return
            
        acc_state.add_log(f"Found {len(pending_contacts)} profiles to process.", "info")
        
        # Pre-scan limits
        sent_today_count = 0
        sent_week_count = 0
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        for c in db_data:
            ds = c.get("date_sent")
            if ds:
                try:
                    if ds.startswith(today_str):
                        sent_today_count += 1
                    dt = datetime.strptime(ds, "%Y-%m-%d %H:%M:%S")
                    if (now - dt).days < 7:
                        sent_week_count += 1
                except:
                    pass
                    
        acc_state.add_log(f"Safety Pre-Scan: {sent_today_count} sent today, {sent_week_count} sent this week (7 days). Limits: Daily {daily_limit}, Weekly {weekly_limit}.", "info")
        
        if sent_today_count >= daily_limit:
            acc_state.add_log(f"Daily safe quota limit of {daily_limit} reached! Stopping automation to protect your account.", "warning")
            return
        if sent_week_count >= weekly_limit:
            acc_state.add_log(f"Weekly safe quota limit of {weekly_limit} reached! Stopping automation to protect your account.", "warning")
            return
            
        # Launch browser
        proxy_cfg = None
        accounts = load_accounts_registry()
        for acc in accounts:
            if acc.get("id") == account_id:
                proxy_cfg = acc.get("proxy")
                break

        playwright, context = launch_browser(account_id=account_id, headed=True, proxy_config=proxy_cfg)
        page = context.new_page()
        
        if not check_login_status(page):
            # Fetch credentials
            accounts = load_accounts_registry()
            li_username = None
            li_password = None
            for acc in accounts:
                if acc.get("id") == account_id:
                    li_username = acc.get("li_username")
                    li_password = acc.get("li_password")
                    break
            
            if li_username and li_password:
                acc_state.add_log("Not logged in. Attempting auto-login...", "info")
                perform_auto_login(page, account_id, acc_state)
                if not check_login_status(page):
                    acc_state.add_log("Auto-login failed or security verification required. Please click 'Launch Browser / Login' to complete manual verification.", "error")
                    return
            else:
                acc_state.add_log("Not logged in to LinkedIn and no stored credentials found! Please click 'Launch Browser / Login' first.", "error")
                return
            
        acc_state.add_log("Login session validated. Starting request sequences...", "success")
        total_to_process = len(pending_contacts)
        
        for idx, contact in enumerate(pending_contacts):
            if acc_state.stop_requested:
                acc_state.add_log("Automation paused/stopped by user.", "warning")
                break
                
            if sent_today_count >= daily_limit:
                acc_state.add_log(f"Daily safe quota limit of {daily_limit} reached! Stopping automation to protect your account.", "warning")
                break
            if sent_week_count >= weekly_limit:
                acc_state.add_log(f"Weekly safe quota limit of {weekly_limit} reached! Stopping automation to protect your account.", "warning")
                break
            
            is_browser_closed = False
            try:
                if page.is_closed():
                    is_browser_closed = True
            except:
                is_browser_closed = True
                
            if is_browser_closed:
                acc_state.add_log("Browser page was closed or lost. Pausing automation sequence...", "warning")
                break
                
            progress = int((idx / total_to_process) * 100)
            acc_state.update_status(action=f"Processing {contact.get('name', 'Contact')}", progress=progress)
            update_account_status_in_registry(account_id, current_action=f"Processing {contact.get('name', 'Contact')}", progress_percent=progress)
            
            profile_url = contact.get("profile_url", "").strip()
            contact_name = contact.get("name", "")
            
            # Strict skip rule for Harshit Saxena (Never touch under any automation worker context)
            if "harshit" in contact_name.lower() or "saxena" in contact_name.lower() or "harshit-saxena" in profile_url.lower():
                acc_state.add_log(f"[SKIP] Excluding Harshit Saxena from automation actions as requested.", "info")
                continue
                
            if not profile_url:
                contact["status"] = "Failed"
                contact["logs"] = "Empty profile URL"
                continue
                
            orig_idx = contact.get("_original_idx", idx + 1)
            acc_state.add_log(f"[{idx+1}/{total_to_process}] Navigating to profile: {contact.get('name', 'Unknown')} (Sr. No. {orig_idx})...", "info")
            try:
                # Normalize URL
                normalized_url = profile_url
                if "linkedin.com" in profile_url:
                    parts = profile_url.split("linkedin.com")
                    scheme_part = parts[0]
                    path_part = parts[1]
                    if scheme_part.endswith("."):
                        scheme_part = scheme_part.split("://")[0] + "://www."
                    normalized_url = f"{scheme_part}linkedin.com{path_part}"

                max_nav_retries = 2
                nav_success = False
                for nav_attempt in range(max_nav_retries):
                    try:
                        page.goto(normalized_url, wait_until="domcontentloaded", timeout=30000)
                        nav_success = True
                        break
                    except Exception as nav_err:
                        err_str = str(nav_err).lower()
                        target_username = profile_url.split("/in/")[-1].split("/")[0].split('?')[0].rstrip('/')
                        current_url = page.url.split('?')[0].rstrip('/')
                        if target_username in current_url:
                            acc_state.add_log(f"Navigation returned an error, but target profile '{target_username}' is active on page. Proceeding...", "warning")
                            nav_success = True
                            break
                            
                        if nav_attempt < max_nav_retries - 1 and ("interrupted" in err_str or "abort" in err_str or "navigation" in err_str):
                            acc_state.add_log(f"Navigation was interrupted/failed. Retrying in 3 seconds (Attempt {nav_attempt+2}/{max_nav_retries})...", "warning")
                            time.sleep(3)
                            try: page.goto("about:blank")
                            except: pass
                            time.sleep(1)
                        else:
                            if target_username in page.url:
                                nav_success = True
                                break
                            raise nav_err

                try:
                    acc_state.add_log("Waiting for profile layout to render...", "info")
                    page.locator("main section h1, main section h2").first.wait_for(state="visible", timeout=12000)
                    profile_name_text = page.locator("main section h1, main section h2").first.text_content() or ""
                    acc_state.add_log(f"Profile loaded: {profile_name_text.strip()}", "info")
                except Exception as wait_err:
                    acc_state.add_log(f"Profile layout heading did not appear within 12 seconds: {str(wait_err)}. Capturing debug screenshot...", "warning")
                    try:
                        screenshot_dir = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c"
                        os.makedirs(screenshot_dir, exist_ok=True)
                        page.screenshot(path=os.path.join(screenshot_dir, "debug_failure.png"))
                        public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
                        page.screenshot(path=os.path.join(public_dir, "debug_failure.png"))
                        acc_state.add_log("Saved debug screenshot to debug_failure.png", "info")
                    except Exception as ss_err:
                        acc_state.add_log(f"Failed to capture debug screenshot: {str(ss_err)}", "warning")

                time.sleep(random.uniform(3, 5))
                page.evaluate("window.scrollTo(0, 300)")
                time.sleep(1.5)
                
                HEADER_ANCHOR = "xpath=(//main//section[1]//h1 | //main//section[1]//h2)[1]/ancestor::section[1]"
                
                # Robust JS-based connection status checker (scoped to profile top card & degree-aware)
                status_result = page.evaluate("""
                    () => {
                        const nameHeader = document.querySelector('main h1');
                        const topCard = nameHeader ? (nameHeader.closest('.artdeco-card') || nameHeader.closest('section') || nameHeader.parentElement?.parentElement?.parentElement || document) : (document.querySelector('main section') || document);
                        
                        const actions = Array.from(topCard.querySelectorAll('button, a'));
                        
                        // 1. First check: Is there a visible "Connect" button in the top card?
                        // If yes, the profile is 100% Not Started (Not Connected).
                        const hasConnect = actions.some(el => {
                            if (!el.offsetHeight && !el.offsetWidth) return false;
                            const text = el.textContent.trim().toLowerCase();
                            const label = (el.getAttribute('aria-label') || '').toLowerCase();
                            return (text === 'connect' || (label.includes('invite') && label.includes('connect'))) && !text.includes('remove') && !label.includes('remove');
                        });
                        
                        if (hasConnect) {
                            return { status: "Not Started" };
                        }
                        
                        // 2. Second check: Is there a visible "Pending" / "Sent" / "Request sent" button in the top card?
                        // If yes, the profile connection is Pending.
                        const hasPending = actions.some(el => {
                            if (!el.offsetHeight && !el.offsetWidth) return false;
                            const text = el.textContent.trim().toLowerCase();
                            const label = (el.getAttribute('aria-label') || '').toLowerCase();
                            
                            if (text === 'pending' || text === 'sent' || label.includes('pending') || label.includes('sent connection')) {
                                return true;
                            }
                            if (text.includes('pending') || text.includes('invitation sent') || text.includes('request sent')) {
                                return true;
                            }
                            return false;
                        });
                        
                        if (hasPending) {
                            return { status: "Pending" };
                        }
                        
                        // 3. Third check: Scan for explicit connection degree badges in the top card
                        const allSpans = Array.from(topCard.querySelectorAll('span, div, button, a'));
                        let degree = null;
                        for (const el of allSpans) {
                            if (!el.offsetHeight && !el.offsetWidth) continue;
                            const text = el.textContent.trim();
                            if (/\b1st\b/i.test(text)) {
                                if (text.length < 30 && !text.toLowerCase().includes("class") && !text.toLowerCase().includes("year") && !text.toLowerCase().includes("anniversary")) {
                                    degree = "1st";
                                    break;
                                }
                            }
                            if (/\b(2nd|3rd)\b/i.test(text)) {
                                if (text.length < 30 && !text.toLowerCase().includes("class") && !text.toLowerCase().includes("year") && !text.toLowerCase().includes("anniversary")) {
                                    degree = "other";
                                    break;
                                }
                            }
                        }
                        
                        if (degree === "1st") {
                            return { status: "Connected" };
                        }
                        
                        // 4. Fourth check: If degree is not other, verify if there's a Messaging thread link or valid Message button
                        if (degree !== "other") {
                            for (const el of actions) {
                                if (!el.offsetHeight && !el.offsetWidth) continue;
                                const text = el.textContent.trim().toLowerCase();
                                const label = (el.getAttribute('aria-label') || '').toLowerCase();
                                const href = el.getAttribute('href') || '';
                                
                                if (href.includes('/messaging/thread/')) {
                                    return { status: "Connected" };
                                }
                                
                                if (text === 'message' || label === 'message' || label.startsWith('message ') || text.startsWith('message ')) {
                                    if (!text.includes('inmail') && !label.includes('inmail') && !label.includes('premium')) {
                                        return { status: "Connected" };
                                    }
                                }
                            }
                        }
                        
                        return { status: "Not Started" };
                    }
                """)
                
                detected_status = status_result.get("status", "Not Started")
                acc_state.add_log(f"Profile connection status detected: '{detected_status}'", "info")
                
                is_first_degree = (detected_status == "Connected")
                
                if is_first_degree:
                    contact["status"] = "Connected"
                    acc_state.add_log(f"Already connected with {contact.get('name', 'this user')} (1st degree). Marked as Connected.", "success")
                    target_username = profile_url.split("/in/")[-1].split("/")[0].split('?')[0].rstrip('/')
                    email, phone = None, None
                    connection_date = None
                    if target_username:
                        try:
                            email, phone, connection_date = scrape_contact_info(page, target_username, account_id)
                            contact["email"] = email if email else "Not Shared"
                            contact["phone"] = phone if phone else "Not Shared"
                        except Exception as enrichment_err:
                            acc_state.add_log(f"Enrichment error for already connected user: {str(enrichment_err)}", "warning")
                    
                    if connection_date:
                        # If the scraped connection date is today's date, use today's current precise time instead of 00:00:00
                        scraped_date = connection_date.split(" ")[0]
                        today_date = datetime.now().strftime("%Y-%m-%d")
                        if scraped_date == today_date:
                            contact["date_accepted"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            contact["date_accepted"] = connection_date
                    else:
                        contact["date_accepted"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                    db_data_fresh = load_db(account_id)
                    for d in db_data_fresh:
                        if d["profile_url"] == profile_url:
                            d["status"] = "Connected"
                            d["date_accepted"] = contact["date_accepted"]
                            d["email"] = contact["email"]
                            d["phone"] = contact["phone"]
                    save_db(db_data_fresh, account_id)
                    continue
                
                if detected_status == "Pending":
                    contact["status"] = "Pending"
                    acc_state.add_log(f"Request is already pending for {contact.get('name', 'this user')}.", "info")
                    db_data_fresh = load_db(account_id)
                    for d in db_data_fresh:
                        if d["profile_url"] == profile_url:
                            d["status"] = "Pending"
                    save_db(db_data_fresh, account_id)
                    continue

                clicked_connect = False
                state.add_log("Primary strategy: Searching for direct 'Connect' button on the profile header...", "info")
                connect_button = None
                direct_connect_selectors = [
                    f"{HEADER_ANCHOR}//button[contains(., 'Connect')]",
                    f"{HEADER_ANCHOR}//*[text()='Connect']",
                    "main [class*='top-card'] button:has-text('Connect')"
                ]
                try:
                    page.locator(", ".join([s for s in direct_connect_selectors if not s.startswith("xpath=")])).first.wait_for(state="visible", timeout=2000)
                except:
                    pass

                for selector in direct_connect_selectors:
                    try:
                        btn = page.locator(selector).first
                        if btn.is_visible() and btn.is_enabled():
                            connect_button = btn
                            break
                    except:
                        pass
                        
                if connect_button:
                    acc_state.add_log("Found direct 'Connect' button on header. Clicking...", "info")
                    connect_button.click(force=True)
                    clicked_connect = True
                else:
                    acc_state.add_log("Direct 'Connect' button not visible or disabled on header.", "info")
                    
                if not clicked_connect:
                    acc_state.add_log("Fallback: Looking for 'More' or '...' dropdown button...", "info")
                    more_button = None

                    # --- STRATEGY 1: Try standard CSS/aria-label selectors ---
                    more_selectors = [
                        # Strict XPath selectors inside the profile's top card
                        f"{HEADER_ANCHOR}//button[@aria-label='More actions']",
                        f"{HEADER_ANCHOR}//button[@aria-label='See more actions']",
                        f"{HEADER_ANCHOR}//button[contains(@aria-label, 'More')]",
                        f"{HEADER_ANCHOR}//button[contains(@aria-label, 'more')]",
                        f"{HEADER_ANCHOR}//button[contains(., 'More')]",
                        f"{HEADER_ANCHOR}//button[contains(., 'more')]",
                        
                        # Strict CSS selectors inside the profile top card
                        "main [class*='top-card'] button[aria-label='More actions']",
                        "main [class*='top-card'] button[aria-label='See more actions']",
                        "main [class*='top-card'] button[aria-label*='More']",
                        "main [class*='top-card'] button[aria-label*='more']",
                        ".pvs-profile-actions button:has-text('More')",
                        "main [class*='top-card'] button:has-text('More')",
                        "main [class*='top-card'] .artdeco-button--muted.artdeco-button--icon",
                    ]
                    css_more = [s for s in more_selectors if not s.startswith("xpath=")]
                    try:
                        page.locator(", ".join(css_more)).first.wait_for(state="visible", timeout=3000)
                    except:
                        pass
                    for selector in more_selectors:
                        try:
                            btn = page.locator(selector).first
                            if btn.is_visible() and btn.is_enabled():
                                more_button = btn
                                acc_state.add_log(f"Found More/... button via: {selector}", "info")
                                break
                        except:
                            pass

                    # --- STRATEGY 2: JS smart scan — finds overflow button regardless of text/icon ---
                    if not more_button:
                        try:
                            acc_state.add_log("CSS selectors missed — using JS smart scan for More/... button...", "info")
                            js_clicked = page.evaluate("""
                                () => {
                                    // Get buttons strictly inside the profile card to prevent collisions
                                    const topCard = document.querySelector('main [class*="top-card"], main section');
                                    const allBtns = topCard ? Array.from(topCard.querySelectorAll('button')) : Array.from(document.querySelectorAll('main button'));
                                    
                                    // Known action button labels to EXCLUDE
                                    const excludeWords = ['message', 'follow', 'connect', 'endorse', 'hire', 'save'];
                                    
                                    for (const btn of allBtns) {
                                        const label = (
                                            btn.getAttribute('aria-label') || 
                                            btn.innerText || 
                                            btn.textContent || ''
                                        ).toLowerCase().trim();
                                        
                                        // Match: button with 'more' in label OR button with no meaningful text (icon-only = ...)
                                        const isMore = label.includes('more');
                                        const isIconOnly = label.length === 0 || label === '...' || label === '•••';
                                        const isExcluded = excludeWords.some(w => label.includes(w));
                                        
                                        if ((isMore || isIconOnly) && !isExcluded) {
                                            // Must be visible
                                            const rect = btn.getBoundingClientRect();
                                            if (rect.width > 0 && rect.height > 0) {
                                                btn.click();
                                                return label || 'icon-only button';
                                            }
                                        }
                                    }
                                    return null;
                                }
                            """)
                            if js_clicked:
                                acc_state.add_log(f"JS found and clicked More/... button (label: '{js_clicked}')", "info")
                                time.sleep(random.uniform(2.0, 3.0))
                                more_button = True  # Signal: dropdown should now be open
                            else:
                                acc_state.add_log("JS scan found no More/... button on this profile.", "warning")
                        except Exception as e:
                            acc_state.add_log(f"JS More button scan error: {e}", "warning")

                    if more_button:
                        if more_button is not True:
                            more_button.click(force=True)
                            acc_state.add_log("Clicked More/... button. Waiting for dropdown...", "info")
                            time.sleep(random.uniform(2.0, 3.0))

                        dropdown_connect = None
                        # Broader set of selectors for Connect inside LinkedIn's More dropdown
                        dropdown_connect_selectors = [
                            # CSS exact text matches (100% safe from 'Remove connection')
                            "[role='menuitem'] span:text-is('Connect')",
                            "[role='menuitem'] button:text-is('Connect')",
                            "[role='menuitem']:text-is('Connect')",
                            # XPath exact match or exclusions to prevent false positive matching of 'Remove connection'
                            "xpath=//*[@role='menuitem'][normalize-space(.)='Connect']",
                            "xpath=//*[@role='menuitem']//*[normalize-space(.)='Connect']",
                            "xpath=//*[@role='menuitem'][contains(normalize-space(.), 'Connect') and not(contains(normalize-space(.), 'Remove')) and not(contains(normalize-space(.), 'connection'))]",
                            "xpath=//*[contains(@class,'artdeco-dropdown')]//*[normalize-space(text())='Connect']",
                        ]
                        
                        # Wait up to 3s for dropdown Connect to appear
                        css_dropdown = [s for s in dropdown_connect_selectors if not s.startswith("xpath=")]
                        try:
                            page.locator(", ".join(css_dropdown)).first.wait_for(state="visible", timeout=3000)
                        except:
                            pass

                        for selector in dropdown_connect_selectors:
                            try:
                                btn = page.locator(selector).first
                                if btn.is_visible():
                                    dropdown_connect = btn
                                    acc_state.add_log(f"Found 'Connect' in dropdown via: {selector}", "info")
                                    break
                            except:
                                pass
                        
                        # Last resort: find via JS evaluation inside the dropdown
                        if not dropdown_connect:
                            try:
                                acc_state.add_log("Trying JS-based Connect search inside dropdown...", "info")
                                js_clicked = page.evaluate("""
                                    () => {
                                        const items = document.querySelectorAll('[role="menuitem"], .artdeco-dropdown__item');
                                        for (const item of items) {
                                            if (item.innerText && item.innerText.trim() === 'Connect') {
                                                item.click();
                                                return true;
                                            }
                                        }
                                        return false;
                                    }
                                """)
                                if js_clicked:
                                    acc_state.add_log("JS-based click on 'Connect' in dropdown succeeded.", "success")
                                    clicked_connect = True
                            except Exception as js_err:
                                acc_state.add_log(f"JS dropdown click failed: {js_err}", "warning")
                                
                        if dropdown_connect and not clicked_connect:
                            acc_state.add_log("Clicking 'Connect' in the 'More' dropdown menu...", "info")
                            dropdown_connect.click(force=True)
                            clicked_connect = True
                        elif not clicked_connect:
                            acc_state.add_log("Could not find 'Connect' in the 'More' dropdown. Taking screenshot for debug...", "warning")
                            try:
                                screenshot_dir = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c"
                                os.makedirs(screenshot_dir, exist_ok=True)
                                page.screenshot(path=os.path.join(screenshot_dir, "debug_more_dropdown.png"))
                            except:
                                pass
                            try:
                                page.keyboard.press("Escape")
                                time.sleep(1.0)
                            except:
                                pass
                    else:
                        acc_state.add_log("Could not find 'More' button on this profile.", "warning")
                                
                if not clicked_connect:
                    acc_state.add_log(f"Skipping {contact.get('name', 'Contact')}: Connect action not available. Capturing debug screenshot...", "warning")
                    try:
                        screenshot_dir = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c"
                        os.makedirs(screenshot_dir, exist_ok=True)
                        page.screenshot(path=os.path.join(screenshot_dir, "debug_connect_missing.png"))
                    except:
                        pass
                    contact["status"] = "Failed"
                    contact["logs"] = "Connect button not found or disabled"
                    db_data_fresh = load_db(account_id)
                    for d in db_data_fresh:
                        if d["profile_url"] == profile_url:
                            d["status"] = "Failed"
                            d["logs"] = "Connect button not found or disabled"
                    save_db(db_data_fresh, account_id)
                    continue

                # Modal handling
                modal = page.locator(".artdeco-modal").first
                modal_appeared = False
                try:
                    acc_state.add_log("Waiting dynamically for connection modal to load...", "info")
                    modal.wait_for(state="visible", timeout=5000)
                    modal_appeared = True
                    acc_state.add_log("LinkedIn modal detected.", "info")
                except:
                    acc_state.add_log("No modal appeared within 5 seconds. Checking direct-send success...", "info")
                
                if modal_appeared and modal.is_visible() and ("How do you know" in (modal.text_content() or "")):
                    acc_state.add_log("LinkedIn asked 'How do you know this person?'. Selecting professional relationship...", "info")
                    know_options = [
                        "button:has-text('Colleague')", "label:has-text('Colleague')",
                        "button:has-text('Classmate')", "label:has-text('Classmate')",
                        "button:has-text('Other')", "label:has-text('Other')"
                    ]
                    clicked_option = False
                    for opt_selector in know_options:
                        opt = modal.locator(opt_selector).first
                        if opt.is_visible():
                            opt.click(force=True)
                            clicked_option = True
                            break
                    time.sleep(1.5)
                    sub_connect = modal.locator("button:has-text('Connect'), button:has-text('Next'), button:has-text('Send')").first
                    if sub_connect.is_visible() and sub_connect.is_enabled():
                        acc_state.add_log("Clicking Next/Connect inside relationship modal...", "info")
                        sub_connect.click(force=True)
                        time.sleep(2.5)

                modal = page.locator(".artdeco-modal").first
                if modal_appeared:
                    time.sleep(1.5)
                
                if not modal.is_visible():
                    acc_state.add_log("No modal is visible. The connection request was successfully sent directly!", "success")
                else:
                    email_input = modal.locator("input[type='email'], input[name='email'], #email").first
                    if email_input.is_visible():
                        acc_state.add_log("LinkedIn is requiring email address verification to connect. Skipping this contact.", "warning")
                        close_btn = modal.locator("button[aria-label*='Dismiss'], button[aria-label*='Close'], button:has-text('Close')").first
                        if close_btn.is_visible():
                            close_btn.click(force=True)
                        else:
                            page.keyboard.press("Escape")
                        time.sleep(1.5)
                        raise Exception("LinkedIn email verification required")
                        
                    add_note_btn = modal.locator("button:has-text('Add a note'), button[aria-label*='Add a note']").first
                    note_sent_successfully = False
                    
                    if send_with_note and add_note_btn.is_visible() and add_note_btn.is_enabled():
                        try:
                            acc_state.add_log("Clicking 'Add a note'...", "info")
                            add_note_btn.click(force=True)
                            time.sleep(1.5)
                            textarea = modal.locator("textarea, #custom-message").first
                            if textarea.is_visible():
                                note_text = resolve_template(note_template, contact)
                                if len(note_text) > 300:
                                    note_text = note_text[:297] + "..."
                                acc_state.add_log(f"Typing personalized note ({len(note_text)} chars)...", "info")
                                textarea.focus()
                                for char in note_text:
                                    page.keyboard.write(char)
                                    time.sleep(random.uniform(0.01, 0.05))
                                time.sleep(1.5)
                                send_btn = modal.locator("button:has-text('Send'), button[aria-label*='Send now']").first
                                if send_btn.is_visible() and send_btn.is_enabled():
                                    send_btn.click(force=True)
                                    acc_state.add_log("Personalized connection request sent!", "success")
                                    note_sent_successfully = True
                                else:
                                    raise Exception("Send button disabled/not found")
                        except Exception as note_err:
                            acc_state.add_log(f"Note-sending failed: {str(note_err)}. Trying fallback to Send without a note...", "warning")
                            try:
                                cancel_btn = modal.locator("button:has-text('Cancel'), button:has-text('Back')").first
                                if cancel_btn.is_visible():
                                    cancel_btn.click(force=True)
                                    time.sleep(1.5)
                            except:
                                pass
                                
                    if not note_sent_successfully:
                        send_without_note_btn = modal.locator("button:has-text('Send without a note'), button[aria-label*='Send without a note']").first
                        if send_without_note_btn.is_visible() and send_without_note_btn.is_enabled():
                            send_without_note_btn.click(force=True)
                            acc_state.add_log("Connection request sent (without note)!", "success")
                        else:
                            send_general = modal.locator("button:has-text('Send'), button[aria-label*='Send now'], button:has-text('Connect')").first
                            if send_general.is_visible() and send_general.is_enabled():
                                send_general.click(force=True)
                                acc_state.add_log("Connection request sent!", "success")
                            else:
                                raise Exception("Send buttons not found or disabled in modal")

                # Success
                sent_today_count += 1
                sent_week_count += 1
                contact["status"] = "Pending"
                contact["date_sent"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                db_data_fresh = load_db(account_id)
                for d in db_data_fresh:
                    if d["profile_url"] == profile_url:
                        d["status"] = "Pending"
                        d["date_sent"] = contact["date_sent"]
                save_db(db_data_fresh, account_id)
                
                if idx < total_to_process - 1:
                    sleep_time = random.randint(delay_min, delay_max)
                    acc_state.add_log(f"Sleeping for {sleep_time} seconds to simulate human activity...", "info")
                    for s in range(sleep_time):
                        if acc_state.stop_requested:
                            break
                        time.sleep(1)
                        
            except Exception as ex:
                acc_state.add_log(f"Exception during request for {contact.get('name', 'Contact')}: {str(ex)}", "error")
                is_browser_closed = False
                try:
                    if page.is_closed():
                        is_browser_closed = True
                except:
                    is_browser_closed = True
                    
                if is_browser_closed:
                    acc_state.add_log("Browser window was closed or crashed. Halting automation loop.", "warning")
                    break
                    
                contact["status"] = "Failed"
                contact["logs"] = str(ex)
                db_data_fresh = load_db(account_id)
                for d in db_data_fresh:
                    if d["profile_url"] == profile_url:
                        d["status"] = "Failed"
                        d["logs"] = str(ex)
                save_db(db_data_fresh, account_id)
                
        acc_state.add_log(f"Automation execution run finished. Requests sent during this run: {sent_today_count}", "success")
        
    except Exception as e:
        acc_state.add_log(f"Critical error in automation loop: {str(e)}", "error")
        update_account_status_in_registry(account_id, status="Error", current_action="Automation crashed")
    finally:
        acc_state.stop_running()
        acc_state.update_status(action="Idle", progress=100)
        update_account_status_in_registry(account_id, status="Idle", current_action="Idle", progress_percent=0)
        if context:
            try: context.close()
            except: pass
        if playwright:
            try: playwright.stop()
            except: pass

# Thread-safe sequential execution queue runner
class SequentialQueueRunner:
    def __init__(self):
        self.queue = []
        self._lock = threading.RLock()
        self.current_thread = None
        self.current_account_id = None
        
    def add_to_queue(self, task_type, account_id, task_func):
        acc_state = get_account_state(account_id)
        with self._lock:
            # Check if this account is already in the queue or running
            if any(item['account_id'] == account_id for item in self.queue) or self.current_account_id == account_id:
                acc_state.add_log("Account is already in the execution queue or currently running.", "warning")
                return False
            
            self.queue.append({
                "task_type": task_type,
                "account_id": account_id,
                "task_func": task_func
            })
            acc_state.add_log("Task added to sequential execution queue.", "info")
            update_account_status_in_registry(account_id, status="Queued", current_action="Waiting in queue...", progress_percent=0)
            
            if self.current_thread is None or not self.current_thread.is_alive():
                self._start_next()
            return True
            
    def _start_next(self):
        with self._lock:
            if not self.queue:
                self.current_thread = None
                self.current_account_id = None
                return
            
            next_task = self.queue.pop(0)
            self.current_account_id = next_task["account_id"]
            self.current_thread = threading.Thread(
                target=self._run_task,
                args=(next_task,),
                daemon=True
            )
            self.current_thread.start()
            
    def _run_task(self, task):
        account_id = task["account_id"]
        task_func = task["task_func"]
        acc_state = get_account_state(account_id)
        
        acc_state.add_log(f"Starting execution from sequential queue for account '{account_id}'...", "info")
        acc_state.start_running()
        try:
            task_func()
        except Exception as e:
            acc_state.add_log(f"Queue task failed: {str(e)}", "error")
        finally:
            acc_state.stop_running()
            acc_state.add_log(f"Finished execution from queue for account '{account_id}'.", "info")
            time.sleep(random.uniform(5, 10))
            self._start_next()

    def stop_account(self, account_id):
        acc_state = get_account_state(account_id)
        acc_state.stop_requested = True
        
        with self._lock:
            # Remove from queue if it was waiting
            self.queue = [item for item in self.queue if item["account_id"] != account_id]
            acc_state.add_log("Removed from sequential queue (if was queued).", "warning")
            if self.current_account_id == account_id:
                acc_state.add_log("Stop requested for currently running worker.", "warning")

queue_runner = SequentialQueueRunner()

# Dynamic background wrappers targeting the sequential queue
def run_automation_worker(note_template=None, send_with_note=False, delay_min=30, delay_max=70, daily_limit=25, weekly_limit=150, start_index=None, end_index=None, account_id="default"):
    config = {
        "note_template": note_template,
        "send_with_note": send_with_note,
        "delay_min": delay_min,
        "delay_max": delay_max,
        "daily_limit": daily_limit,
        "weekly_limit": weekly_limit,
        "start_index": start_index,
        "end_index": end_index
    }
    return queue_runner.add_to_queue("automation", account_id, lambda: run_automation_worker_sync(account_id, config))

def sync_acceptance_task(account_id="default"):
    return queue_runner.add_to_queue("sync", account_id, lambda: sync_acceptance_task_sync(account_id))

def background_scheduler_loop():
    """
    Background scheduler loop that runs continuously, checking for scheduled runs.
    """
    time.sleep(10)  # Wait for startup to settle
    while True:
        try:
            now = datetime.now()
            current_time_str = now.strftime("%H:%M")
            current_day = now.weekday()  # Monday is 0, Sunday is 6
            today_str = now.strftime("%Y-%m-%d")

            accounts = load_accounts_registry()
            dirty = False
            for acc in accounts:
                acc_id = acc.get("id")
                acc_config = acc.get("config", {})
                sched = acc_config.get("schedule")
                
                if sched and sched.get("enabled", False):
                    time_sched = sched.get("time", "10:00").strip()
                    days = sched.get("days")
                    if not days: # If None or empty list []
                        days = [0, 1, 2, 3, 4, 5, 6]
                    last_run = sched.get("last_run")

                    if current_time_str == time_sched and (current_day in days or str(current_day) in days):
                        if last_run != today_str:
                            acc_state = get_account_state(acc_id)
                            # Verify if already running or queued to prevent duplicate logs
                            if not acc_state.is_running:
                                acc_state.add_log(f"[SCHEDULER] Triggering scheduled automation run for '{acc.get('name')}'...", "info")
                                
                                # Fetch config limits and trigger connection request sending
                                run_automation_worker(
                                    note_template=acc_config.get("note_template"),
                                    send_with_note=acc_config.get("send_with_note", False),
                                    delay_min=acc_config.get("delay_min", 30),
                                    delay_max=acc_config.get("delay_max", 70),
                                    daily_limit=acc_config.get("daily_limit", 25),
                                    weekly_limit=acc_config.get("weekly_limit", 150),
                                    start_index=acc_config.get("start_index"),
                                    end_index=acc_config.get("end_index"),
                                    account_id=acc_id
                                )
                                
                                # Mark as run today
                                sched["last_run"] = today_str
                                dirty = True
            if dirty:
                save_accounts_registry(accounts)
        except Exception as e:
            # Prevent thread crash from taking down scheduler
            pass
        time.sleep(30) # Check every 30 seconds

threading.Thread(target=background_scheduler_loop, daemon=True).start()

