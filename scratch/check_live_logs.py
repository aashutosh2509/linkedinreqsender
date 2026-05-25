import urllib.request
import json

url = "http://127.0.0.1:5000/api/state?account_id=default"

try:
    with urllib.request.urlopen(url) as res:
        state = json.loads(res.read().decode("utf-8"))
        print(f"Status: {state.get('is_running')} | Action: {state.get('current_action')} | Progress: {state.get('progress_percent')}%")
        print("\nCaptured Logs:")
        for log in state.get("logs", []):
            print(f"[{log['time']}] [{log['type'].upper()}] {log['message']}")
except Exception as e:
    print("Error fetching state:", str(e))
