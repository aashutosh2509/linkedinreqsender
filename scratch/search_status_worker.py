with open("automation.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "status" in line and ("=" in line or "contact" in line) and 1000 <= i <= 1550:
        print(f"Line {i+1}: {line.strip()}")
