from playwright.sync_api import sync_playwright
import os

with open("cookie.txt", "r") as f:
    li_at = f.read().strip()

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=os.path.join(os.getcwd(), "test_profile_2"),
        headless=False,
        args=["--headless=new", "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    context.add_cookies([{
        "name": "li_at",
        "value": li_at,
        "domain": ".linkedin.com",
        "path": "/",
        "secure": True,
        "httpOnly": True,
        "sameSite": "None"
    }])
    page = context.new_page()
    try:
        response = page.goto("https://www.linkedin.com/feed/", wait_until="commit")
        print(f"Status: {response.status if response else 'None'}")
        print(f"URL: {page.url}")
    except Exception as e:
        print(f"Error: {e}")
    context.close()
