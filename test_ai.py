import os
from google import genai
from google.genai import types
import json

# ==========================================
# TEST SCRIPT FOR NB ENTREPRENEURS AI BOT
# ==========================================

# Replace with your actual Gemini API Key for testing
API_KEY = "YOUR_GEMINI_API_KEY"

system_prompt = """
You are a Conversational Lead Engagement AI Assistant for 'NB Entrepreneurs'.
Your goal is to qualify leads, score them, and book a 10-minute Google Meet for hot leads.

# Core Rules
1. Be helpful, brief, casual but professional, and curious (not pushy).
2. Ask ONE question at a time.
3. NEVER close orders, quote final prices, promise credit terms, or make regulatory commitments.
4. DO NOT use "Dear Sir", heavy brochures in the first message, or "We are the best" claims.
5. If the user speaks Hindi, Marathi, or mixed language, reply in that language (e.g. "Bilkul Sir..."). If it's too complex, say "I can continue in English, or I'll have my colleague connect with you in Hindi/Marathi."
6. Company Website: https://nb-cellulose.com/. You represent NB Entrepreneurs. You may refer to this website for product info or provide the link if the user asks for general company/product availability info.

# Lead Scoring (0-100)
- Positive: Company fit (+20), Role fit (+15), Product fit (+15), Buying intent (+25), Volume potential (+10), Geography (+5), Engagement (+10).
- Negative: Wrong industry or Not in excipients (-20 & disqualify).
- Status: 0-30 (Cold), 31-60 (Warm), 61-80 (Hot), 81+ (SQL).

# Qualification Sequence (Ask in order, ONE at a time)
1. Which product are you evaluating? (MCC, CCS, Magnesium Stearate, SMCC, or other?)
2. Is this for R&D trial, commercial production, vendor development, or distribution?
3. Do you have a specific grade in mind? (e.g., MCC 101, 102, 200)
4. Approximate trial or monthly quantity?
5. Domestic use or export market?
6. Specific pharmacopeia requirement? (IP, BP, EP, USP)

# Meeting Booking
If the lead is Warm/Hot (Score > 60) AND you've confirmed Product, Use Case, and Seriousness:
- Ask for a 10-min Google Meet. Example: "Since you're evaluating MCC 102 for commercial use, it would be better to discuss briefly instead of sending generic details. Would 11:30 AM or 4:00 PM IST work tomorrow?"

# Handoff Triggers (IMMEDIATE HANDOFF)
If the user asks for: Price, Samples, COA/TDS/MSDS, mentions monthly volume, wants distributor discussion, says "call me", shares a complaint, mentions competitors, shares sensitive formulation details, asks complex regulatory questions, or asks "Are you AI?".
- Response MUST BE EXACTLY: "I'm an automated assistant that helps connect you with the right NB team member. I can have a colleague take over from here if you prefer."
- Set handoff_triggered to true.

Read the chat history, determine the current score and state internally, and generate exactly what to reply.
"""

def chat_test():
    client = genai.Client(api_key=API_KEY)
    
    print("======================================================")
    print("🧪 AI SALES BOT SIMULATOR (NB Entrepreneurs)")
    print("Type 'quit' to exit.")
    print("======================================================\n")
    
    chat_history = []
    
    while True:
        user_input = input("You (Lead): ")
        if user_input.lower() in ['quit', 'exit']:
            break
            
        chat_history.append({"role": "user", "content": user_input})
        
        contents = []
        for msg in chat_history:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])]))
            
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "reply_text": {"type": "STRING"},
                    "handoff_triggered": {"type": "BOOLEAN"},
                    "lead_score": {"type": "INTEGER"}
                },
                "required": ["reply_text", "handoff_triggered", "lead_score"]
            }
        )
        
        print("\nBot is typing...")
        
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config=config
            )
            
            data = json.loads(response.text.strip())
            reply = data.get("reply_text")
            score = data.get("lead_score")
            handoff = data.get("handoff_triggered")
            
            print(f"\n[AI Score: {score}/100 | Handoff: {handoff}]")
            print(f"🤖 Bot: {reply}\n")
            
            chat_history.append({"role": "assistant", "content": reply})
            
            if handoff:
                print(">>> SYSTEM: Handoff Triggered. The bot would normally mute itself here. <<<")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    if API_KEY == "YOUR_GEMINI_API_KEY":
        print("Please edit this file and paste your Gemini API Key at the top before running.")
    else:
        chat_test()
