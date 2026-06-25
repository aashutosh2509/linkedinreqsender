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

# Pacing & Lead Objectives (CRITICAL)
- Single-Topic Rule: You must ONLY talk about "Industry News" or "Market Trends" during this conversation. DO NOT bring up hobbies, travels, sports, or anything else today.
- Fast Track: IF the lead replies warmly or shows interest in talking about the industry, transition to business early (after just 2-3 messages) by asking if they happen to use any excipient solutions for their formulations.
- Cold Lead Assessment: Do NOT assume a short 1-word reply (like 'ok' or 'yes') automatically means they are a cold lead. Look at the context! They might just be agreeing with you or acknowledging your message. If they are actually engaging, continue the conversation or ask a follow-up qualification question.
- Cold Lead Nurturing Protocol (CRITICAL RULE): ONLY IF the lead is genuinely cold, dismissive, or shows absolutely no interest in engaging further, politely end the conversation (e.g., "Great to hear! Wishing you a productive week ahead.") and set `requires_reply` to FALSE. We will nurture them again after a few days with a different topic. NEVER drag out a dead conversation.
- Ultimate Goal: This is a B2B sales automation. Your ultimate, final objective is to qualify the lead for excipient sales and book a meeting for the sales team.
- Warm Lead: Once they show interest or mention formulations, move them through the Qualification Flow below.
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

# Disqualification, Rejections & Irrelevant Content (CRITICAL - READ CAREFULLY)
- ABSOLUTE RULE: If the lead explicitly says they are NOT interested, do not need your products, or tells you to stop messaging: YOU MUST IMMEDIATELY STOP ALL SALES ATTEMPTS. 
- DO NOT mention samples, DO NOT mention pricing, DO NOT ask for a meeting, and DO NOT ask any more qualification questions.
- Your ONLY response should be a polite, 1-sentence acknowledgment (e.g., "No problem at all, thank you for your time!"). 
- IMPORTANT: When sending this polite acknowledgment, you MUST set `requires_reply` to TRUE so the message actually gets sent to them!
- Emotional/Irrelevant Content: If the lead's message is venting about a personal issue, a toxic workplace, politics, or something highly emotional and unrelated to business, DO NOT try to pivot to sales. Show brief, polite empathy (e.g., "I'm sorry to hear you went through that. Wishing you the best.") and set `requires_reply` to FALSE to end the conversation.
- Inappropriate Behavior: Firmly but professionally deflect any romantic/unprofessional messages. If they persist, set `requires_reply` to false.

# Ignoring End-of-Conversation Messages (CRITICAL)
- Set `requires_reply` to FALSE ONLY IF:
  1. The lead's last message is just a conversational ender (like "thank you", "ok", "got it"), AND you are already deep into a conversation.
  2. Or if YOU already sent the polite rejection acknowledgment in the previous message, and the lead replied again with something that doesn't need an answer.
- CRITICAL EXCEPTION: If the lead's message is literally their FIRST message ever (e.g., "Thanks for connecting!"), DO NOT ignore it! You must set `requires_reply` to TRUE and immediately ask your first qualification question to start the conversation!

# Meeting Booking & Handoff Triggers (CRITICAL 2-STEP PROCESS)
- ONLY apply this if the lead is POSITIVE and INTERESTED.
- YOUR ULTIMATE MOTTO IS TO BOOK A 10-MINUTE QUICK MEETING. Once the lead has answered your qualification questions, OR if they actively ask for Price, Samples, COA/TDS/MSDS, mention volume, or want to discuss business:
- Step 1 (Ask for time): Immediately ask them what time works for a quick 10-minute Google Meet to discuss further.
- Step 2 (Send Link): Once they give a time, give the link: https://calendar.app.google/pt5oudMGhUwwFjeH8
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
                "requires_reply": {"type": "BOOLEAN", "description": "Set to true normally. Set to false if the user just said 'thanks' or 'ok' and no reply is needed."}
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
        return data.get("reply_text", "I'll have a colleague connect with you shortly."), data.get("handoff_triggered", False), data.get("lead_score", 0), data.get("requires_reply", True)
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
                    break
                time.sleep(5)
                continue
                
            threads = page.locator(".msg-conversation-listitem").all()
            # Scan top 10 recent threads
            for i, thread in enumerate(threads[:10]):
                if acc_state.stop_requested:
                    break
                    
                try:
                    # Skip sponsored ads
                    thread_text = thread.inner_text().strip()
                    if "Sponsored" in thread_text:
                        acc_state.add_log("Skipping Sponsored Ad thread...", "info")
                        continue
                        
                    # Extract lead name from thread snippet before clicking
                    current_lead_name = "there"
                    try:
                        name_el = thread.locator(".msg-conversation-listitem__participant-names").first
                        if name_el.is_visible():
                            # Extract first name, stripping common prefixes
                            full_name = name_el.inner_text().strip()
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
                    
                    # Click the thread to open it
                    thread.click()
                    time.sleep(3) # Wait for chat history to load
                    
                    while True:
                        if acc_state.stop_requested:
                            break
                            
                        thread_url = page.url
                        if thread_url in muted_threads:
                            acc_state.add_log(f"Skipping muted thread (Human Handoff): {thread_url}", "info")
                            break
                        
                        # Extract messages
                        # Messages are usually inside .msg-s-message-list-container
                        message_elements = page.locator(".msg-s-event-listitem").all()
                        
                        chat_history = []
                        last_sender_name = None
                        last_message_text = None
                        
                        for msg_el in message_elements[-10:]: # Look at last 10 messages for better context
                            # Try to find sender name
                            sender_name_el = msg_el.locator(".msg-s-message-group__name").first
                            text_el = msg_el.locator(".msg-s-event-listitem__body").first
                            
                            if text_el.is_visible():
                                text = text_el.inner_text().strip()
                                if sender_name_el.is_visible():
                                    last_sender_name = sender_name_el.inner_text().strip()
                                
                                is_me = False
                                
                                # Primary check: If the sender name is not the lead's name, it's us.
                                if last_sender_name and current_lead_name != "there" and current_lead_name.lower() not in last_sender_name.lower():
                                    is_me = True
                                    
                                # Secondary fallback check: LinkedIn DOM classes
                                try:
                                    # Safely find the parent message group to check if we are the sender
                                    group_el = msg_el.locator("xpath=ancestor::div[contains(@class, 'msg-s-message-group')]").first
                                    if group_el.is_visible():
                                        class_str = group_el.get_attribute("class") or ""
                                        if "msg-s-message-group--profile-viewer" in class_str:
                                            is_me = True
                                except:
                                    pass
                                    
                                role = "assistant" if is_me else "user"
                                chat_history.append({"role": role, "content": text})
                                if not is_me:
                                    last_message_text = text
                                    
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
                                    if sender_name_el.is_visible():
                                        new_sender = sender_name_el.inner_text().strip()
                                        if current_lead_name != "there" and current_lead_name.lower() not in new_sender.lower():
                                            is_me = True
                                    try:
                                        group_el = msg_el.locator("xpath=ancestor::div[contains(@class, 'msg-s-message-group')]").first
                                        if group_el.is_visible() and "msg-s-message-group--profile-viewer" in (group_el.get_attribute("class") or ""):
                                            is_me = True
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
                                    if sender_name_el.is_visible():
                                        new_sender = sender_name_el.inner_text().strip()
                                        if current_lead_name != "there" and current_lead_name.lower() not in new_sender.lower():
                                            is_me = True
                                    try:
                                        group_el = msg_el.locator("xpath=ancestor::div[contains(@class, 'msg-s-message-group')]").first
                                        if group_el.is_visible() and "msg-s-message-group--profile-viewer" in (group_el.get_attribute("class") or ""):
                                            is_me = True
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
