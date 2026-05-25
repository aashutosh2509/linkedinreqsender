with open("automation.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "def open_linkedin_for_login" in line or "open_linkedin_for_login" in line:
        print(f"Line {i+1}: {line.strip()}")
        # print next 20 lines
        for j in range(i+1, min(i+40, len(lines))):
            print(f"  Line {j+1}: {lines[j].strip()}")
