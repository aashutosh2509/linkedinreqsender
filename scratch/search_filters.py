with open("automation.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "status" in line and ("filter" in line or "==" in line or "not in" in line or "pending" in line or "db_data" in line):
        if "def " in lines[max(0, i-5):i+1]:
            continue
        print(f"Line {i+1}: {line.strip()}")
