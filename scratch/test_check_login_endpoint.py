import urllib.request
import urllib.error
import json

URL = "http://127.0.0.1:5000/api/accounts/check-login"
payload = json.dumps({"account_id": "default"}).encode("utf-8")

req = urllib.request.Request(
    URL,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    print("Sending POST request to check-login endpoint via urllib...")
    with urllib.request.urlopen(req, timeout=30) as response:
        status_code = response.getcode()
        body = response.read().decode("utf-8")
        print(f"Status Code: {status_code}")
        print(f"Response: {json.dumps(json.loads(body), indent=4)}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
except Exception as e:
    print(f"Request failed: {str(e)}")
