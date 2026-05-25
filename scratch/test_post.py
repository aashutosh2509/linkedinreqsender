import urllib.request
import json
import urllib.error

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
        print("Success!")
        print("Code:", res.getcode())
        print("Body:", res.read().decode("utf-8"))
except urllib.error.HTTPError as e:
    print("HTTPError!")
    print("Code:", e.code)
    print("Body:", e.read().decode("utf-8"))
except Exception as e:
    print("General Exception:", str(e))
