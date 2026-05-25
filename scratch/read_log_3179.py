import os

log_path = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c\.system_generated\tasks\task-3179.log"
print(f"Log path: {log_path}")
print(f"Exists: {os.path.exists(log_path)}")
if os.path.exists(log_path):
    print(f"Size: {os.path.getsize(log_path)} bytes")
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        print(f.read())
else:
    # Try to find all log files in tasks folder starting with task-317
    tasks_dir = os.path.dirname(log_path)
    if os.path.exists(tasks_dir):
        files = os.listdir(tasks_dir)
        print("Files in tasks dir matching task-317*:")
        for f in files:
            if f.startswith("task-317"):
                print(f"  {f} ({os.path.getsize(os.path.join(tasks_dir, f))} bytes)")
