import os

log_path = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c\.system_generated\tasks\task-4601.log"
if os.path.exists(log_path):
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    print("Searching for Abhay's execution lines:")
    found = False
    for i, line in enumerate(lines):
        if "abhay" in line.lower() or "sr. no. 18" in line.lower():
            # Print 10 lines before and 25 lines after
            start = max(0, i-5)
            end = min(len(lines), i+30)
            print(f"\n--- MATCH AT LINE {i+1} ---")
            for idx in range(start, end):
                cleaned_line = lines[idx].strip().encode('ascii', errors='replace').decode('ascii')
                print(f"  {idx+1}: {cleaned_line}")
            found = True
            break
    if not found:
        print("No execution lines found in current active log.")
else:
    print("Active server log not found.")
