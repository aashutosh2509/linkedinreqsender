import os

log_path = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c\.system_generated\tasks\task-4601.log"
if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    print(f"Total lines in current active server log: {len(lines)}")
    # Print last 200 lines safely
    start_line = max(0, len(lines) - 200)
    for idx in range(start_line, len(lines)):
        cleaned_line = lines[idx].strip().encode('ascii', errors='replace').decode('ascii')
        print(f"Line {idx+1}: {cleaned_line}")
else:
    print("Active server log not found.")
