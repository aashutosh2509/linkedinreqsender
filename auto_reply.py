import time
import os
import json
import threading
from playwright.sync_api import sync_playwright

from automation import launch_browser, get_account_state, update_account_status_in_registry

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None

import smtplib
from email.mime.text import MIMEText

# --- EMAIL CONFIGURATION FOR MEETING TEAM ---
# Fill these in with your Gmail details. You MUST use a 16-digit "App Password", not your normal Gmail password.
SENDER_EMAIL = "your_email@gmail.com" 
SENDER_APP_PASSWORD = "your_16_digit_app_password"
RECEIVER_EMAIL = "team_email@gmail.com" # The email of your meeting handling team

def send_handoff_email(lead_name, thread_url, chat_history):
    try:
        if "your_email@gmail.com" in SENDER_EMAIL:
            return # Skip if user hasn't configured it yet
            
        subject = f"🚨 New Meeting Booked! LinkedIn Lead: {lead_name}"
        
        body = f"A new hot lead has booked a meeting on LinkedIn!\n\n"
        body += f"Lead Name: {lead_name}\n"
        body += f"LinkedIn Thread: {thread_url}\n\n"
        body += "--- CHAT HISTORY ---\n"
        for msg in chat_history:
            role = "Our Bot" if msg["role"] == "assistant" else "Lead"
            body += f"{role}: {msg['content']}\n"
            
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            smtp_server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            
        print("Successfully sent chat history email to the team!")
    except Exception as e:
        print(f"Failed to send email: {e}")

# We store replied thread URLs and their last message snippets so we don't reply multiple times
STATE_FILE = os.path.join("linkedin_user_data", "auto_reply_state.json")
def load_reply_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_reply_state(state):
    os.makedirs("linkedin_user_data", exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)

def save_chat_history_to_db(account_id, lead_name, thread_url, chat_history, full_name=None, headline=None):
    DATA_DIR = "C:\\data" if os.name == 'nt' and os.path.exists("C:\\data") else "/data"
    os.makedirs(DATA_DIR, exist_ok=True)
    chats_file = os.path.join(DATA_DIR, f"chats_{account_id}.json")
    try:
        if os.path.exists(chats_file):
            with open(chats_file, "r", encoding="utf-8") as f:
                chats = json.load(f)
        else:
            chats = {}
            
        # The user requested to NOT show 1-way chats in the CRM.
        # If the prospect has never replied (no 'user' messages), we skip saving it.
        has_user_reply = any(msg.get("role") == "user" for msg in chat_history)
        
        if not has_user_reply:
            # If it's a 1-way chat, remove it from the CRM if it exists
            if thread_url in chats:
                del chats[thread_url]
                with open(chats_file, "w", encoding="utf-8") as f:
                    json.dump(chats, f, indent=4)
            return
            
        chats[thread_url] = {
            "lead_name": lead_name,
            "full_name": full_name,
            "headline": headline,
            "thread_url": thread_url,
            "messages": chat_history,
            "last_updated": time.time()
        }
        
        with open(chats_file, "w", encoding="utf-8") as f:
            json.dump(chats, f, indent=4)
    except Exception as e:
        print(f"Error saving chat history: {e}")

def generate_ai_reply(api_key, chat_history, lead_name=""):
    if not genai:
        raise Exception("Google GenAI package is not installed. Run 'pip install google-genai'.")
    
    client = genai.Client(api_key=api_key)
    
    system_prompt = f"""
You are the human behind this LinkedIn profile. You work as an employee at 'NB Entrepreneurs'. YOU ARE A REAL HUMAN. NEVER claim to be the CEO, Founder, or Owner of the company unless explicitly stated.
You are chatting with a lead named: '{lead_name}'.

# Core Guidelines
1. Tone: Helpful, brief, casual but professional, and curious (not pushy).
2. DO NOT sound like a bot. NEVER reveal that you are an AI, a bot, or an assistant. Speak strictly in the first-person as a human professional.
3. NEVER close orders, quote final prices, promise credit terms, or make regulatory commitments.
4. Avoid "Dear Sir", heavy brochures, or "We are the best" claims.
5. Language Matching (CRITICAL): Detect the language of the lead's MOST RECENT message. You MUST reply in that EXACT same language. If they wrote in Hindi, your reply MUST be in Hindi. If they wrote in English, your reply MUST be in English. Do not mix up Hindi and Marathi! NEVER skip a message just because it's not in English.
6. Company Facts (To use in conversation):
- We are NB Entrepreneurs, founded in 1976 (over 49 years of experience).
- We operate a cGMP-approved facility in Nagpur, Maharashtra and are ISO 9001-2008 certified.
- Our products comply with IP, USP-NF, BP, and JP compendia.
- Our Brand Names include: SANCEL (Microcrystalline Cellulose/MCC), SOLUCEL (Croscarmellose Sodium/CCS), MAGLUBE (Magnesium Stearate), and STARCEL (Silicified MCC).

# ANTI-HALLUCINATION (CRITICAL PRIORITY)
- YOU ARE ALLOWED to discuss our standard product grades and specific brands because these are standard offerings on our website:
  * SANCEL (MCC): Grades 101, 102, 200, 112.
  * STARCEL (SMCC): Grades SMCC 90, SMCC 90 LM.
  * SOLUCEL (CCS) & MAGLUBE (Magnesium Stearate): We do not list standard grades. If asked, you must say: "We provide these based on your specific formulation requirements (e.g., density or particle size). Let's schedule a quick 10-minute Google Meet with our technical team so we can understand your exact specifications and provide the right grade!" (And then proceed with Step 1 of Meeting Booking).
- NEVER hallucinate, guess, or make up chemical properties, particle sizes, prices, or technical details beyond the basic grade names and brand names above.
- If the lead asks for deeper technical specifications or certificates (COA/TDS), politely tell them: "You can find all our exact technical specifications on our website here: https://nb-cellulose.com/ or I can email you our detailed product catalog.

# Pacing & Lead Objectives (CRITICAL - DO NOT RUSH)
- Single-Topic Rule: You must ONLY talk about "Industry News" or "Market Trends" during the casual phase. DO NOT bring up hobbies, travels, or sports.
- The First Message Rule (STRICT): If this is your very first reply to the lead (e.g., they just said "Thanks for connecting"), YOU MUST NOT MENTION EXCIPIENTS, PRODUCTS, OR SALES YET. You must simply acknowledge their message and ask a casual, open-ended question about their industry (e.g., "What interesting trends are you seeing in the pharmaceutical space lately?").
- Transition to Business: You MUST NOT bring up business, raw materials, or excipient procurement until you have exchanged at least 3 friendly messages. First, focus entirely on building trust and establishing a professional friendship. Only ask about their day-to-day role and general industry challenges. NEVER ask 'does your team handle procurement' early on.
- Cold Lead Assessment: Do NOT assume a short 1-word reply (like 'ok' or 'yes') automatically means they are a cold lead. Look at the context!
- Ultimate Goal: Your ultimate, final objective is to qualify the lead for excipient sales and book a meeting for the sales team, but you must pace yourself.
- Referral/Inbound: If they explicitly messaged YOU asking for products, skip the casual phase completely and treat as Warm.

# Qualification Flow (For WARM Leads only. Ask ONE question at a time)
Optional Early Question: "Before we dive in, may I know your company name and location? This helps us check prior context and regulatory fit."
1. Which product are they evaluating? (e.g., MCC, CCS, Magnesium Stearate, SMCC)
2. Is this for R&D trial, commercial production, vendor development, or distribution?
3. Do they have a specific grade in mind? (e.g., MCC 101, 102, 200)
4. Approximate trial or monthly quantity?
5. Domestic use or export market?
6. Specific pharmacopeia requirement? (IP, BP, EP, USP)

# Lead Scoring (0-100)
- Positive: Company fit (+20), Role fit (+15), Product fit (+15), Buying intent (+25), Volume potential (+10), Geography (+5), Engagement (+10).
- Negative: Wrong industry or Not in excipients (-20 & disqualify).
- Status: 0-30 (Cold), 31-60 (Warm), 61-80 (Hot), 81+ (SQL).

# Handling Rejections & 'No' Answers (CRITICAL - FORBIDDEN TO GIVE UP EASILY)
- RULE ZERO: YOU ARE FORBIDDEN from saying "Thank you for your time" or giving up if the lead simply answers "No" or gives a short negative answer to a question.
- Scenario 1: If you ask if they procure excipients/raw materials, and they say "No" (or a variation of it): YOU MUST PIVOT. You MUST ask: "Ah got it! Since your company is in pharma, would you happen to know who in your team handles the raw material or excipient procurement? I'd love to connect with them." Do NOT end the conversation here.
- Scenario 2: If they explicitly say "We are NOT interested in buying", "Stop messaging me", or "We already have a vendor and will not change": ONLY THEN should you stop all sales attempts. Your ONLY response should be a polite, 1-sentence acknowledgment (e.g., "No problem at all, I completely understand. Thanks for your time!"). 
- Scenario 3: If you asked a casual question about industry trends and they brush it off (e.g., "Not at the moment", "No idea"): DO NOT instantly jump into asking about excipients or pitching products! Instead, smoothly change the topic to something else friendly to build a relationship first (e.g., "Fair enough! How are things going at your company otherwise?").
- Scenario 4 (Wrong Industry): If the lead explicitly states they are in a completely different industry (e.g., IT, Software, Hardware, Finance) and are not in Pharma, you MUST gracefully end the conversation. DO NOT ask any follow-up questions about their irrelevant industry. Just send a polite 1-sentence goodbye (e.g., "Ah, I understand! Thanks for clarifying your field, wishing you the best with your projects!"). Set `requires_reply` to TRUE to send this goodbye message.
- Scenario 5 (Student or Not Beneficial): If the lead is a student or clearly not beneficial for business, you MUST gracefully end the conversation with a polite message. DO NOT try to sell to them or ask further questions. Send a polite 1-sentence goodbye (e.g., "Wishing you the best in your studies and future endeavors!"). Set `requires_reply` to TRUE to send this goodbye message.
- IMPORTANT: When sending a polite acknowledgment, a pivot, or a goodbye, you MUST set `requires_reply` to TRUE so the message actually gets sent to them!
- Emotional/Irrelevant Content: If the lead's message is venting about a personal issue, a toxic workplace, politics, or something highly emotional and unrelated to business, DO NOT try to pivot to sales. Show brief, polite empathy (e.g., "I'm sorry to hear you went through that. Wishing you the best.") and set `requires_reply` to FALSE to end the conversation.

# Reply Policy
- ALWAYS set `requires_reply` to TRUE for almost every message, including short acknowledgments like "Thanks", "Ok", or "Got it".
- If they just say "Thanks", respond with a friendly follow-up question (e.g., "You're welcome! How are things going with your current projects?").
- ONLY set `requires_reply` to FALSE if you have ALREADY sent them a final polite rejection acknowledgment in the past. If they just rejected you or said they aren't interested right now, you MUST set `requires_reply` to TRUE and send the polite acknowledgment first!

# Meeting Booking & Handoff Triggers (CRITICAL 3-STEP PROCESS)
- ONLY apply this if the lead is POSITIVE and INTERESTED.
- YOUR ULTIMATE MOTTO IS TO BOOK A 10-MINUTE QUICK MEETING. Once the lead has answered your qualification questions, OR if they actively ask for Price, Samples, COA/TDS/MSDS, mention volume, or want to discuss business:
- Step 1 (Ask for time): Immediately ask them what time works for a quick 10-minute Google Meet THIS WEEK (do not say "next week") so our technical team can understand their exact requirements and arrange trial samples for them to test.
- Step 2 (Send Link & Ask Contact Info): Once they give a time, give the link: https://calendar.app.google/pt5oudMGhUwwFjeH8 AND in the exact same message, ask for their mobile number or email address so your team can send them a calendar invite/reminder. Example: "Here is the link: https://calendar.app.google/pt5oudMGhUwwFjeH8. Also, could you share your mobile number or email so I can send you a quick reminder before the meeting?"
- ONLY set handoff_triggered to true AFTER sending the link.

Read the chat history, determine the current score and state internally, and generate EXACTLY what to reply. Keep it under 3 sentences. Be extremely conversational. DO NOT mention you are an AI or bot. If the lead is not interested, just say goodbye nicely and nothing else.
"""
    
    contents = []
    for msg in chat_history:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
        
    if not contents or contents[-1].role == "model":
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text="(System: The user just connected or hasn't replied yet. Send a casual welcome or follow-up message.)")]))
        
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        temperature=0.7,
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "properties": {
                "reply_text": {"type": "STRING"},
                "handoff_triggered": {"type": "BOOLEAN"},
                "lead_score": {"type": "INTEGER"},
                "requires_reply": {"type": "BOOLEAN", "description": "ALWAYS set to true, unless you have ALREADY sent a 'goodbye' or final acknowledgment in the previous turn. If the lead is rejecting you now, set this to TRUE and write your polite goodbye in reply_text."}
            },
            "required": ["reply_text", "handoff_triggered", "lead_score", "requires_reply"]
        }
    )
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=contents,
        config=config
    )
    
    try:
        data = json.loads(response.text.strip())
        reply_text = data.get("reply_text", "I'll have a colleague connect with you shortly.")
        
        # Ensure it is a single paragraph so Playwright doesn't accidentally send multiple messages on Enter
        reply_text = reply_text.replace("\n\n", " ").replace("\n", " ").strip()
        
        # If Gemini double-escaped unicode characters (like \\u2013), decode them back to normal characters
        import codecs
        if r"\u" in reply_text:
            reply_text = codecs.decode(reply_text, 'unicode_escape')
            
        return reply_text, data.get("handoff_triggered", False), data.get("lead_score", 0), data.get("requires_reply", True)
    except Exception as e:
        return "I'm an automated assistant. I will have a human colleague reach out shortly.", True, 0, True


def run_auto_reply_worker_sync(account_id="default", api_key=None):
    acc_state = get_account_state(account_id)
    acc_state.update_status(action="Starting AI Auto-Responder...", progress=5)
    acc_state.add_log("Starting AI Auto-Responder...", "info")
    
    if not api_key:
        acc_state.add_log("Error: No Gemini API Key provided. Please add it in Settings.", "error")
        acc_state.update_status(action="Idle", progress=0)
        return

    pw = None
    context = None
    try:
        pw, context = launch_browser(account_id, headed=True)
        page = context.pages[0] if context.pages else context.new_page()
        
        acc_state.add_log("Navigating to Messaging inbox...", "info")
        page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded", timeout=45000)
        time.sleep(5)
        
        reply_state = load_reply_state()
        if account_id not in reply_state:
            reply_state[account_id] = {"muted_threads": []}
            
        muted_threads = reply_state[account_id].get("muted_threads", [])
            
        while True:
            if acc_state.stop_requested:
                acc_state.add_log("Stop requested. Exiting continuous monitor...", "info")
                break
                
            # Get list of conversation threads
            # Note: LinkedIn uses `.msg-conversation-listitem`
            acc_state.add_log("Scanning recent conversations...", "info")
            acc_state.update_status(action="Monitoring Inbox...", progress=50)
            update_account_status_in_registry(account_id, current_action="Monitoring Inbox...", progress_percent=50)
            
            # Wait for threads to load
            try:
                page.wait_for_selector(".msg-conversation-listitem", timeout=10000)
            except Exception as wait_err:
                if "closed" in str(wait_err).lower():
                    acc_state.add_log("Browser or page was closed. Exiting auto-responder...", "error")
                    break
                
                acc_state.add_log("Could not find any conversations. Checking if we are logged out or stuck...", "warning")
                
                # Check if page is closed
                try:
                    current_url = page.url
                    if "challenge" in current_url or "checkpoint" in current_url:
                        acc_state.add_log("LinkedIn is asking for a Security Check or CAPTCHA! Please solve it in the browser window.", "error")
                        time.sleep(15)
                        continue
                        
                    page.reload(timeout=15000, wait_until="domcontentloaded")
                except Exception as reload_err:
                    acc_state.add_log(f"Browser connection lost ({reload_err}). Exiting...", "error")
            # Scroll down the conversation list a few times to load older threads (User specifically requested 30 threads)
            try:
                acc_state.add_log("Scrolling inbox to load older messages...", "info")
                for _ in range(2):
                    page.evaluate("""() => {
                        const list = Array.from(document.querySelectorAll('div')).find(el => 
                            el.classList.contains('msg-conversations-container__conversations-list') ||
                            (el.scrollHeight > el.clientHeight && el.querySelector('.msg-conversation-listitem'))
                        );
                        if (list) list.scrollTop = list.scrollHeight;
                    }""")
                    time.sleep(1.5)
            except: pass
            
            # Get list of conversation threads
            threads = page.locator(".msg-conversation-listitem").all()
            
            # Scan top 30 recent threads as requested
            # Extract our own name to perfectly identify our outbound messages
            my_full_name = ""
            try:
                my_name_el = page.locator(".global-nav__me-photo, .global-nav__me img, img.global-nav__me-photo").first
                if my_name_el.count() > 0:
                    my_full_name = my_name_el.get_attribute("alt") or ""
            except: pass
            
            for i in range(min(30, len(threads))):
                if acc_state.stop_requested:
                    break
                    
                try:
                    thread = threads[i]
                    # Skip sponsored ads
                    thread_text = thread.inner_text().strip()
                    if "Sponsored" in thread_text:
                        acc_state.add_log("Skipping Sponsored Ad thread...", "info")
                        continue
                        
                    # Extract lead name from thread snippet before clicking
                    current_lead_name = "there"
                    lead_full_name = ""
                    try:
                        name_el = thread.locator(".msg-conversation-listitem__participant-names, h3, .msg-conversation-card__participant-names").first
                        if name_el.count() > 0:
                            # Extract first name, stripping common prefixes. Using text_content() handles elements scrolled out of view.
                            full_name = name_el.text_content().strip()
                            lead_full_name = full_name
                            if full_name:
                                parts = full_name.split()
                                prefixes = {"dr", "dr.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "prof", "prof.", "er", "er.", "ca", "cma", "adv", "adv.", "cs"}
                                while parts and parts[0].lower() in prefixes:
                                    parts.pop(0)
                                current_lead_name = parts[0] if parts else full_name.split()[0]
                            else:
                                current_lead_name = "there"
                    except:
                        pass
                    
                    # Click the thread to open it safely using force=True to bypass UI overlays while still triggering React events
                    thread.click(force=True)
                    
                    # CRITICAL FIX: Wait for the main chat window to actually load the new thread!
                    # If LinkedIn is slow, it might still show the previous lead's chat history.
                    try:
                        if current_lead_name and current_lead_name != "there":
                            page.wait_for_function(f"""() => {{
                                const headers = Array.from(document.querySelectorAll('h2'));
                                return headers.some(h => h.innerText.toLowerCase().includes('{current_lead_name.lower().replace("'", "\\'")}'));
                            }}""", timeout=5000)
                            time.sleep(2) # EXTRA FIX: Wait for React to finish rendering the message list after the header updates!
                        else:
                            time.sleep(4)
                    except:
                        time.sleep(4) # Fallback if name matching fails or takes too long
                    
                    while True:
                        if acc_state.stop_requested:
                            break
                            
                        thread_url = page.url
                        # SECONDARY NAME EXTRACTION: If we missed the name from the sidebar, grab it from the main chat header!
                        try:
                            header_el = page.locator("h2.msg-entity-lockup__entity-title, .msg-thread__name").first
                            if header_el.count() > 0:
                                header_text = header_el.text_content().strip()
                                if header_text and header_text.lower() not in ["messaging", "messages", "linkedin member"]:
                                    lead_full_name = header_text
                                    parts = header_text.split()
                                    prefixes = {"dr", "dr.", "mr", "mr.", "mrs", "mrs.", "ms", "ms.", "prof", "prof.", "er", "er.", "ca", "cma", "adv", "adv.", "cs"}
                                    while parts and parts[0].lower() in prefixes:
                                        parts.pop(0)
                                    if parts:
                                        current_lead_name = parts[0]
                        except:
                            pass
                            
                        # HEADLINE EXTRACTION
                        lead_headline = ""
                        try:
                            headline_el = page.locator(".msg-entity-lockup__entity-info, .msg-thread__headline").first
                            if headline_el.count() > 0:
                                lead_headline = headline_el.text_content().strip()
                        except:
                            pass
                        
                        # Extract messages
                        # Messages are usually inside .msg-s-message-list-container
                        message_elements = page.locator(".msg-s-event-listitem").all()
                        
                        chat_history = []
                        last_sender_name = None
                        last_message_text = None
                        
                        for msg_el in message_elements[-10:]: # Look at last 10 messages for better context
                            text_el = msg_el.locator(".msg-s-event-listitem__body").first
                            
                            if text_el.count() > 0:
                                text = text_el.text_content().strip()
                                is_me = False
                                
                                # Try to find sender name by looking up to the message group container
                                try:
                                    group_el = msg_el.locator("xpath=ancestor::div[contains(@class, 'msg-s-message-group')]").first
                                    if group_el.count() > 0:
                                        class_str = group_el.get_attribute("class") or ""
                                        if "msg-s-message-group--profile-viewer" in class_str or "msg-s-message-group--me" in class_str:
                                            is_me = True
                                except:
                                    pass
                                
                                # Bulletproof sender verification via native JS DOM traversal (100% reliable)
                                try:
                                    is_me = msg_el.evaluate("""(el, args) => {
                                        // 1. Check classes on the element or any ancestor
                                        if (el.closest('.msg-s-message-group--me, .msg-s-message-group--profile-viewer, .msg-s-event-listitem--me')) {
                                            return true;
                                        }
                                        if (el.closest('.msg-s-message-group--other, .msg-s-event-listitem--other')) {
                                            return false;
                                        }
                                        
                                        const group = el.closest('.msg-s-message-group');
                                        const searchContainer = group || el; // Fallback to checking the element itself if no group
                                        
                                        const leadName = (args.leadName || "").toLowerCase();
                                        const leadFull = (args.leadFull || "").toLowerCase();
                                        const myFull = (args.myFull || "").toLowerCase();
                                        const accountId = (args.accountId || "").toLowerCase();
                                        
                                        // 2. Check the visible display name attached to the message group
                                        const nameEl = searchContainer.querySelector('.msg-s-message-group__name, .msg-s-message-group__profile-name');
                                        if (nameEl) {
                                            const nameText = nameEl.innerText.toLowerCase();
                                            // If the name matches OUR name (extracted or account ID), we sent it!
                                            if (myFull && nameText.includes(myFull.split(' ')[0])) return true;
                                            if (accountId && nameText.includes(accountId)) return true;
                                            
                                            // If the name matches THEIR name, they sent it!
                                            if (leadName !== "there" && nameText.includes(leadName)) return false;
                                        }
                                        
                                        // 3. Check the profile URLs attached to the message group
                                        const profileLinks = Array.from(searchContainer.querySelectorAll('a[href*="/in/"]'));
                                        for (const a of profileLinks) {
                                            const href = (a.href || "").toLowerCase();
                                            if (leadName !== "there" && href.includes(leadName)) return false;
                                        }
                                        
                                        // 4. Check for 'seen' receipts (only our own outbound messages have these)
                                        const receipt = el.querySelector('.msg-s-event-listitem__seen-receipt, li-icon[type^="status-"], li-icon[type="check"], [data-test-icon^="status-"]');
                                        if (receipt) return true;
                                        
                                        // FINAL FALLBACK
                                        return false; // If we can't prove it's us, assume it's them to prevent dropping their messages!
                                    }""", {"leadName": current_lead_name, "leadFull": lead_full_name, "myFull": my_full_name, "accountId": account_id})
                                except Exception as e:
                                    print(f"EVALUATE EXCEPTION: {e}")
                                    pass
                                
                                # (Removed signature fallback because it falsely identifies lead messages ending with our name as our own)
                                
                                role = "assistant" if is_me else "user"
                                chat_history.append({"role": role, "content": text})
                                if not is_me:
                                    last_message_text = text
                                    
                        if chat_history:
                            save_chat_history_to_db(account_id, current_lead_name, thread_url, chat_history, full_name=lead_full_name, headline=lead_headline)
                            
                        if thread_url in muted_threads:
                            acc_state.add_log(f"Skipping AI generation for muted thread (Human Handoff): {thread_url}", "info")
                            break
                            

                        msg_hash = None
                        
                        if not chat_history:
                            # New connection, no history
                            msg_hash = thread_url + "|INIT"
                            if msg_hash in reply_state[account_id]:
                                break
                            acc_state.add_log(f"Initiating conversation with new connection '{current_lead_name}'...", "info")
                        elif chat_history[-1]["role"] == "assistant":
                            # Last message is from us. 
                            # We strictly DO NOT send automated follow-ups if they haven't replied.
                            acc_state.add_log(f"Skipping thread because last message is from us. Content: '{chat_history[-1]['content'][:100]}'", "info")
                            break
                        else:
                            # Last message is from the lead
                            msg_hash = thread_url + "|" + str(len(chat_history)) + "|" + chat_history[-1]["content"]
                            if msg_hash in reply_state[account_id]:
                                break
                            acc_state.add_log(f"Found new message requiring reply: '{chat_history[-1]['content'][:50]}...'", "info")
                            
                        acc_state.add_log(f"Asking AI for a response for lead '{current_lead_name}'...", "info")
                        
                        reply_text, handoff_triggered, lead_score, requires_reply = generate_ai_reply(api_key, chat_history, lead_name=current_lead_name)
                        
                        # HARDCODED OVERRIDE: NEVER ignore the lead's very first message
                        user_message_count = sum(1 for m in chat_history if m["role"] == "user")
                        if user_message_count == 1:
                            acc_state.add_log(f"Hardcoded override: Forcing reply because this is '{current_lead_name}'s first message.", "info")
                            requires_reply = True
                            if not reply_text or len(reply_text.strip()) < 2 or reply_text.lower() in ["none", "n/a", "null"]:
                                reply_text = f"Thanks for connecting, {current_lead_name}! What interesting trends are you seeing in the pharmaceutical space lately?"
                                acc_state.add_log(f"Fallback reply text injected: '{reply_text}'", "info")
                        
                        if not requires_reply:
                            acc_state.add_log(f"AI determined no reply is needed for '{current_lead_name}'. Skipping.", "info")
                            reply_state[account_id][msg_hash] = True
                            save_reply_state(reply_state)
                            break
                            
                        acc_state.add_log(f"AI generated reply (Score: {lead_score}): '{reply_text}'", "success")
                        
                        if handoff_triggered:
                            acc_state.add_log("HANDOFF TRIGGERED! Thread will be muted after this message.", "warning")
                        
                        # Type and send
                        editor_selectors = [
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
                        editor = None
                        for sel in editor_selectors:
                            try:
                                for j in range(page.locator(sel).count()):
                                    el = page.locator(sel).nth(j)
                                    if el.is_visible():
                                        editor = el
                                        break
                                if editor:
                                    break
                            except:
                                pass
                        
                        # FALLBACK: If it's a Message Request or InMail, the text box is hidden until we click 'Accept' or 'Reply'
                        if not editor:
                            try:
                                fallback_buttons = page.locator("button:has-text('Accept'), button:has-text('Reply')").all()
                                for btn in fallback_buttons:
                                    if btn.is_visible():
                                        btn.click()
                                        time.sleep(2)
                                        # Try finding the editor one more time
                                        for sel in editor_selectors:
                                            if page.locator(sel).first.is_visible():
                                                editor = page.locator(sel).first
                                                break
                                        break
                            except:
                                pass
                                
                        if editor:
                            editor.click()
                            # Clear it first just in case
                            editor.press("Control+A")
                            editor.press("Backspace")
                            time.sleep(0.5)
                            # Type the reply instantly using insert_text or fast type
                            # Insert text is much faster and prevents timeout errors
                            page.keyboard.insert_text(reply_text)
                            time.sleep(1)
                            
                            # Hit Send
                            send_selectors = [
                                "button.msg-form__send-button",
                                ".msg-form__send-button"
                            ]
                            send_btn = None
                            for sel in send_selectors:
                                try:
                                    for j in range(page.locator(sel).count()):
                                        el = page.locator(sel).nth(j)
                                        if el.is_visible() and not el.is_disabled():
                                            send_btn = el
                                            break
                                    if send_btn:
                                        break
                                except:
                                    pass
                                    
                            if send_btn:
                                send_btn.click()
                                time.sleep(2)
                                acc_state.add_log("Reply sent successfully!", "success")
                                
                                chat_history.append({"role": "assistant", "content": reply_text})
                                save_chat_history_to_db(account_id, current_lead_name, thread_url, chat_history)

                                # Save state so we don't reply again
                                reply_state[account_id][msg_hash] = True
                                if handoff_triggered:
                                    reply_state[account_id].setdefault("muted_threads", []).append(thread_url)
                                    acc_state.add_log("Sending chat history to meeting team via email...", "info")
                                    send_handoff_email(current_lead_name, thread_url, chat_history)
                                save_reply_state(reply_state)
                                
                                if handoff_triggered:
                                    break
                                    
                                # Wait 12 seconds to see if they reply immediately
                                acc_state.add_log("Waiting 12 seconds to see if the lead replies immediately...", "info")
                                for _ in range(12):
                                    if acc_state.stop_requested: break
                                    time.sleep(1)
                                    
                                if acc_state.stop_requested: break
                                
                                # Re-check messages
                                new_message_elements = page.locator(".msg-s-event-listitem").all()
                                if new_message_elements:
                                    msg_el = new_message_elements[-1]
                                    text_el = msg_el.locator(".msg-s-event-listitem__body").first
                                    sender_name_el = msg_el.locator(".msg-s-message-group__name").first
                                    
                                    is_me = False
                                    
                                    # Bulletproof sender verification via native JS DOM traversal (100% reliable)
                                    try:
                                        is_me = msg_el.evaluate("""(el, args) => {
                                            const group = el.closest('.msg-s-message-group');
                                            const searchContainer = group || el;
                                            
                                            if (searchContainer.classList.contains('msg-s-message-group--me') || 
                                                searchContainer.classList.contains('msg-s-message-group--profile-viewer') ||
                                                el.classList.contains('msg-s-event-listitem--me')) {
                                                return true;
                                            }
                                            
                                            const leadName = (args.leadName || "").toLowerCase();
                                            const leadFull = (args.leadFull || "").toLowerCase();
                                            
                                            const profileLinks = Array.from(searchContainer.querySelectorAll('.msg-s-message-group__profile-link'));
                                            for (const a of profileLinks) {
                                                const href = (a.href || "").toLowerCase();
                                                if (leadName !== "there" && href.includes(leadName)) return false;
                                            }
                                            
                                            const nameEl = searchContainer.querySelector('.msg-s-message-group__name');
                                            if (nameEl) {
                                                const nameText = (nameEl.innerText || "").trim().toLowerCase();
                                                if (leadName !== "there" && nameText && (nameText.includes(leadName) || leadFull.includes(nameText))) return false;
                                            }
                                            
                                            const imgEl = searchContainer.querySelector('.msg-s-message-group__profile-link img');
                                            if (imgEl) {
                                                const altText = (imgEl.alt || "").toLowerCase();
                                                if (leadName !== "there" && altText.includes(leadName)) return false;
                                            }
                                            
                                            if (profileLinks.length === 0) return true;
                                            
                                            const receipt = el.querySelector('.msg-s-event-listitem__seen-receipt, li-icon[type^="status-"], li-icon[type="check"]');
                                            if (receipt) return true;
                                            
                                            return false; // Default to lead
                                        }""", {"leadName": current_lead_name, "leadFull": lead_full_name})
                                    except: pass
                                    
                                    if not is_me:
                                        acc_state.add_log("Lead replied immediately! Continuing chat...", "success")
                                        continue # Loop back to top of while True to extract and reply again!
                                        
                                # No immediate reply, move on to the next thread
                                break
                            else:
                                editor.press("Enter") # fallback
                                time.sleep(2)
                                acc_state.add_log("Reply sent successfully via Enter!", "success")

                                chat_history.append({"role": "assistant", "content": reply_text})
                                save_chat_history_to_db(account_id, current_lead_name, thread_url, chat_history)
                                
                                reply_state[account_id][msg_hash] = True
                                if handoff_triggered:
                                    reply_state[account_id].setdefault("muted_threads", []).append(thread_url)
                                    acc_state.add_log("Sending chat history to meeting team via email...", "info")
                                    send_handoff_email(current_lead_name, thread_url, chat_history)
                                save_reply_state(reply_state)
                                
                                if handoff_triggered:
                                    break
                                    
                                # Wait 12 seconds to see if they reply immediately
                                acc_state.add_log("Waiting 12 seconds to see if the lead replies immediately...", "info")
                                for _ in range(12):
                                    if acc_state.stop_requested: break
                                    time.sleep(1)
                                    
                                if acc_state.stop_requested: break
                                
                                # Re-check messages
                                new_message_elements = page.locator(".msg-s-event-listitem").all()
                                if new_message_elements:
                                    msg_el = new_message_elements[-1]
                                    sender_name_el = msg_el.locator(".msg-s-message-group__name").first
                                    
                                    is_me = False
                                    
                                    # Bulletproof sender verification via native JS DOM traversal (100% reliable)
                                    try:
                                        is_me = msg_el.evaluate("""(el, args) => {
                                            const group = el.closest('.msg-s-message-group');
                                            const searchContainer = group || el;
                                            
                                            if (searchContainer.classList.contains('msg-s-message-group--me') || 
                                                searchContainer.classList.contains('msg-s-message-group--profile-viewer') ||
                                                el.classList.contains('msg-s-event-listitem--me')) {
                                                return true;
                                            }
                                            
                                            const leadName = (args.leadName || "").toLowerCase();
                                            const leadFull = (args.leadFull || "").toLowerCase();
                                            
                                            const profileLinks = Array.from(searchContainer.querySelectorAll('.msg-s-message-group__profile-link'));
                                            for (const a of profileLinks) {
                                                const href = (a.href || "").toLowerCase();
                                                if (leadName !== "there" && href.includes(leadName)) return false;
                                            }
                                            
                                            const nameEl = searchContainer.querySelector('.msg-s-message-group__name');
                                            if (nameEl) {
                                                const nameText = (nameEl.innerText || "").trim().toLowerCase();
                                                if (leadName !== "there" && nameText && (nameText.includes(leadName) || leadFull.includes(nameText))) return false;
                                            }
                                            
                                            const imgEl = searchContainer.querySelector('.msg-s-message-group__profile-link img');
                                            if (imgEl) {
                                                const altText = (imgEl.alt || "").toLowerCase();
                                                if (leadName !== "there" && altText.includes(leadName)) return false;
                                            }
                                            
                                            if (profileLinks.length === 0) return true;
                                            
                                            const receipt = el.querySelector('.msg-s-event-listitem__seen-receipt, li-icon[type^="status-"], li-icon[type="check"]');
                                            if (receipt) return true;
                                            
                                            return false; // Default to lead
                                        }""", {"leadName": current_lead_name, "leadFull": lead_full_name})
                                    except: pass
                                    
                                    if not is_me:
                                        acc_state.add_log("Lead replied immediately! Continuing chat...", "success")
                                        continue # Loop back to top of while True to extract and reply again!
                                        
                                break # Next thread
                        else:
                            acc_state.add_log("Message editor not found. LinkedIn UI might have changed.", "warning")
                            break
                            
                except Exception as ex:
                    acc_state.add_log(f"Error processing thread: {str(ex)}", "warning")
                    
                time.sleep(2) # Delay between threads
                    
            if acc_state.stop_requested:
                break
                
            acc_state.add_log("Sweep complete. Waiting 20 seconds before checking for new messages...", "success")
            for _ in range(20):
                if acc_state.stop_requested: break
                time.sleep(1)

    except Exception as e:
        acc_state.add_log(f"Auto-responder error: {str(e)}", "error")
    finally:
        acc_state.update_status(action="Idle", progress=0)
        acc_state.is_running = False
        acc_state.add_log("Auto-Responder finished. Browser tab left open as requested.", "info")
        # Do NOT close browser until human manually closes it
        # if context:
        #     try: context.close()
        #     except: pass
        # if pw:
        #     try: pw.stop()
        #     except: pass

def start_auto_responder(account_id, api_key):
    acc_state = get_account_state(account_id)
    if acc_state.is_running:
        return False
    acc_state.is_running = True
    threading.Thread(target=run_auto_reply_worker_sync, args=(account_id, api_key), daemon=True).start()
    return True
