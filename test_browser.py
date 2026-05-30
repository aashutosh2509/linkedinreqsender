import sys
import os

# Add the directory to sys.path so we can import automation
sys.path.insert(0, r"c:\linkedineq\linkedinreqsender")

import automation

print("Testing launch_browser...")
try:
    playwright, context = automation.launch_browser("default", headed=True)
    page = context.new_page()
    page.goto("https://www.linkedin.com/login")
    print("Browser launched successfully and navigated to LinkedIn!")
    print("Page Title:", page.title())
    context.close()
    playwright.stop()
except Exception as e:
    print(f"FAILED TO LAUNCH: {str(e)}")
