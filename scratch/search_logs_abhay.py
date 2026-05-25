import os
import glob

# Search in all task logs
log_pattern = r"C:\Users\lenovo\.gemini\antigravity\brain\eeb3f292-7445-4086-bb03-812d2a3c527c\.system_generated\tasks\task-*.log"
log_files = glob.glob(log_pattern)
print(f"Found {len(log_files)} log files to search.")

for log_path in log_files:
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if "abhay" in line.lower():
                if not found:
                    print(f"\n--- In File: {os.path.basename(log_path)} ---")
                    found = True
                cleaned_line = line.strip().encode('ascii', errors='replace').decode('ascii')
                print(f"  Line {i+1}: {cleaned_line}")
