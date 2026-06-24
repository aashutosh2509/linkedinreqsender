import re

with open("public/app.js", "r", encoding="utf-8") as f:
    js_content = f.read()

# 1. Add variable declaration at the top
var_declaration = "const btnStartMessaging = document.getElementById(\"btn-start-messaging\");\n"
if "btnStartMessaging" not in js_content:
    js_content = js_content.replace(
        'const btnSync = document.getElementById("btn-sync");',
        'const btnSync = document.getElementById("btn-sync");\n' + var_declaration
    )

# 2. Add event listener
listener = "btnStartMessaging.addEventListener(\"click\", startMessagingCampaign);\n"
if "btnStartMessaging.addEventListener" not in js_content:
    js_content = js_content.replace(
        'btnSync.addEventListener("click", syncAcceptedRequests);',
        'btnSync.addEventListener("click", syncAcceptedRequests);\n    ' + listener
    )

# 3. Add startMessagingCampaign function definition
func_def = """
async function startMessagingCampaign() {
    if (currentAccountId === "admin") return;
    
    const minDelay = parseInt(delayMinInput.value) || 30;
    const maxDelay = parseInt(delayMaxInput.value) || 70;
    
    if (btnStartMessaging) btnStartMessaging.disabled = true;
    appendLogToConsole("Queueing messaging campaign...", "info");
    
    const payload = {
        account_id: currentAccountId,
        template: noteTemplateTextarea.value,
        delay_min: minDelay,
        delay_max: maxDelay
    };
    
    try {
        const response = await fetch(`${API_BASE}/start-messaging`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        
        if (res.status === "success") {
            appendLogToConsole("Messaging sequence task added to queue.", "success");
            await fetchWorkspaceState();
        } else {
            appendLogToConsole(`Failed dispatching messaging: ${res.error}`, "error");
            if (btnStartMessaging) btnStartMessaging.disabled = false;
        }
    } catch (e) {
        appendLogToConsole("Network connection error running messaging.", "error");
        if (btnStartMessaging) btnStartMessaging.disabled = false;
    }
}
"""

if "startMessagingCampaign()" not in js_content:
    js_content = js_content.replace(
        'async function syncAcceptedRequests() {',
        func_def + '\nasync function syncAcceptedRequests() {'
    )

with open("public/app.js", "w", encoding="utf-8") as f:
    f.write(js_content)

print("Frontend JS updated.")
