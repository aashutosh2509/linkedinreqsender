with open("automation.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "status" in line and ('"Pending"' in line or "'Pending'" in line) and "worker" in "".join(lines[max(0, i-50):i]):
        print(f"Line {i+1}: {line.strip()}")
