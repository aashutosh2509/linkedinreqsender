import urllib.request
import json

url = "http://127.0.0.1:5000/api/sync-acceptance"
data = json.dumps({"account_id": "default"}).encode("utf-8")

req = urllib.request.Request(
    url,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST"
)

try:
    with urllib.request.urlopen(req) as res:
        response = res.read().decode("utf-8")
        print("Trigger Sync Response:", response)
except Exception as e:
    print("Error triggering sync:", str(e))
