import os

# Dynamic Writable Paths Resolver
def resolve_base_paths():
    # Try writing to /data to verify mount permissions (Linux/Render only)
    data_writable = False
    if os.name != 'nt':
        try:
            os.makedirs("/data", exist_ok=True)
            test_file = "/data/.write_test"
            with open(test_file, 'w') as f:
                f.write("OK")
            os.remove(test_file)
            data_writable = True
        except Exception:
            data_writable = False
    else:
        # On Windows, check if C:\data exists and is writable
        if os.path.exists("C:\\data"):
            data_writable = True
        else:
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
_cached_accounts = []

def load_accounts_registry():
    global _cached_accounts
    
    import time, os
    
    # If the file doesn't exist, we can safely initialize it
    if not os.path.exists(ACCOUNTS_REGISTRY_PATH):
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
            tmp_path = ACCOUNTS_REGISTRY_PATH + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump([default_acc], f, indent=4)
            os.replace(tmp_path, ACCOUNTS_REGISTRY_PATH)
            _cached_accounts = [default_acc]
        except Exception:
            pass
        return _cached_accounts or [default_acc]

    # File exists, try reading it with retries
    for _ in range(10):
        try:
            with open(ACCOUNTS_REGISTRY_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    _cached_accounts = data
                    return data
        except Exception:
            time.sleep(0.5)
            
    # If we get here, file reading failed 10 times but the file exists!
    # DO NOT OVERWRITE. Return the cache if we have it, else raise error.
    if _cached_accounts:
        return _cached_accounts
        
    print("[ERROR] Failed to read accounts registry, but it exists. Returning empty list temporarily to avoid overwrite.")
    return []

def save_accounts_registry(accounts):
    try:
        tmp_path = ACCOUNTS_REGISTRY_PATH + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=4)
        os.replace(tmp_path, ACCOUNTS_REGISTRY_PATH)
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
def get_db_path(account_id, db_type="prospects"):
    return os.path.join(BASE_ACCOUNTS_DB_DIR, f"db_{account_id}_{db_type}.json")

_cached_dbs = {}

def load_db(account_id="default", db_type="prospects"):
    global _cached_dbs
    cache_key = f"{account_id}_{db_type}"
    
    # Migration logic: rename old db to prospects
    old_db_path = os.path.join(BASE_ACCOUNTS_DB_DIR, f"db_{account_id}.json")
    prospects_db_path = get_db_path(account_id, "prospects")
    if os.path.exists(old_db_path) and not os.path.exists(prospects_db_path):
        try:
            os.rename(old_db_path, prospects_db_path)
        except:
            pass

    db_path = get_db_path(account_id, db_type)
        
    import time
    for _ in range(10):
        try:
            with open(db_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    _cached_dbs[cache_key] = data
                    return data
        except Exception:
            time.sleep(0.2)
            
    # If reading failed 10 times but we have a cache, use it
    if cache_key in _cached_dbs and _cached_dbs[cache_key]:
        return _cached_dbs[cache_key]
        
    # If no cache and file is unreadable, create default empty DB
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        save_db([], account_id, db_type)
        _cached_dbs[cache_key] = []
    except Exception:
        pass
        
    acc_state = get_account_state(account_id)
    acc_state.add_log(f"Error loading {db_type} database after retries, using cache", "error")
    return _cached_dbs.get(cache_key, [])

def save_db(data, account_id="default", db_type="prospects"):
    db_path = get_db_path(account_id, db_type)
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        tmp_path = db_path + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, db_path)
        
        # update cache
        cache_key = f"{account_id}_{db_type}"
        _cached_dbs[cache_key] = data
    except Exception as e:
        acc_state = get_account_state(account_id)
        acc_state.add_log(f"Error saving {db_type} database: {str(e)}", "error")

import re
import random

SPINTAX_TEMPLATES = [
    "{Greetings|Hello there|Hi} {FirstName}, {thanks|thank you|many thanks} for {accepting my request|connecting with me|joining my network}!\n\n{Your background is truly impressive and I wanted to connect.|I noticed your experience and thought it would be great to connect.|I am actively growing my network with driven professionals like you.}\n\n{I am always eager to share insights with peers.|I'd love to follow your work and see your future posts.|If you ever want to bounce ideas around, feel free to message me.}\n\n{Wishing you a highly productive week!|Hope everything is going well!|Looking forward to seeing your updates!}\n\n{Warmly,|Best regards,|Thanks again,}\n{SenderName}",
    "{Hey|Hi|Hello} {FirstName}, {I really appreciate|thanks so much for|thank you for} {the connection|connecting|adding me to your connections}!\n\n{It is always great to connect with fellow industry professionals.|I came across your profile and knew I had to reach out.|I love networking with people who share similar professional interests.}\n\n{I would be thrilled to learn more about your current projects.|I am always open to discussing new ideas and industry shifts.|My inbox is always open if you want to talk shop.}\n\n{Hope you crush your goals this week!|Wishing you nothing but the best in your career!|Hope you have a fantastic month ahead!}\n\n{Take care,|Cheers,|Best,}\n{SenderName}",
    "{Hi|Hello|Hey there} {FirstName}, {thank you|thanks a ton|I appreciate you} for {accepting my invite|connecting here on LinkedIn|the connection approval}!\n\n{I was browsing your profile and really liked your trajectory.|Your professional journey caught my attention.|I am building a network of ambitious professionals and wanted to include you.}\n\n{I am always happy to explore ways we might collaborate in the future.|I'd love to hear more about what you specialize in.|If you ever need a second opinion on an industry topic, let me know.}\n\n{Keep up the great work!|Wishing you continued success!|Hope to see you around the LinkedIn feed!}\n\n{Best wishes,|Regards,|Sincerely,}\n{SenderName}",
    "{Hi|Hello|Hey} {FirstName}, {thank you|thanks so much|I appreciate you} for {connecting with me|accepting my connection request|adding me to your network}!\n\n{I was looking at your profile and saw we are in similar industries.|Your profile caught my eye and I wanted to reach out.|I am currently expanding my network with professionals like yourself.}\n\n{I would love to learn more about what you do.|I am always open to exploring mutual synergies.|If you ever want to chat about industry trends, my inbox is open.}\n\n{Hope you have a fantastic week ahead!|Looking forward to following your journey here on LinkedIn.|Wishing you great success in your upcoming projects!}\n\n{Best,|Cheers,|Regards,}\n{SenderName}",
    "{Greetings|Hi|Hello} {FirstName}, {thank you|thanks|I'm grateful} for {the connection|accepting my request|connecting}!\n\n{Your career path is fascinating and I wanted to reach out.|I love connecting with seasoned professionals in our space.|I noticed your recent career moves and wanted to introduce myself.}\n\n{I am always looking to exchange ideas with smart people.|I would love to stay in the loop with your professional journey.|If you ever want to discuss new trends, feel free to drop me a line.}\n\n{Have an amazing week!|Wishing you a spectacular month!|Hope everything is going well on your end!}\n\n{Best,|Warmly,|Regards,}\n{SenderName}",
    "{Hello|Hi|Hey there} {FirstName}, {thanks a lot|thank you|thanks} for {adding me|connecting with me|accepting my invite}!\n\n{I enjoy surrounding myself with talented professionals on here.|Your experience resonated with me and I wanted to connect.|I am working on growing my professional circle with people like you.}\n\n{I would be glad to learn more about your day-to-day work.|I am always down to discuss strategies and ideas.|My DMs are open if you ever want to chat about the industry.}\n\n{Wishing you a stellar week!|Hope you achieve all your goals this week!|Looking forward to your future updates!}\n\n{Thanks again,|Cheers,|Best,}\n{SenderName}",
    "{Greetings|Hi|Hello} {FirstName}, {I appreciate|thanks so much for|thank you for} {the connect|accepting my LinkedIn request|adding me to your network}!\n\n{I was impressed by your profile and thought we should connect.|Networking with driven individuals is always a priority for me.|I saw we share some mutual professional interests.}\n\n{I'd love to find out more about your current focus.|I am always eager to share perspectives with peers.|If you ever need a sounding board for ideas, I'm just a message away.}\n\n{Hope your week is off to a great start!|Wishing you massive success!|Looking forward to staying connected!}\n\n{Best regards,|Take care,|Sincerely,}\n{SenderName}",
    "{Hey|Hello|Hi} {FirstName}, {thank you|thanks|many thanks} for {the new connection|connecting|approving my request}!\n\n{I'm always looking to connect with influential voices in our field.|Your work history stood out to me as quite unique.|I'm building a strong network and felt you'd be a great addition.}\n\n{I'd be interested in learning what you are currently working on.|I am always open to networking and finding mutual ground.|Feel free to reach out if you ever want to talk shop.}\n\n{Have a productive week!|Wishing you the best in your endeavors!|Looking forward to staying in touch!}\n\n{Cheers,|Best,|Warm regards,}\n{SenderName}",
    "{Hi|Hey|Hello} {FirstName}, {thanks|thank you|thanks a ton} for {accepting my invite|connecting with me|joining my network}!\n\n{I admire professionals who are making an impact in our industry.|I came across your page and thought we should be connected.|I am passionate about connecting with forward-thinking people.}\n\n{I'd love to follow your insights and updates.|I am always thrilled to exchange thoughts on industry changes.|If you ever want to brainstorm, don't hesitate to reach out.}\n\n{Have a fantastic rest of the week!|Wishing you endless success!|Hope you're having a brilliant month!}\n\n{Regards,|Best,|Thanks,}\n{SenderName}",
    "{Greetings|Hello|Hi} {FirstName}, {thank you so much|thanks|I appreciate you} for {connecting|the connection|accepting my request}!\n\n{I strive to connect with experienced leaders like yourself.|Your profile reflects a lot of hard work and dedication.|I'm expanding my horizons by connecting with diverse professionals.}\n\n{I would love to understand more about your professional focus.|I am always open to discussing new opportunities or ideas.|If there is ever a way I can add value to your network, let me know.}\n\n{Wishing you a great week!|Hope you crush it this month!|Looking forward to your content!}\n\n{Warmly,|Best wishes,|Cheers,}\n{SenderName}",
    "{Hello|Hi|Hey} {FirstName}, {thanks|thank you|I'm thankful} for {the LinkedIn connection|connecting with me|adding me to your circle}!\n\n{I saw your background and thought it would be beneficial to connect.|Networking with people in similar fields is something I value highly.|I was captivated by your professional journey.}\n\n{I'd be curious to hear about your latest projects.|I am always open to sharing resources and knowledge.|If you ever want to connect on a quick call, my schedule is flexible.}\n\n{Have an excellent week!|Wishing you a highly successful year!|Hope everything is going smoothly for you!}\n\n{Best,|Sincerely,|Regards,}\n{SenderName}",
    "{Hi there|Hello|Hi} {FirstName}, {thanks so much|thank you|thanks} for {accepting my connection|connecting|joining my network on here}!\n\n{I love seeing what other professionals in our space are up to.|Your profile is very engaging and I wanted to introduce myself.|I am proactively connecting with people whose work I respect.}\n\n{I'd love to see the kind of content you share.|I am always eager to discuss industry innovations.|If you ever want to chat about market trends, just say the word.}\n\n{Hope you have a beautiful week!|Wishing you all the best!|Looking forward to connecting further!}\n\n{Cheers,|Take care,|Best,}\n{SenderName}",
    "{Hey there|Hello|Hi} {FirstName}, {thank you|thanks|I appreciate you} for {the connection approval|connecting with me|adding me as a connection}!\n\n{Your career progression is really inspiring to see.|I am building a network of high-achievers and wanted to reach out.|I noticed your profile and knew it would be great to connect.}\n\n{I would love to learn more about your business model.|I am always open to exploring ways to support one another.|If you ever need advice or want to share ideas, I'm available.}\n\n{Hope you have a wonderful time ahead!|Wishing you phenomenal growth!|Hope your week is going wonderfully!}\n\n{Warm regards,|Best,|Thanks again,}\n{SenderName}",
    "{Hey|Hi|Hello} {FirstName}, {thanks a lot|thank you|thanks} for {connecting|accepting my request|the new connection}!\n\n{I value connecting with people who have strong industry experience.|I came across your account and wanted to say hi.|I'm working on expanding my professional footprint with like-minded folks.}\n\n{I'd be interested in hearing about your biggest wins lately.|I am always open to networking for mutual benefit.|Feel free to shoot me a message if you ever want to talk business.}\n\n{Wishing you a fantastic week!|Hope you accomplish all your goals!|Looking forward to seeing you on my feed!}\n\n{Best,|Cheers,|Regards,}\n{SenderName}",
    "{Greetings|Hi|Hello} {FirstName}, {I really appreciate|thank you for|thanks for} {accepting my invite|connecting with me|the connection}!\n\n{I was drawn to your profile because of your impressive skillset.|Networking with ambitious professionals is a big focus of mine.|I saw we have some shared connections and thought I'd reach out.}\n\n{I would love to find out what you are focusing on right now.|I am always happy to discuss industry best practices.|If you ever want to exchange thoughts on the market, let me know.}\n\n{Hope you have an awesome week!|Wishing you a prosperous month!|Hope to interact with your posts soon!}\n\n{Sincerely,|Best wishes,|Take care,}\n{SenderName}"
]

def send_followup_message(page, message_text, acc_state, contact_name=""):
    """
    Attempts to send a message to the currently loaded profile.
    Returns True if sent successfully, False otherwise.
    """
    import time
    try:
        acc_state.add_log("Sending automated follow-up message...", "info")
        
        msg_btn = None
        
        # Close any currently open message overlay bubbles to prevent sending to the wrong person
        try:
            page.evaluate("""() => {
                const bubbles = document.querySelectorAll('.msg-overlay-conversation-bubble, aside.msg-overlay-container');
                bubbles.forEach(bubble => {
                    const closeBtns = bubble.querySelectorAll('button[aria-label^="Close"], button[aria-label^="Dismiss"], svg[data-test-icon*="close"]');
                    closeBtns.forEach(btn => {
                        const target = btn.tagName === 'BUTTON' ? btn : btn.closest('button');
                        if (target) target.click();
                    });
                });
            }""")
            time.sleep(1)
        except:
            pass
            
        acc_state.add_log("Sending automated follow-up message...", "info")
        
        js_find_btn = r"""() => {
            let root = document.querySelector('.pv-top-card, .ph5.pb5') || document.querySelector('main > section') || document;
            const elements = Array.from(root.querySelectorAll('button, a, [role="button"]'));
            
            // Priority 1: Primary buttons
            for (const el of elements) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
                    const text = (el.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    if (text === 'message' || text === 'send message' || aria.includes('message')) {
                        if (el.classList.contains('artdeco-button--primary') || el.classList.contains('pvs-profile-actions__action')) {
                            return el;
                        }
                    }
                }
            }
            
            // Priority 2: Any matching button
            for (const el of elements) {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
                    const text = (el.textContent || '').replace(/\s+/g, ' ').trim().toLowerCase();
                    const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                    if (text === 'message' || text === 'send message' || aria.includes('message')) {
                        return el;
                    }
                }
            }
            return null;
        }"""

        msg_btn = None
        for _ in range(3):
            handle = page.evaluate_handle(js_find_btn)
            msg_btn = handle.as_element()
            if msg_btn:
                break
            time.sleep(1)
            
        if not msg_btn:
            # Last resort fallback: try the More dropdown but force click to avoid interception
            more_btns = page.locator("button:has-text('More'), button[aria-label*='More actions']").all()
            for mb in more_btns:
                if mb.is_visible():
                    try:
                        mb.click(force=True)
                        time.sleep(1.5)
                        handle = page.evaluate_handle(js_find_btn)
                        msg_btn = handle.as_element()
                        if msg_btn:
                            break
                    except: pass

        if not msg_btn:
            acc_state.add_log("Message button not found or not visible on profile. Follow-up failed.", "warning")
            return False
            
        # Try to find the message box using broad robust selectors
        editor_selectors = [
            ".msg-overlay-conversation-bubble--is-active .msg-form__contenteditable",
            ".msg-overlay-conversation-bubble--is-active div[role='textbox']",
            "div[role='textbox'].msg-form__contenteditable",
            ".msg-form__contenteditable",
            "div[aria-label*='Write a message']",
            "div[aria-label*='Reply']",
            "div[role='textbox'][aria-label*='essage']",
            ".msg-form div[role='textbox']",
            "div.msg-form__msg-content-container[role='textbox']",
            ".msg-form__msg-content-container",
            "form.msg-form"
        ]
        
        # Click the button if no message box is currently visible
        message_box = None
        for sel in editor_selectors:
            if page.locator(sel).first.is_visible():
                message_box = page.locator(sel).first
                break
                
        if not message_box:
            try:
                msg_btn.evaluate("el => el.click()")
            except Exception:
                pass
            time.sleep(3)
            
            if not page.locator(editor_selectors[0]).first.is_visible():
                try:
                    msg_btn.click(force=True, timeout=2000)
                except Exception:
                    pass
                time.sleep(3)
                
        for sel in editor_selectors:
            if page.locator(sel).first.is_visible():
                message_box = page.locator(sel).first
                break
                
        if not message_box:
            acc_state.add_log("Message box failed to appear after clicking Message.", "warning")
            return False
        
        message_box.click()
        # Type the message like a human to avoid bot detection flags
        try:
            message_box.type(message_text, delay=random.uniform(30, 80))
        except:
            # Fallback if type fails
            message_box.fill(message_text)
            page.keyboard.press("Space")
            page.keyboard.press("Backspace")
            
        time.sleep(2)  # Delay before sending
        
        # Send button might not be inside a <form> tag anymore, find the closest container
        send_btn = message_box.locator("xpath=ancestor::*[contains(@class, 'msg-form')]").locator("button[type='submit'], .msg-form__send-button, button:has-text('Send')").first
            
        try:
            # Wait for the send button to be enabled (React takes a moment)
            for _ in range(5):
                try:
                    if send_btn.is_enabled():
                        break
                except:
                    pass
                time.sleep(1)
                
            enabled = False
            try: enabled = send_btn.is_enabled()
            except: pass
            
            if enabled:
                try:
                    send_btn.evaluate("el => el.click()")
                except:
                    send_btn.click(force=True)
                acc_state.add_log("Follow-up message sent successfully!", "success")
                time.sleep(2)
            else:
                # Force via JS form submission if React still holds it disabled
                message_box.evaluate("el => { let form = el.closest('.msg-form, form'); if(form) { let btn = form.querySelector('button[type=\"submit\"], .msg-form__send-button, button'); if(btn) { btn.removeAttribute('disabled'); btn.click(); } } }")
                acc_state.add_log("Follow-up message sent via JS trigger!", "success")
                time.sleep(2)
        except Exception:
            # If Playwright locator completely fails, attempt raw JS directly
            try:
                message_box.evaluate("el => { let form = el.closest('.msg-form, form'); if(form) { let btn = form.querySelector('button[type=\"submit\"], .msg-form__send-button'); if(btn) { btn.removeAttribute('disabled'); btn.click(); } } }")
                acc_state.add_log("Follow-up message sent via raw JS fallback!", "success")
                time.sleep(2)
            except Exception:
                acc_state.add_log("Send button not found after typing message.", "warning")
                return False
            
        # Close the message overlay to return to normal profile view
        try:
            close_btn = message_box.locator("xpath=ancestor::*[contains(@class, 'msg-overlay-conversation-bubble')]").locator("button[aria-label*='Close'], button[aria-label*='close'], button:has-text('Close')").first
            if close_btn.is_visible():
                close_btn.evaluate("el => el.click()")
            else:
                # Global fallback
                page.evaluate("document.querySelectorAll('.msg-overlay-conversation-bubble button[aria-label*=\"Close\"]').forEach(b => b.click())")
        except:
            page.evaluate("document.querySelectorAll('.msg-overlay-conversation-bubble button[aria-label*=\"Close\"]').forEach(b => b.click())")
            
        return True
    except Exception as e:
        acc_state.add_log(f"Error during follow-up message: {e}", "warning")
        return False

def resolve_template(template, contact, sender_name=""):
    """
    Replaces tags like {FirstName}, {LastName}, {Company} with values from the contact dictionary,
    and resolves spintax like {Greetings|Hello}.
    """
    if not template:
        return ""
    full_name = contact.get("name", "")
    first_name = contact.get("first_name", "")
    last_name = contact.get("last_name", "")
    
    if not first_name and full_name:
        parts = full_name.split()
        prefixes = {"dr", "dr.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "prof", "prof.", "er", "er.", "ca", "cma", "adv", "adv.", "cs"}
        while parts and parts[0].lower() in prefixes:
            parts.pop(0)
        first_name = parts[0] if parts else (full_name.split()[0] if full_name.split() else "")
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

    replacements = {
        "{FirstName}": first_name or full_name or "there",
        "{LastName}": last_name or "",
        "{FullName}": full_name or "there",
        "{Company}": contact.get("company", "") or "your company",
        "{Title}": contact.get("title", "") or "your role",
        "{SenderName}": sender_name
    }
    
    resolved = template
    for tag, value in replacements.items():
        resolved = resolved.replace(tag, value)
        
    # Process spintax: {a|b|c}
    import re
    def spin_match(match):
        options = match.group(1).split('|')
        import random
        return random.choice(options)
        
    # Support simple spintax using regex substitution
    resolved = re.sub(r'\{([^{}]+)\}', spin_match, resolved)
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
        
    base_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox"
    ]
    if not headed:
        base_args.append("--headless=new")

    # Removed forceful Chrome termination to prevent SQLite cookie database corruption!
    # If the user left a window open, Playwright will safely raise a Lock error instead of
    # wiping their session.

    try:
        context = pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=executable_path,
            headless=False,
            viewport={"width": 1280, "height": 800},
            proxy=pw_proxy,
            ignore_default_args=["--enable-automation"],
            args=base_args
        )
    except Exception as e:
        acc_state.add_log(f"Browser launch failed: {str(e)}. Attempting to unlock profile cache...", "warning")
        lock_path = os.path.join(user_data_dir, "SingletonLock")
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except:
                pass
        # Try launching again after unlocking the cache
        context = pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            executable_path=executable_path,
            headless=False,
            viewport={"width": 1280, "height": 800},
            proxy=pw_proxy,
            ignore_default_args=["--enable-automation"],
            args=base_args
        )
        
    context.set_default_timeout(20000)
    
    # Inject secure session cookie from file or environment
    li_at_val = os.environ.get("LI_AT_COOKIE")
    try:
        cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookie.txt")
        if os.path.exists(cookie_path):
            with open(cookie_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    li_at_val = content
    except Exception:
        pass

    if li_at_val:
        clean_cookie = li_at_val.strip().strip('"').strip("'")
        context.add_cookies([{
            "name": "li_at",
            "value": clean_cookie,
            "url": "https://www.linkedin.com",
            "secure": True,
            "httpOnly": True,
            "sameSite": "None"
        }])
        acc_state.add_log("Successfully injected secure LI_AT cookie! Bypassing login screen.", "success")
        
    return pw, context

def check_login_status(page):
    """
    Checks if user is logged into LinkedIn. If not, directs them to login.
    """
    try:
        # Use wait_until="domcontentloaded" with a generous timeout to resolve instantly on server response, 
        # avoiding freezes from assets or trackers that could block domcontentloaded.
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        
        # Wait up to 15 seconds for automatic sign-in redirect to '/feed' if we are on an intermediate page
        try:
            page.wait_for_url("**/feed*", timeout=15000)
        except Exception:
            pass
            
        time.sleep(2)
        if "login" in page.url or "signup" in page.url or page.locator("a:has-text('Sign in')").is_visible():
            try:
                public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
                page.screenshot(path=os.path.join(public_dir, "debug_login_status.png"))
            except Exception:
                pass
            print(f"[DEBUG] check_login_status returning False because URL or Sign In visible. URL: {page.url}")
            return False
        return True
    except Exception as e:
        print(f"[DEBUG] check_login_status threw exception: {str(e)}")
        import traceback
        traceback.print_exc()
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
                
        playwright, context = launch_browser(account_id, headed=True, proxy_config=proxy_cfg)
        page = context.new_page()
        
        # Navigate to feed to see if we're authenticated (using wait_until="domcontentloaded" for speed and reliability)
        page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=25000)
        
        # Wait up to 15 seconds for automatic sign-in redirect to '/feed' if we are on an intermediate page
        try:
            page.wait_for_url("**/feed*", timeout=15000)
        except Exception:
            pass
            
        time.sleep(2)
        
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
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
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
                page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                acc_state.add_log(f"Initial navigation warning: {str(e)}. Retrying...", "warning")
                page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)
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
    Utility to open LinkedIn in headed browser for user to log in manually.
    """
    acc_state = get_account_state(account_id)
    if not acc_state.start_running():
        acc_state.add_log("System is currently busy (another automation or browser task is active).", "warning")
        return
        
    def run():
        acc_state.update_status(action="Opening login window...")
        update_account_status_in_registry(account_id, status="Login Setup", current_action="Opening login browser...")
        playwright = None
        context = None
        try:
            # Fetch proxy if configured
            proxy_cfg = None
            accounts = load_accounts_registry()
            for acc in accounts:
                if acc.get("id") == account_id:
                    proxy_cfg = acc.get("proxy")
                    break
                    
            playwright, context = launch_browser(account_id, headed=True, proxy_config=proxy_cfg)
            page = context.new_page()
            acc_state.add_log("Opening LinkedIn login page. Please log in manually if needed...", "info")
            page.goto("https://www.linkedin.com/login")
            
            # Wait until user is on feed page or closes browser
            logged_in = False
            for _ in range(600): # Wait up to 10 minutes
                if acc_state.stop_requested:
                    break
                try:
                    # Detect login once and log success
                    if not logged_in and ("feed" in page.url or page.locator(".global-nav").is_visible()):
                        acc_state.add_log("Successfully detected LinkedIn login session! You can close this window now or keep it open.", "success")
                        acc_state.update_status(action="Login OK! Close window.")
                        update_account_status_in_registry(account_id, status="Login Setup", current_action="Login OK! Close window.")
                        logged_in = True
                    
                    if page.is_closed():
                        acc_state.add_log("Browser window was closed by the user.", "info")
                        break
                        
                    # Keep checking if the page is still open. 
                    _check = page.title() # title() actually communicates with the browser
                except Exception:
                    # Browser might have been closed by user
                    acc_state.add_log("Browser window was closed by the user.", "info")
                    break
                time.sleep(1)
                
            if not logged_in:
                acc_state.add_log("Login session setup complete or cancelled.", "info")
                
        except Exception as e:
            acc_state.add_log(f"Error during manual login setup: {str(e)}", "error")
        finally:
            acc_state.stop_running()
            acc_state.update_status(action="Idle")
            update_account_status_in_registry(account_id, status="Idle", current_action="Idle", progress_percent=0)
            if context:
                try: context.close() 
                except: pass
            if playwright:
                try: playwright.stop()
                except: pass

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
            
            # Human simulation: browse profile before clicking contact info
            acc_state.add_log("Simulating human behavior: browsing profile...", "info")
            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight/3)")
                time.sleep(random.uniform(1.5, 3.0))
                page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
                time.sleep(random.uniform(2.0, 3.5))
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(random.uniform(1.5, 2.5))
            except Exception as scroll_e:
                acc_state.add_log(f"Scroll simulation skipped: {str(scroll_e)}", "warning")
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
            return None, None, None

            
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
                
                if (!dialog) return null;
                
                let links = Array.from(dialog.querySelectorAll('a[href^="mailto:"]'));
                
                // If we found mailto links inside the dialog, try to match by username or return the first one
                if (links.length > 0) {
                    const byUsername = links.find(l => {
                        const addr = l.href.replace('mailto:', '').split('?')[0].trim();
                        const local = addr.split('@')[0].toLowerCase().replace(/[^a-z0-9]/g, '');
                        return usernameClean && (local.includes(usernameClean) || usernameClean.includes(local));
                    });
                    const bestLink = byUsername || links[0];
                    const addr = bestLink.href.replace('mailto:', '').split('?')[0].trim();
                    if (addr.includes('@')) return addr;
                }
                
                // Fallback: search DOM near "Email" text inside the dialog
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
                                if (addr && addr.includes('@')) return addr;
                            }
                            // Also check raw text nodes for email-like strings
                            const childTxts = Array.from(cur.childNodes).map(n => (n.textContent || '').trim());
                            for (const t of childTxts) {
                                const emailMatch = t.match(/([a-zA-Z0-9._-]+@[a-zA-Z0-9._-]+\.[a-zA-Z0-9_-]+)/);
                                if (emailMatch) return emailMatch[1];
                            }
                            cur = cur.parentElement;
                        }
                    }
                }
                
                return null;
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
        birthday = None
        try:
            connection_date_raw = page.evaluate(r"""() => {
                const dialog = document.querySelector('.pv-contact-info-modal') ||
                               document.querySelector('.artdeco-modal') ||
                               document.querySelector('dialog[open]') ||
                               document.querySelector('[data-testid="dialog"]') ||
                               document.querySelector('[role="dialog"].artdeco-modal') ||
                               document.querySelector('[role="dialog"]');
                if (!dialog) return null;
                
                const dateRegex = /([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4}|[A-Za-z]+\s+\d{4})/;
                const labelRegex = /^Connected(\s+(since|on))?$/i;
                
                const allEls = Array.from(dialog.querySelectorAll('*'));
                for (const el of allEls) {
                    const txt = (el.textContent || '').trim();
                    if (labelRegex.test(txt) && el.children.length === 0) {
                        let cur = el.parentElement;
                        for (let i = 0; i < 4; i++) {
                            if (!cur) break;
                            const childTxts = Array.from(cur.childNodes)
                                .map(node => (node.textContent || '').trim())
                                .filter(t => t && !labelRegex.test(t));
                            for (const t of childTxts) {
                                if (dateRegex.test(t)) {
                                    return t;
                                }
                            }
                            cur = cur.parentElement;
                        }
                    }
                }
                const dlgText = dialog.innerText || '';
                const lines = dlgText.split('\n').map(l => l.trim()).filter(l => l);
                for (let i = 0; i < lines.length; i++) {
                    if (labelRegex.test(lines[i]) && i + 1 < lines.length) {
                        const nxt = lines[i + 1];
                        if (dateRegex.test(nxt)) {
                            return nxt;
                        }
                    }
                    const inlineMatch = lines[i].match(new RegExp(`^Connected(?:\\s+(?:since|on))?\\s+([A-Za-z]+\\s+\\d{1,2},?\\s+\\d{4}|\\d{1,2}\\s+[A-Za-z]+\\s+\\d{4}|[A-Za-z]+\\s+\\d{4})`, 'i'));
                    if (inlineMatch) return inlineMatch[1].trim();
                }
                return null;
            }""")
            if connection_date_raw:
                acc_state.add_log(f"Extracted raw connection date: {connection_date_raw}", "info")
                # Clean prefix
                ds = re.sub(r'^Connected(\s+(since|on))?\s+', '', connection_date_raw.strip(), flags=re.IGNORECASE).strip()
                parsed_dt = None
                for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
                    try:
                        parsed_dt = datetime.strptime(ds, fmt)
                        break
                    except:
                        pass
                if not parsed_dt:
                    for fmt in ("%B %Y", "%b %Y", "%m/%d/%Y"):
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
            birthday_raw = page.evaluate(r"""() => {
                const dialog = document.querySelector('.pv-contact-info-modal') ||
                               document.querySelector('.artdeco-modal') ||
                               document.querySelector('dialog[open]') ||
                               document.querySelector('[data-testid="dialog"]') ||
                               document.querySelector('[role="dialog"].artdeco-modal') ||
                               document.querySelector('[role="dialog"]') ||
                               document.body;
                
                const allSections = Array.from(dialog.querySelectorAll('section'));
                for (const section of allSections) {
                    const header = section.querySelector('h3');
                    if (header && header.textContent.trim().toLowerCase().includes('birthday')) {
                        const span = section.querySelector('span');
                        if (span) {
                            return span.textContent.trim();
                        }
                        const div = section.querySelector('div');
                        if (div) {
                            return div.textContent.trim();
                        }
                    }
                }
                
                // Fallback: search text directly
                const dlgText = dialog.innerText || '';
                const lines = dlgText.split('\n').map(l => l.trim()).filter(l => l);
                for (let i = 0; i < lines.length; i++) {
                    if (/^(Birthday|Birth Date|DOB)$/i.test(lines[i]) && i + 1 < lines.length) {
                        return lines[i + 1];
                    }
                }
                
                return null;
            }""")
            if birthday_raw:
                birthday = birthday_raw
                acc_state.add_log(f"Extracted birthday: {birthday}", "info")
        except Exception as e:
            acc_state.add_log(f"JS birthday extraction failed: {str(e)}", "warning")
        try:
            page.evaluate("""() => {
                const dialogs = document.querySelectorAll('.pv-contact-info-modal, .artdeco-modal, dialog[open], [data-testid="dialog"], [role="dialog"]');
                dialogs.forEach(dialog => {
                    const closeBtns = dialog.querySelectorAll('button[aria-label^="Dismiss"], button[aria-label^="Close"]');
                    closeBtns.forEach(btn => btn.click());
                    
                    const svgBtns = dialog.querySelectorAll('svg[data-test-icon^="close"]');
                    svgBtns.forEach(svg => {
                        const btn = svg.closest('button');
                        if (btn) btn.click();
                    });
                });
            }""")
            time.sleep(0.5)
            page.keyboard.press("Escape")
            time.sleep(1.0)
        except:
            pass
    except Exception as ex:
        acc_state.add_log(f"Failed to scrape contact info overlay: {str(ex)}", "error")
    return email, phone, connection_date, birthday


def verify_profile_status(page, username, acc_state):
    import time
    import random
    try:
        profile_url = f"https://www.linkedin.com/in/{username}/"
        acc_state.add_log(f"Navigating to {profile_url} to verify status...", "info")
        page.goto(profile_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(random.uniform(3.0, 5.0))
        
        # Failsafe: Force open all 'More' dropdowns to reveal 'Remove connection' if they are 1st degree but badges are hidden
        try:
            page.evaluate("""() => {
                document.querySelectorAll('button').forEach(b => {
                    const t = (b.textContent || '').trim().toLowerCase();
                    const a = (b.getAttribute('aria-label') || '').toLowerCase();
                    if (t === 'more' || t === 'mehr' || t === 'अधिक' || a.includes('more actions')) {
                        b.click();
                    }
                });
            }""")
            time.sleep(1.0)
        except: pass
        
        status_result = page.evaluate(r"""
                  () => {
                      const mainEl = document.querySelector('main') || document.body;
                      const headerSection = mainEl.querySelector('section') || mainEl;
                      
                      const headerActions = Array.from(headerSection.querySelectorAll('button, a, [role="button"]'));
                      const allElements = Array.from(document.querySelectorAll('*'));
                      const allActions = Array.from(document.querySelectorAll('button, a, [role="button"]'));
                      const dropdownActions = Array.from(document.querySelectorAll('.artdeco-dropdown__content button, .artdeco-dropdown__content a, .artdeco-dropdown__content [role="button"]'));
                      
                      // Priority 1: Check for Pending / Sent anywhere
                      const hasPending = allActions.some(el => {
                          const text = (el.textContent || '').trim().toLowerCase();
                          const label = (el.getAttribute('aria-label') || '').toLowerCase();
                          return text === 'pending' || text === 'sent' || text === 'ausstehend' || text === 'लंबित' || label.includes('pending') || label.includes('sent connection') || text.includes('invitation sent') || text.includes('request sent');
                      });
                      if (hasPending) return { status: "Pending", reason: "Found Pending/Sent button" };
                      
                      // Priority 2: Bulletproof Remove Connection
                      const hasRemove = allElements.some(el => {
                          const txt = (el.textContent || '').trim().toLowerCase();
                          const aria = (el.getAttribute('aria-label') || '').toLowerCase();
                          return txt === 'remove connection' || aria === 'remove connection' || txt === 'verbindung entfernen';
                      });
                      if (hasRemove) return { status: "Connected", reason: "Found Remove Connection" };
                      
                      // Priority 3: 1st Degree Badge strictly in Header
                      const badgeSpans = Array.from(headerSection.querySelectorAll('span, div'));
                      let degree = null;
                      for (const el of badgeSpans) {
                          const text = (el.textContent || '').trim().toLowerCase();
                          if (text.includes('1st') || text.includes('1.') || text === 'प्रथम') {
                              degree = '1st'; break;
                          }
                          if (text.includes('2nd') || text.includes('2.') || text.includes('3rd') || text.includes('3.') || text.includes('3rd+')) {
                              degree = 'other'; break;
                          }
                      }
                      if (degree === "1st") return { status: "Connected", reason: "Found 1st degree badge" };
                      
                      // Priority 4: Connect button strictly in Header or Dropdown (excludes sidebar)
                      const combinedConnectActions = headerActions.concat(dropdownActions);
                      const hasConnect = combinedConnectActions.some(el => {
                          const text = (el.textContent || '').trim().toLowerCase();
                          const label = (el.getAttribute('aria-label') || '').toLowerCase();
                          const isConnectBtn = (text === 'connect' || text === '+ connect' || text === 'vernetzen' || text === 'कनेक्ट करें' || (label.includes('invite') && label.includes('connect')));
                          return isConnectBtn && !text.includes('remove') && !label.includes('remove');
                      });
                      if (hasConnect) return { status: "Not Started", reason: "Found explicit Connect button" };
                      
                      // Priority 5: Message button strictly in Header
                      const hasMessage = headerActions.some(el => {
                          const text = (el.textContent || '').trim().toLowerCase();
                          return text === 'message' || text === 'nachricht' || text === 'संदेश';
                      });
                      if (hasMessage) return { status: "Connected", reason: "Found Message button fallback" };
                      
                      if (degree === "other") return { status: "Not Started", reason: "Found 2nd/3rd degree badge" };
                      return { status: "Not Started", reason: "Default fallback" };
                  }
              """)
    
        detected_status = status_result.get("status", "Not Started")
        acc_state.add_log(f"Profile connection status detected: '{detected_status}'", "info")
        
        # Close the More dropdown if it was opened during the scan to avoid alarming users
        try:
            page.keyboard.press("Escape")
            time.sleep(0.5)
        except:
            pass
            
        # DEBUG: Take a screenshot if it's Heike or if it's Not Started so we can see what the bot sees
        if detected_status == "Not Started" or "heike" in username.lower():
            try:
                public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
                screenshot_path = os.path.join(public_dir, f"debug_{username}.png")
                page.screenshot(path=screenshot_path)
                acc_state.add_log(f"Saved debug screenshot to {screenshot_path}", "info")
            except Exception as e:
                acc_state.add_log(f"Failed to capture debug screenshot: {str(e)}", "warning")
                
        return detected_status
        
    except Exception as e:
        acc_state.add_log(f"Error verifying status on profile for {username}: {str(e)}", "warning")
        return "Error"

def sync_acceptance_task_sync(account_id="default", db_type="prospects"):
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
        try:
            page.goto("https://www.linkedin.com/mynetwork/invitation-manager/sent/", wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            acc_state.add_log(f"Page load taking longer than 60s, continuing anyway... ({str(e)})", "warning")
        time.sleep(5)
        
        last_count = 0
        no_change_count = 0
        max_scroll_steps = 25
        
        acc_state.add_log("Scrolling through Sent invitations list dynamically to load all pending items...", "info")
        for scroll_step in range(1, max_scroll_steps + 1):
            if acc_state.stop_requested:
                break
            in_links = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => a.href).filter(h => h && h.includes('/in/'))")
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
        hrefs = page.evaluate("Array.from(document.querySelectorAll('a')).map(a => a.href).filter(h => h && h.includes('/in/'))")
        for href in hrefs:
            try:
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
            
        db_data = load_db(account_id, db_type)
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
                if status in ["Sent", "Pending"] or (status == "Connected" and (contact.get("email") is None or contact.get("phone") is None or contact.get("date_accepted") is None or contact.get("date_accepted") == "")):
                    if contact_username:
                        verified_status = verify_profile_status(page, contact_username, acc_state)
                        if verified_status == "Connected":
                            if status != "Connected":
                                contact["status"] = "Connected"
                                contact["date_accepted"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                acc_state.add_log(f"Verified connection: {contact_name} is Connected! Initiating contact enrichment...", "success")
                                updated_count += 1
                            else:
                                acc_state.add_log(f"Profile {contact_name} confirmed Connected but lacks info. Attempting enrichment...", "info")
                            should_enrich = True
                        elif verified_status == "Pending":
                            acc_state.add_log(f"Verified status: {contact_name} is still Pending on LinkedIn.", "info")
                            if status != "Pending":
                                contact["status"] = "Pending"
                                contact["date_accepted"] = None
                                acc_state.add_log(f"Auto-fixed corrupted database status for {contact_name}: Reverted back to Pending.", "warning")
                                updated_count += 1
                        elif verified_status == "Not Started":
                            contact["status"] = "Not Started"
                            contact["date_sent"] = None
                            contact["date_accepted"] = None
                            acc_state.add_log(f"Verified status: {contact_name} has no active pending invitation. Status reset to 'Not Started'.", "warning")
                            updated_count += 1
                        else:
                            acc_state.add_log(f"Verification failed or inconclusive for {contact_name}. Leaving status as {status} for safety.", "warning")
                    
                if should_enrich:
                    if contact_username:
                        try:
                            email, phone, connection_date, birthday = scrape_contact_info(page, contact_username, account_id)
                            contact["email"] = email if email else "Not Shared"
                            contact["phone"] = phone if phone else "Not Shared"
                            contact["dob"] = birthday if birthday else None
                            if connection_date:
                                contact["linkedin_connection_date"] = connection_date
                                # Prioritize the date the system synced/discovered the connection so they appear on the dashboard!
                                # Only use the scraped historical date if we have absolutely no date recorded.
                                if not contact.get("date_accepted"):
                                    contact["date_accepted"] = connection_date
                            # NEW AUTO-MESSAGE LOGIC
                            if contact.get("status") == "Connected" and not contact.get("message_sent"):
                                acc_state.add_log(f"Profile is Connected and no welcome message sent yet. Attempting to send Auto-Welcome message...", "info")
                                try:
                                    template_chosen = random.choice(SPINTAX_TEMPLATES)
                                    msg = resolve_template(template_chosen, contact, next((a.get('name').split()[0] for a in load_accounts_registry() if a['id'] == account_id), account_id))
                                    if send_followup_message(page, msg, acc_state, contact.get('name', '')):
                                        acc_state.add_log(f"Auto-Welcome message successfully sent to {contact.get('name')}!", "success")
                                        contact["message_sent"] = True
                                        contact["date_messaged"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        
                                        # Automatically mark any duplicate entries in the database as sent too
                                        raw_url = contact.get("profile_url", "").strip()
                                        url_clean = raw_url.split("?")[0].rstrip("/")
                                        sent_username = url_clean.split("/in/")[-1].strip().lower() if "/in/" in url_clean else ""
                                        
                                        for c in db_data:
                                            c_url = c.get("profile_url", "").strip()
                                            c_clean = c_url.split("?")[0].rstrip("/")
                                            c_username = c_clean.split("/in/")[-1].strip().lower() if "/in/" in c_clean else ""
                                            if sent_username and c_username == sent_username:
                                                c["message_sent"] = True
                                                c["date_messaged"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                                
                                    else:
                                        acc_state.add_log(f"Failed to send Auto-Welcome message to {contact.get('name')}.", "warning")
                                except Exception as msg_err:
                                    acc_state.add_log(f"Auto-Welcome message error: {str(msg_err)}", "warning")
                                    
                        except Exception as enrichment_err:
                            acc_state.add_log(f"Enrichment error for {contact.get('name', 'Unknown')}: {str(enrichment_err)}", "warning")
                        finally:
                            try:
                                acc_state.add_log("Returning to Sent Invitations page...", "info")
                                try:
                                    page.goto("https://www.linkedin.com/mynetwork/invitation-manager/sent/", wait_until="domcontentloaded", timeout=60000)
                                except Exception as e:
                                    acc_state.add_log(f"Page load taking longer than 60s, continuing anyway... ({str(e)})", "warning")
                                time.sleep(3)
                            except Exception as return_err:
                                acc_state.add_log(f"Failed to navigate back to Sent Invitations: {str(return_err)}", "warning")
                    if status == "Connected":
                        updated_count += 1
        
        if updated_count > 0:
            save_db(db_data, account_id, db_type)
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

def run_automation_worker_sync(account_id="default", config=None, db_type="prospects"):
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
        db_data = load_db(account_id, db_type)
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
        
        # Calculate the date of the most recent Wednesday at 00:00:00
        from datetime import timedelta
        offset = (now.weekday() - 2) % 7
        last_wed = now - timedelta(days=offset)
        last_wed = last_wed.replace(hour=0, minute=0, second=0, microsecond=0)
        
        for c in db_data:
            if c.get("status") not in ["Pending", "Connected", "Sent"]:
                continue
            ds = c.get("date_sent")
            if ds:
                try:
                    if ds.startswith(today_str):
                        sent_today_count += 1
                    dt = datetime.strptime(ds, "%Y-%m-%d %H:%M:%S")
                    # Count if the request was sent exactly on or after the most recent Wednesday
                    if dt >= last_wed:
                        sent_week_count += 1
                except:
                    pass
                    
        acc_state.add_log(f"Safety Pre-Scan: {sent_today_count} sent today, {sent_week_count} sent this week (since Wednesday). Limits: Daily {daily_limit}, Weekly {weekly_limit}.", "info")
        
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
            
            
            if not profile_url:
                contact["status"] = "Failed"
                contact["logs"] = "Empty profile URL"
                contact["date_sent"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                sent_today_count += 1
                sent_week_count += 1
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
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(1.5)
                
                # OLD RELIABLE PYTHON STATUS CHECKER (Restored from automation - Copy.py)
                is_first_degree = False
                is_second_or_third_degree = False
                
                HEADER_ANCHOR = "xpath=(//main//section[1]//h1 | //main//section[1]//h2)[1]/ancestor::section[1]"
                
                # 1. Look for specific degree badges inside the main layout
                degree_selectors = [
                    f"{HEADER_ANCHOR}//*[contains(@class, 'dist-value')]",
                    f"{HEADER_ANCHOR}//*[text()='1st' or text()='2nd' or text()='3rd' or contains(text(), '1st') or contains(text(), '2nd') or contains(text(), '3rd')]",
                    "main.scaffold-layout__main span.dist-value",
                    "main.scaffold-layout__main [class*='dist-value']",
                    ".pv-text-details__leftpanel span.dist-value",
                    ".pv-member-badge span.dist-value"
                ]
                
                for sel in degree_selectors:
                    try:
                        badge = page.locator(sel).first
                        if badge.is_visible():
                            degree_text = (badge.text_content() or "").strip().lower()
                            if "1st" in degree_text or "1." in degree_text or "प्रथम" in degree_text:
                                is_first_degree = True
                                break
                            elif "2nd" in degree_text or "3rd" in degree_text or "2." in degree_text or "3." in degree_text:
                                is_second_or_third_degree = True
                                break
                    except Exception:
                        continue
                        
                already_connected = False
                if is_first_degree:
                    already_connected = True
                    
                if already_connected:
                    contact["status"] = "Connected"
                    acc_state.add_log(f"Already connected with {contact.get('name', 'this user')} (1st degree). Marked as Connected.", "success")
                    contact["date_accepted"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    db_data_fresh = load_db(account_id, db_type)
                    for d in db_data_fresh:
                        if d["profile_url"] == profile_url:
                            d["status"] = "Connected"
                            d["date_accepted"] = contact["date_accepted"]
                    save_db(db_data_fresh, account_id, db_type)
                    continue
                    
                # Scoped check to determine if invitation is already pending
                pending_selectors = [
                    f"{HEADER_ANCHOR}//button[contains(., 'Pending') or contains(., 'Sent')]",
                    f"{HEADER_ANCHOR}//*[text()='Pending' or text()='Sent']",
                    "main [class*='top-card'] button:has-text('Pending')",
                    "main [class*='top-card'] button:has-text('Sent')"
                ]
                
                pending_button = page.locator(pending_selectors[0]).first
                for sel in pending_selectors:
                    try:
                        btn = page.locator(sel).first
                        if btn.is_visible():
                            pending_button = btn
                            break
                    except Exception:
                        continue
                        
                if pending_button and pending_button.is_visible():
                    contact["status"] = "Pending"
                    acc_state.add_log(f"Request is already pending for {contact.get('name', 'this user')}.", "info")
                    db_data_fresh = load_db(account_id, db_type)
                    for d in db_data_fresh:
                        if d["profile_url"] == profile_url:
                            d["status"] = "Pending"
                            if not d.get("date_sent"):
                                d["date_sent"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                contact["date_sent"] = d["date_sent"]
                    save_db(db_data_fresh, account_id, db_type)
                    continue

                clicked_connect = False
                acc_state.add_log("Primary strategy: Searching for direct 'Connect' button on the profile header...", "info")
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
                    try:
                        connect_button.click(force=True)
                    except Exception as click_err:
                        acc_state.add_log(f"Playwright locator click failed: {click_err}.", "warning")
                    clicked_connect = True
                else:
                    acc_state.add_log("Direct 'Connect' button not visible or disabled on header.", "info")
                    
                if not clicked_connect:
                    acc_state.add_log("Fallback: Looking for 'More' or '...' dropdown button...", "info")
                    more_button = None

                    # --- STRATEGY 1: Try standard CSS/aria-label selectors (strictly scoped to top card section) ---
                    more_selectors = [
                        # Strict XPath selectors inside the profile's top card
                        f"{HEADER_ANCHOR}//button[@aria-label='More actions']",
                        f"{HEADER_ANCHOR}//button[@aria-label='See more actions']",
                        f"{HEADER_ANCHOR}//button[contains(@aria-label, 'More')]",
                        f"{HEADER_ANCHOR}//button[contains(@aria-label, 'more')]",
                        f"{HEADER_ANCHOR}//button[contains(., 'More')]",
                        f"{HEADER_ANCHOR}//button[contains(., 'more')]",
                        
                        # Strict CSS selectors inside the profile top card
                        "main section:first-of-type button[aria-label='More actions']",
                        "main section:first-of-type button[aria-label='See more actions']",
                        "main section:first-of-type button[aria-label*='More']",
                        "main section:first-of-type button[aria-label*='more']",
                        "main section:first-of-type button:has-text('More')",
                        "main section:first-of-type button[aria-expanded]",
                        "main [class*='top-card'] button[aria-label='More actions']",
                        "main [class*='top-card'] button[aria-label='See more actions']",
                        "main [class*='top-card'] button[aria-label*='More']",
                        "main [class*='top-card'] button[aria-label*='more']",
                        ".pvs-profile-actions button:has-text('More')",
                        "main [class*='top-card'] button:has-text('More')",
                        "main [class*='top-card'] .artdeco-button--muted.artdeco-button--icon",
                        "xpath=//main//section[1]//button[normalize-space(.)='More']",
                        "xpath=//main//section[1]//button[contains(., 'More')]",
                        "xpath=//main//section[1]//button[contains(@aria-label, 'More actions')]"
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
                                    // Get buttons strictly inside the profile's first top card section to prevent collisions
                                    const topCard = document.querySelector('main section') || document.querySelector('main [class*="top-card"]') || document.querySelector('main');
                                    const allBtns = topCard ? Array.from(topCard.querySelectorAll('button')) : [];
                                    
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

                    # Tracking failure reasons for detailed database and dashboard logs
                    detailed_fail_reason = "Connect option not visible or disabled on header."
                    
                    if more_button:
                        if more_button is not True:
                            try:
                                more_button.click(force=True)
                            except Exception as click_err:
                                acc_state.add_log(f"Playwright locator click on More button failed: {click_err}.", "warning")
                            acc_state.add_log("Clicked More/... button. Waiting for dropdown...", "info")
                            time.sleep(random.uniform(2.0, 3.0))

                        dropdown_connect = None
                        # Broader set of selectors for Connect inside LinkedIn's More dropdown
                        dropdown_connect_selectors = [
                            "xpath=//*[@role='menuitem']//*[text()='Connect']",
                            "xpath=//*[@role='menuitem']//*[text()='Invite']",
                            "xpath=//*[@role='menu']//*[text()='Connect']",
                            "xpath=//*[@role='menu']//*[text()='Invite']",
                            "xpath=//*[text()='Connect']",
                            "xpath=//*[text()='Invite']",
                            "[role='menuitem'] p:text-is('Connect')",
                            "[role='menuitem'] span:text-is('Connect')",
                            "p:text-is('Connect')",
                            "span:text-is('Connect')",
                            "div[role='button']:has-text('Connect')",
                            "div[role='button']:has-text('Invite')",
                            "li:has-text('Connect')",
                            "li:has-text('Invite')",
                            "span:has-text('Connect')",
                            "span:has-text('Invite')",
                            "p:has-text('Connect')",
                            "[role='menuitem'] :has-text('Connect')",
                            "[role='menuitem'] :has-text('Invite')",
                            "[role='menuitem']:has-text('Connect')",
                            "[role='menuitem']:has-text('Invite')",
                            "[aria-label^='Connect']",
                            "[aria-label^='Invite']",
                            "[aria-label='Connect']",
                            "[aria-label='Invite']"
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
                                            const text = (item.innerText || item.textContent || '').trim().toLowerCase();
                                            if (text.includes('connect') && !text.includes('remove') && !text.includes('message') && !text.includes('report') && !text.includes('block')) {
                                                const btn = item.closest('button') || item.querySelector('button') || item.closest('div[role="button"]') || item;
                                                if (btn && btn.offsetHeight > 0) {
                                                    btn.click();
                                                    return true;
                                                }
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
                            try:
                                dropdown_connect.evaluate("el => el.click()")
                            except Exception as js_err:
                                acc_state.add_log(f"Playwright locator.evaluate click on dropdown Connect failed: {js_err}. Trying fallback locator click...", "warning")
                                dropdown_connect.click(force=True)
                            clicked_connect = True
                        elif not clicked_connect:
                            acc_state.add_log("Could not find 'Connect' in the 'More' dropdown. Taking screenshot for debug...", "warning")
                            detailed_fail_reason = "Connect option not found inside the 'More' dropdown menu (profile may have connection limits or require email verification)."
                            try:
                                screenshot_dir = r"C:\Users\lenovo\.gemini\antigravity-ide\brain\5d2cf3c0-0265-42fb-8309-82621cd19047"
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
                        detailed_fail_reason = "Could not locate 'More' or '...' actions dropdown button on profile card."
                                
                if not clicked_connect:
                    acc_state.add_log(f"Skipping {contact.get('name', 'Contact')}: Connect action not available. Capturing debug screenshot...", "warning")
                    try:
                        screenshot_dir = r"C:\Users\lenovo\.gemini\antigravity-ide\brain\5d2cf3c0-0265-42fb-8309-82621cd19047"
                        os.makedirs(screenshot_dir, exist_ok=True)
                        page.screenshot(path=os.path.join(screenshot_dir, "debug_connect_missing.png"))
                    except:
                        pass
                    contact["status"] = "Failed"
                    contact["logs"] = detailed_fail_reason
                    contact["date_sent"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sent_today_count += 1
                    sent_week_count += 1
                    db_data_fresh = load_db(account_id, db_type)
                    for d in db_data_fresh:
                        if d["profile_url"] == profile_url:
                            d["status"] = "Failed"
                            d["logs"] = detailed_fail_reason
                            d["date_sent"] = contact["date_sent"]
                    save_db(db_data_fresh, account_id, db_type)
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
                                note_text = resolve_template(note_template, contact, next((a.get('name').split()[0] for a in load_accounts_registry() if a['id'] == account_id), account_id))
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
                
                db_data_fresh = load_db(account_id, db_type)
                for d in db_data_fresh:
                    if d["profile_url"] == profile_url:
                        d["status"] = "Pending"
                        d["date_sent"] = contact["date_sent"]
                save_db(db_data_fresh, account_id, db_type)
                
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
                contact["date_sent"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_data_fresh = load_db(account_id, db_type)
                for d in db_data_fresh:
                    if d["profile_url"] == profile_url:
                        d["status"] = "Failed"
                        d["logs"] = str(ex)
                        d["date_sent"] = contact["date_sent"]
                save_db(db_data_fresh, account_id, db_type)
                
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
def run_automation_worker(note_template=None, send_with_note=False, delay_min=30, delay_max=70, daily_limit=25, weekly_limit=150, start_index=None, end_index=None, account_id="default", db_type="prospects"):
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
    return queue_runner.add_to_queue("automation", account_id, lambda: run_automation_worker_sync(account_id, config, db_type))

def sync_acceptance_task(account_id="default", db_type="prospects"):
    return queue_runner.add_to_queue("sync", account_id, lambda: sync_acceptance_task_sync(account_id, db_type))

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

def run_messaging_worker_sync(account_id="default", config=None, db_type="prospects"):
    from datetime import datetime
    import random
    import time
    acc_state = get_account_state(account_id)
    acc_state.update_status(action="Starting messaging sequence...", progress=5)
    update_account_status_in_registry(account_id, status="Running", current_action="Starting messaging sequence...", progress_percent=5)
    acc_state.add_log("Starting LinkedIn Messaging Sequence...", "info")
    
    if not config:
        config = {}
    delay_min = int(config.get("delay_min", 30))
    delay_max = int(config.get("delay_max", 60))
    
    start_index = config.get("start_index")
    end_index = config.get("end_index")
    try: start_index = int(start_index) if start_index is not None else None
    except: start_index = None
    try: end_index = int(end_index) if end_index is not None else None
    except: end_index = None

    db_data = load_db(account_id, db_type)
    
    # Filter by range if provided
    if start_index is not None or end_index is not None:
        s_idx = start_index if start_index is not None else 1
        e_idx = end_index if end_index is not None else len(db_data)
        s_idx = max(1, s_idx)
        e_idx = min(len(db_data), e_idx)
        if s_idx <= e_idx:
            db_data_slice = db_data[s_idx - 1 : e_idx]
            acc_state.add_log(f"Range filter active: targeting profiles from Sr. No. {s_idx} to {e_idx}.", "info")
        else:
            db_data_slice = db_data
            acc_state.add_log(f"Invalid range. Processing full list.", "warning")
    else:
        db_data_slice = db_data
    
    # Filter for connected users and deduplicate by URL to prevent messaging the same person twice
    unique_urls = set()
    contacts_to_message = []
    for c in db_data_slice:
        if c.get("status") == "Connected" and not c.get("message_sent"):
            raw_url = c.get("profile_url", "").strip().lower()
            # Normalize URL (remove www., trailing slashes, etc.)
            norm_url = raw_url.replace("www.", "").replace("http://", "https://").rstrip('/')
            if norm_url and norm_url not in unique_urls:
                unique_urls.add(norm_url)
                contacts_to_message.append(c)
    
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
            
            template_chosen = random.choice(SPINTAX_TEMPLATES)
            msg = resolve_template(template_chosen, contact, next((a.get('name').split()[0] for a in load_accounts_registry() if a['id'] == account_id), account_id))
            if send_followup_message(page, msg, acc_state, contact.get('name', '')):
                acc_state.add_log(f"Message sent to {contact.get('name')}!", "success")
                contact["message_sent"] = True
                contact["date_messaged"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Automatically mark any duplicate entries in the database as sent too
                raw_url = contact.get("profile_url", "").strip().lower()
                norm_url = raw_url.replace("www.", "").replace("http://", "https://").rstrip('/')
                for c in db_data:
                    c_url = c.get("profile_url", "").strip().lower()
                    c_norm = c_url.replace("www.", "").replace("http://", "https://").rstrip('/')
                    if c_norm == norm_url and c_norm:
                        c["message_sent"] = True
                        c["date_messaged"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                save_db(db_data, account_id, db_type)
            else:
                acc_state.add_log(f"Failed to send message to {contact.get('name')}.", "warning")
                
        except Exception as e:
            acc_state.add_log(f"Error messaging {contact.get('name')}: {str(e)}", "warning")
            
        if idx < len(contacts_to_message) - 1 and not acc_state.stop_requested:
            delay = random.randint(delay_min, delay_max)
            acc_state.add_log(f"Waiting {delay} seconds before next message...", "info")
            time.sleep(delay)
            
    acc_state.update_status(action="Idle", progress=100)
    update_account_status_in_registry(account_id, status="Idle", current_action="Idle", progress_percent=100)
    if context:
        try: context.close()
        except: pass
    if playwright:
        try: playwright.stop()
        except: pass
    acc_state.stop_running()

def start_messaging_worker(account_id="default", config=None, db_type="prospects"):
    acc_state = get_account_state(account_id)
    if acc_state.get_state()["is_running"]:
        return {"status": "error", "error": "Another task is already running."}
    acc_state.start_running()
    queue_runner.add_to_queue("MESSAGING", account_id, lambda: run_messaging_worker_sync(account_id, config, db_type))
    return {"status": "success", "message": "Messaging started"}
