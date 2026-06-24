import automation
import time
import os

print("Testing Playwright cookie injection...")
print(f"Cookie in file: {os.path.exists('cookie.txt')}")

res = automation.test_login_session("ashu")
print(f"Result of test_login_session: {res}")
