import os

log_path = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c\.system_generated\tasks\task-4370.log"
if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    print(f"Total log lines: {len(lines)}")
    found = False
    for i, line in enumerate(lines):
        if "Harshit" in line or "Saxena" in line or "harshit" in line or "saxena" in line:
            print(f"Line {i+1}: {line.strip()}")
            found = True
    if not found:
        print("No log lines found containing Harshit Saxena.")
else:
    print("Log file not found.")
