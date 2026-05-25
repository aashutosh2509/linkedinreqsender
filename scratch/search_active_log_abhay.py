import os

log_path = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c\.system_generated\tasks\task-4601.log"
if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    print(f"Total lines in current active server log: {len(lines)}")
    found = False
    for i, line in enumerate(lines):
        if "abhay" in line.lower() or "pending" in line.lower() or "connected" in line.lower() or "processing" in line.lower():
            cleaned_line = line.strip().encode('ascii', errors='replace').decode('ascii')
            # Print matching lines with timestamp context
            print(f"Line {i+1}: {cleaned_line}")
            found = True
    if not found:
        print("No matches found in active server log.")
else:
    print("Active server log not found.")
