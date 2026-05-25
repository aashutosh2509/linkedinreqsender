import os
import sys
import time
from playwright.sync_api import sync_playwright

# Reconfigure stdout to support unicode on Windows terminal
try:
    sys.stdout.reconfigure(encoding='utf-8')
except:
    pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import automation

class MockAccState:
    def __init__(self):
        self.stop_requested = False
    def add_log(self, msg, level="info"):
        print(f"[Mock Log] [{level.upper()}] {msg}")

def main():
    account_id = "profile_2_9950"
    profile_username = "shrikant-mate-90422b3a2"
    user_data_dir = os.path.join(automation.BASE_USER_DATA_DIR, account_id)
    
    print(f"Launching persistent browser context for: {account_id}")
    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            page = context.new_page()
            
            profile_url = f"https://www.linkedin.com/in/{profile_username}/"
            print(f"Navigating to: {profile_url}")
            page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            
            # Wait for h1 name to appear
            try:
                page.locator("main section h1, main section h2").first.wait_for(state="visible", timeout=8000)
            except:
                pass
                
            print("\n--- Inspecting Top Card DOM elements ---")
            top_card_html = page.evaluate("""
                () => {
                    const topCard = document.querySelector('main section h1')?.closest('section') || document.querySelector('main section') || document.body;
                    
                    const spans = Array.from(topCard.querySelectorAll('span, div, button, a'));
                    const spanTexts = spans.map(el => {
                        if (!el.offsetHeight && !el.offsetWidth) return null;
                        return { tag: el.tagName, text: el.textContent.trim(), class: el.className };
                    }).filter(x => x && x.text);
                    
                    const buttons = Array.from(topCard.querySelectorAll('button, a'));
                    const btnTexts = buttons.map(el => {
                        if (!el.offsetHeight && !el.offsetWidth) return null;
                        return {
                            tag: el.tagName,
                            text: el.textContent.trim(),
                            aria: el.getAttribute('aria-label') || '',
                            href: el.getAttribute('href') || '',
                            class: el.className
                        };
                    }).filter(x => x);
                    
                    return {
                        html_tag: topCard.tagName,
                        html_class: topCard.className,
                        spanTexts: spanTexts.slice(0, 100),
                        btnTexts: btnTexts
                    };
                }
            """)
            
            print(f"Top Card container tag: {top_card_html['html_tag']} class: {top_card_html['html_class']}")
            print("\nSpans texts (visible):")
            for idx, item in enumerate(top_card_html['spanTexts']):
                print(f"  [{idx}] <{item['tag']}> class='{item['class']}': '{item['text']}'")
                
            print("\nButtons and Links:")
            for idx, item in enumerate(top_card_html['btnTexts']):
                print(f"  [{idx}] <{item['tag']}> href='{item['href']}' aria='{item['aria']}' class='{item['class']}': '{item['text']}'")
                
            # Now call verify_profile_status and print result
            print("\nRunning verification...")
            acc_state = MockAccState()
            res = automation.verify_profile_status(page, profile_username, acc_state)
            print(f"\nverify_profile_status returned: '{res}'")
            
            context.close()
        except Exception as e:
            print(f"Error occurred: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
