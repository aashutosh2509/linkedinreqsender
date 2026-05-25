with open("public/app.js", "r", encoding="utf-8") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "function quickCreateAndLoginAccount" in line or "quickCreateAndLoginAccount" in line:
        print(f"Line {i+1}: {line.strip()}")
        # print next 30 lines
        for j in range(i+1, min(i+40, len(lines))):
            print(f"  Line {j+1}: {lines[j].strip()}")
