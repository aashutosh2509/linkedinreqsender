import requests
import os

cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookie.txt")
with open(cookie_path, "r", encoding="utf-8") as f:
    li_at = f.read().strip()

cookies = {"li_at": li_at}
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

response = requests.get("https://www.linkedin.com/feed/", cookies=cookies, headers=headers, allow_redirects=False)

if response.status_code == 200:
    print("SUCCESS: Cookie is VALID and working!")
elif response.status_code == 302 and "login" in response.headers.get("Location", ""):
    print("FAILED: Cookie is EXPIRED or INVALID. LinkedIn redirected to login.")
else:
    print(f"UNKNOWN: Status {response.status_code}")
