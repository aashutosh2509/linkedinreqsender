import os

log_path = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c\.system_generated\tasks\task-4586.log"
if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    print(f"Total lines in task-4586 log: {len(lines)}")
    found = False
    for i, line in enumerate(lines):
        if "abhay" in line.lower() or "connected" in line.lower() or "first degree" in line.lower() or "pending" in line.lower() or "processing" in line.lower() or "navigating" in line.lower():
            cleaned_line = line.strip().encode('ascii', errors='replace').decode('ascii')
            print(f"Line {i+1}: {cleaned_line}")
            found = True
    if not found:
        print("No matches found in task-4586 log.")
else:
    print("Log file task-4586.log not found.")
