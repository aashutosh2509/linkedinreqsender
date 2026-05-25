// ==========================================================================
// LINKCONNECT FRONTEND CONTROLLER (app.js)
// Handles API integration, polling, drag-drop excel loading, and reactive UI
// ==========================================================================

const API_BASE = "http://127.0.0.1:5000/api";

// UI Elements
const systemStatusDot = document.getElementById("system-status-dot");
const systemStatusText = document.getElementById("system-status-text");

const btnLaunchLogin = document.getElementById("btn-launch-login");
const excelDropZone = document.getElementById("excel-drop-zone");
const excelFileInput = document.getElementById("excel-file-input");

const quickUrlInput = document.getElementById("quick-url-input");
const quickNameInput = document.getElementById("quick-name-input");
const btnQuickAdd = document.getElementById("btn-quick-add");


const delayMinInput = document.getElementById("delay-min");
const delayMaxInput = document.getElementById("delay-max");
const dailyLimitInput = document.getElementById("daily-limit");

// Selective Send Range & Date Filter Elements
const rangeStartInput = document.getElementById("range-start");
const rangeEndInput = document.getElementById("range-end");
const dateFilterSelect = document.getElementById("date-filter");
const customDateContainer = document.getElementById("custom-date-container");
const customStartDateInput = document.getElementById("custom-start-date");
const customEndDateInput = document.getElementById("custom-end-date");
const btnApplyDate = document.getElementById("btn-apply-date");
const btnClearDate = document.getElementById("btn-clear-date");

const sendWithNoteCheckbox = document.getElementById("send-with-note");
const noteTemplateContainer = document.getElementById("note-template-container");
const noteTemplateTextarea = document.getElementById("note-template");
const charCountSpan = document.getElementById("char-count");
const tagBadges = document.querySelectorAll(".tag-badge");

const btnStart = document.getElementById("btn-start");
const btnStop = document.getElementById("btn-stop");
const btnSync = document.getElementById("btn-sync");
const btnClearLogs = document.getElementById("btn-clear-logs");
const consoleOutput = document.getElementById("console-output");

const statTotal = document.getElementById("stat-total");
const statSent = document.getElementById("stat-sent");
const statPending = document.getElementById("stat-pending");
const statConnected = document.getElementById("stat-connected");

const quotaCurrent = document.getElementById("quota-current");
const quotaMax = document.getElementById("quota-max");
const quotaBar = document.getElementById("quota-bar");

const contactsCountSpan = document.getElementById("contacts-count");
const tableSearchInput = document.getElementById("table-search");
const statusFilterSelect = document.getElementById("status-filter");
const btnResetContacts = document.getElementById("btn-reset-contacts");
const btnClearDb = document.getElementById("btn-clear-db");
const tableBody = document.getElementById("table-body");

// Global Application State
let localContacts = [];
let localLogs = [];
let isSystemRunning = false;
let pollingInterval = null;

// Initial Setup
document.addEventListener("DOMContentLoaded", () => {
    // Render initial Lucide Icons
    lucide.createIcons();
    
    // Load initial data
    fetchContacts();
    fetchSystemState();
    
    // Start standard background status loop (every 5 seconds)
    startPolling(5000);
    
    // Setup listeners
    setupEventListeners();
});

// Setup Events
function setupEventListeners() {
    // Launch browser button
    btnLaunchLogin.addEventListener("click", launchLoginBrowser);
    
    // Quick Add Single Profile
    btnQuickAdd.addEventListener("click", addSingleContact);
    
    // File inputs
    excelDropZone.addEventListener("click", () => excelFileInput.click());

    excelFileInput.addEventListener("change", handleFileSelect);
    
    // Drag & Drop visual states
    ['dragenter', 'dragover'].forEach(eventName => {
        excelDropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            excelDropZone.classList.add('dragover');
        }, false);
    });
    ['dragleave', 'drop'].forEach(eventName => {
        excelDropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            excelDropZone.classList.remove('dragover');
        }, false);
    });
    excelDropZone.addEventListener('drop', handleFileDrop, false);
    
    // Textarea templates character counter
    noteTemplateTextarea.addEventListener("input", updateCharCounter);
    
    // Note toggler
    sendWithNoteCheckbox.addEventListener("change", () => {
        const checked = sendWithNoteCheckbox.checked;
        noteTemplateTextarea.disabled = !checked;
        if (checked) {
            noteTemplateContainer.style.opacity = "1";
            noteTemplateContainer.style.pointerEvents = "auto";
        } else {
            noteTemplateContainer.style.opacity = "0.4";
            noteTemplateContainer.style.pointerEvents = "none";
        }
    });
    
    // Initialize note template state on page load
    const checkedOnInit = sendWithNoteCheckbox.checked;
    noteTemplateTextarea.disabled = !checkedOnInit;
    if (checkedOnInit) {
        noteTemplateContainer.style.opacity = "1";
        noteTemplateContainer.style.pointerEvents = "auto";
    } else {
        noteTemplateContainer.style.opacity = "0.4";
        noteTemplateContainer.style.pointerEvents = "none";
    }
    
    // Add tag to template cursor position
    tagBadges.forEach(badge => {
        badge.addEventListener("click", () => {
            if (noteTemplateTextarea.disabled) return;
            
            const tag = badge.getAttribute("data-tag");
            const startPos = noteTemplateTextarea.selectionStart;
            const endPos = noteTemplateTextarea.selectionEnd;
            const text = noteTemplateTextarea.value;
            
            noteTemplateTextarea.value = text.substring(0, startPos) + tag + text.substring(endPos, text.length);
            
            // Move cursor to after tag
            noteTemplateTextarea.focus();
            noteTemplateTextarea.selectionStart = startPos + tag.length;
            noteTemplateTextarea.selectionEnd = startPos + tag.length;
            
            updateCharCounter();
        });
    });
    
    // Control Buttons
    btnStart.addEventListener("click", startAutomation);
    btnStop.addEventListener("click", stopAutomation);
    btnSync.addEventListener("click", syncAcceptance);
    btnClearLogs.addEventListener("click", clearLogsPanel);
    
    // Database utility buttons
    btnResetContacts.addEventListener("click", resetContactsStatus);
    btnClearDb.addEventListener("click", clearDatabase);
    
    // Table click actions (e.g. Delete contact)
    tableBody.addEventListener("click", handleTableClick);
    
    // Table Search and Filter
    tableSearchInput.addEventListener("input", renderTable);
    statusFilterSelect.addEventListener("change", renderTable);

    // Date filter event listeners
    dateFilterSelect.addEventListener("change", () => {
        if (dateFilterSelect.value === "custom") {
            customDateContainer.style.display = "flex";
        } else {
            customDateContainer.style.display = "none";
            customStartDateInput.value = "";
            customEndDateInput.value = "";
            renderTable();
        }
    });

    btnApplyDate.addEventListener("click", renderTable);
    btnClearDate.addEventListener("click", () => {
        customStartDateInput.value = "";
        customEndDateInput.value = "";
        renderTable();
    });
}

// ==========================================================================
// POLLING ENGINE
// ==========================================================================
function startPolling(ms) {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(() => {
        fetchSystemState();
        fetchContacts();
    }, ms);
}

// ==========================================================================
// API CLIENT CALLS
// ==========================================================================

// Fetch system state (actions, logs, running status)
async function fetchSystemState() {
    try {
        const response = await fetch(`${API_BASE}/state`);
        const state = await response.json();
        
        // Update Running States
        isSystemRunning = state.is_running;
        
        if (isSystemRunning) {
            systemStatusDot.className = "pulse-dot running";
            systemStatusText.textContent = `Running: ${state.current_action}`;
            btnStart.disabled = true;
            btnStop.disabled = false;
            btnLaunchLogin.disabled = true;
            btnSync.disabled = true;
            btnClearDb.disabled = true;
            btnResetContacts.disabled = true;
            excelDropZone.style.pointerEvents = "none";
            excelDropZone.style.opacity = "0.5";
            
            // Speed up polling to 2s for reactive logs
            if (pollingInterval && pollingInterval._idleTimeout !== 2000) {
                startPolling(2000);
            }
        } else {
            systemStatusDot.className = "pulse-dot";
            systemStatusText.textContent = "System Idle";
            // Start button only enabled if there are contacts in the DB
            btnStart.disabled = localContacts.length === 0;
            btnStop.disabled = true;
            btnLaunchLogin.disabled = false;
            btnSync.disabled = false;
            btnClearDb.disabled = false;
            btnResetContacts.disabled = false;
            excelDropZone.style.pointerEvents = "auto";
            excelDropZone.style.opacity = "1";
            
            // Slow down polling to 5s if idle
            if (pollingInterval && pollingInterval._idleTimeout !== 5000) {
                startPolling(5000);
            }
        }
        
        // Append logs
        updateLogsPanel(state.logs);
        
    } catch (error) {
        console.error("Error fetching system state:", error);
    }
}

// Fetch Contacts from JSON DB
async function fetchContacts() {
    try {
        const response = await fetch(`${API_BASE}/contacts`);
        const contacts = await response.json();
        localContacts = contacts;
        
        // Update Stats Counters
        updateStats();
        
        // Refresh Table
        renderTable();
        
        // Toggle Start Button if contacts present
        if (!isSystemRunning) {
            btnStart.disabled = localContacts.length === 0;
        }
    } catch (error) {
        console.error("Error fetching contacts:", error);
    }
}

// Launch Playwright headed session for user to login
async function launchLoginBrowser() {
    btnLaunchLogin.disabled = true;
    appendLogToConsole("Requesting browser launch...", "info");
    try {
        const response = await fetch(`${API_BASE}/launch-login`, { method: "POST" });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole("Browser window spawned! Check your system taskbar.", "success");
            fetchSystemState();
        } else {
            appendLogToConsole(`Failed to launch browser: ${res.error}`, "error");
            btnLaunchLogin.disabled = false;
        }
    } catch (error) {
        appendLogToConsole("Network error while launching browser.", "error");
        btnLaunchLogin.disabled = false;
    }
}

// Start Automation Send Connection Loops
async function startAutomation() {
    const minDelay = parseInt(delayMinInput.value) || 30;
    const maxDelay = parseInt(delayMaxInput.value) || 70;
    const dailyLimit = parseInt(dailyLimitInput.value) || 50;
    
    if (minDelay < 10) {
        alert("For your safety, minimum delay cannot be less than 10 seconds.");
        return;
    }
    if (maxDelay < minDelay) {
        alert("Maximum delay must be greater than or equal to minimum delay.");
        return;
    }

    const startIdxVal = rangeStartInput.value.trim();
    const endIdxVal = rangeEndInput.value.trim();
    
    let startIndex = null;
    let endIndex = null;
    
    if (startIdxVal !== "") {
        startIndex = parseInt(startIdxVal);
        if (isNaN(startIndex) || startIndex < 1) {
            alert("Starting Serial Number must be a positive integer.");
            return;
        }
    }
    
    if (endIdxVal !== "") {
        endIndex = parseInt(endIdxVal);
        if (isNaN(endIndex) || endIndex < 1) {
            alert("Ending Serial Number must be a positive integer.");
            return;
        }
    }
    
    if (startIndex !== null && endIndex !== null && startIndex > endIndex) {
        alert("Starting Serial Number cannot be greater than Ending Serial Number.");
        return;
    }

    btnStart.disabled = true;
    appendLogToConsole("Initiating Connection Request Automation...", "info");
    
    const payload = {
        note_template: noteTemplateTextarea.value,
        send_with_note: sendWithNoteCheckbox.checked,
        delay_min: minDelay,
        delay_max: maxDelay,
        daily_limit: dailyLimit,
        start_index: startIndex,
        end_index: endIndex
    };
    
    try {
        const response = await fetch(`${API_BASE}/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        
        if (res.status === "success") {
            appendLogToConsole("Automation loop active. Launching automation thread...", "success");
            fetchSystemState();
        } else {
            appendLogToConsole(`Failed to start: ${res.error}`, "error");
            btnStart.disabled = false;
            alert(`Error: ${res.error}`);
        }
    } catch (error) {
        appendLogToConsole("Network error while starting automation.", "error");
        btnStart.disabled = false;
    }
}

// Stop/Pause Automation worker safely
async function stopAutomation() {
    appendLogToConsole("Sending stop signal...", "warning");
    try {
        const response = await fetch(`${API_BASE}/stop`, { method: "POST" });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole("Stop signal acknowledged. Pausing execution shortly.", "info");
        }
    } catch (error) {
        appendLogToConsole("Network error stopping automation.", "error");
    }
}

// Run Acceptance Sync
async function syncAcceptance() {
    btnSync.disabled = true;
    appendLogToConsole("Initiating acceptance synchronization...", "info");
    try {
        const response = await fetch(`${API_BASE}/sync-acceptance`, { method: "POST" });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole("Acceptance sync worker dispatched in background.", "info");
            fetchSystemState();
        } else {
            appendLogToConsole(`Sync failed: ${res.error}`, "error");
            btnSync.disabled = false;
        }
    } catch (error) {
        appendLogToConsole("Network error starting sync.", "error");
        btnSync.disabled = false;
    }
}

// Reset Database statuses
async function resetContactsStatus() {
    const scope = confirm("Reset ALL contact statuses to 'Not Started'? (This lets you run automation again from the beginning)") 
        ? "all" 
        : (confirm("Reset only 'Failed' contacts?") ? "failed" : null);
        
    if (!scope) return;
    
    try {
        const response = await fetch(`${API_BASE}/contacts/reset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scope })
        });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole(`Status reset completed successfully (${scope}).`, "success");
            fetchContacts();
        }
    } catch (error) {
        appendLogToConsole("Network error resetting contacts.", "error");
    }
}

// Clear Database completely
async function clearDatabase() {
    if (!confirm("Are you absolutely sure you want to delete ALL contacts? This cannot be undone.")) return;
    
    try {
        const response = await fetch(`${API_BASE}/contacts/clear`, { method: "POST" });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole("Database cleared.", "warning");
            fetchContacts();
        }
    } catch (error) {
        appendLogToConsole("Network error clearing database.", "error");
    }
}

// ==========================================================================
// EXCEL FILE UPLOAD LOGIC
// ==========================================================================
function handleFileDrop(e) {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
        excelFileInput.files = files;
        uploadExcelFile(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadExcelFile(files[0]);
    }
}

async function uploadExcelFile(file) {
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        alert("Invalid file format. Please upload an Excel sheet (.xlsx or .xls).");
        return;
    }
    
    appendLogToConsole(`Uploading spreadsheet: ${file.name}...`, "info");
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        // Change dropzone UI to uploading status
        excelDropZone.classList.add("dragover");
        excelDropZone.querySelector(".drop-zone-text").textContent = "Uploading & parsing sheet...";
        
        const response = await fetch(`${API_BASE}/upload`, {
            method: "POST",
            body: formData
        });
        const res = await response.json();
        
        // Restore dropzone UI
        excelDropZone.classList.remove("dragover");
        excelDropZone.querySelector(".drop-zone-text").textContent = "Drag & drop your Excel file here or click to browse";
        excelFileInput.value = ""; // clear inputs
        
        if (res.status === "success") {
            appendLogToConsole(`Sheet parsed successfully! Added ${res.added_count} new contacts.`, "success");
            alert(`Spreadsheet imported! Added ${res.added_count} contacts.`);
            fetchContacts();
        } else {
            appendLogToConsole(`Import failed: ${res.error}`, "error");
            alert(`Error loading Excel: ${res.error}`);
        }
    } catch (error) {
        appendLogToConsole("Network error uploading Excel file.", "error");
        excelDropZone.classList.remove("dragover");
        excelDropZone.querySelector(".drop-zone-text").textContent = "Drag & drop your Excel file here or click to browse";
    }
}

// ==========================================================================
// REACTIVE METRICS & DATABASE RENDERERS
// ==========================================================================
function updateStats() {
    const total = localContacts.length;
    const pending = localContacts.filter(c => c.status === "Pending").length;
    const connected = localContacts.filter(c => c.status === "Connected").length;
    
    // "Sent" status accounts for Requests Sent which includes pending & connected
    const sent = localContacts.filter(c => ["Sent", "Pending", "Connected"].includes(c.status)).length;
    
    statTotal.textContent = total;
    statSent.textContent = sent;
    statPending.textContent = pending;
    statConnected.textContent = connected;
    
    contactsCountSpan.textContent = `${total} contact${total !== 1 ? 's' : ''}`;
    
    // Daily quota UI calculations
    const limit = parseInt(dailyLimitInput.value) || 50;
    quotaCurrent.textContent = sent;
    quotaMax.textContent = limit;
    
    const quotaPercent = Math.min((sent / limit) * 100, 100);
    quotaBar.style.width = `${quotaPercent}%`;
    
    // Danger colors if approaching close to quota limit
    if (quotaPercent >= 90) {
        quotaBar.style.background = "var(--status-danger)";
    } else if (quotaPercent >= 70) {
        quotaBar.style.background = "var(--status-warning)";
    } else {
        quotaBar.style.background = "linear-gradient(to right, var(--accent-blue), var(--accent-purple))";
    }
}

// Render data table with Search Filters
function renderTable() {
    const query = tableSearchInput.value.toLowerCase().trim();
    const filter = statusFilterSelect.value;
    const dateFilter = dateFilterSelect.value;
    
    let filtered = localContacts;
    
    // Scoped date parser
    function getRowDate(c) {
        const rawDate = c.date_accepted || c.date_sent;
        if (!rawDate) return null;
        const parts = rawDate.split(" ");
        if (!parts[0]) return null;
        const dateParts = parts[0].split("-");
        if (dateParts.length !== 3) return null;
        return new Date(parseInt(dateParts[0]), parseInt(dateParts[1]) - 1, parseInt(dateParts[2]));
    }
    
    // Filter status
    if (filter !== "all") {
        filtered = filtered.filter(c => c.status === filter);
    }
    
    // Filter by Date
    if (dateFilter !== "all") {
        const now = new Date();
        now.setHours(0,0,0,0);
        
        filtered = filtered.filter(c => {
            const rowDate = getRowDate(c);
            if (!rowDate) return false;
            rowDate.setHours(0,0,0,0);
            
            if (dateFilter === "today") {
                return rowDate.toDateString() === now.toDateString();
            } else if (dateFilter === "yesterday") {
                const yesterday = new Date();
                yesterday.setDate(yesterday.getDate() - 1);
                return rowDate.toDateString() === yesterday.toDateString();
            } else if (dateFilter === "week") {
                const sevenDaysAgo = new Date();
                sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
                sevenDaysAgo.setHours(0,0,0,0);
                return rowDate >= sevenDaysAgo;
            } else if (dateFilter === "month") {
                const thirtyDaysAgo = new Date();
                thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
                thirtyDaysAgo.setHours(0,0,0,0);
                return rowDate >= thirtyDaysAgo;
            } else if (dateFilter === "custom") {
                const startDateVal = customStartDateInput.value;
                const endDateVal = customEndDateInput.value;
                
                if (startDateVal) {
                    const sParts = startDateVal.split("-");
                    const startDate = new Date(parseInt(sParts[0]), parseInt(sParts[1]) - 1, parseInt(sParts[2]));
                    startDate.setHours(0,0,0,0);
                    if (rowDate < startDate) return false;
                }
                if (endDateVal) {
                    const eParts = endDateVal.split("-");
                    const endDate = new Date(parseInt(eParts[0]), parseInt(eParts[1]) - 1, parseInt(eParts[2]));
                    endDate.setHours(23,59,59,999);
                    if (rowDate > endDate) return false;
                }
                return true;
            }
            return true;
        });
    }
    
    // Search query match name, company, title, or url
    if (query) {
        filtered = filtered.filter(c => 
            c.name.toLowerCase().includes(query) ||
            (c.company && c.company.toLowerCase().includes(query)) ||
            (c.title && c.title.toLowerCase().includes(query)) ||
            c.profile_url.toLowerCase().includes(query)
        );
    }
    
    // Empty state check
    if (filtered.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-table-state">
                    <div class="empty-state-content">
                        <i data-lucide="search-code"></i>
                        <p>${localContacts.length === 0 ? 'No contacts loaded yet.' : 'No matching results found.'}</p>
                        <span class="sub-text">${localContacts.length === 0 ? 'Drag and drop an Excel file in the sidebar to populate the database.' : 'Try adjusting your search filters.'}</span>
                    </div>
                </td>
            </tr>
        `;
        lucide.createIcons();
        return;
    }
    
    // Build rows
    let html = "";
    filtered.forEach(c => {
        const statusClass = c.status.toLowerCase().replace(" ", "-");
        const originalIndex = localContacts.indexOf(c) + 1;
        
        let statusIcon = "help-circle";
        if (c.status === "Connected") statusIcon = "check-circle2";
        else if (c.status === "Pending") statusIcon = "clock";
        else if (c.status === "Sent") statusIcon = "send";
        else if (c.status === "Not Started") statusIcon = "play";
        else if (c.status === "Failed") statusIcon = "alert-triangle";
        
        // Date display
        let dateStr = "—";
        if (c.status === "Connected" && c.date_accepted) {
            dateStr = c.date_accepted.split(" ")[0];
        } else if (c.date_sent) {
            dateStr = c.date_sent.split(" ")[0];
        }
        
        html += `
            <tr>
                <td style="text-align: center; font-weight: 600; color: var(--text-muted);">
                    ${originalIndex}
                </td>
                <td>
                    <div class="lead-name-cell">
                        <span class="lead-name">${c.name}</span>
                        <span class="lead-title">${c.title || 'Prospect'}</span>
                    </div>
                </td>
                <td>
                    <span class="lead-company">${c.company || '—'}</span>
                </td>
                <td>
                    <a href="${c.profile_url}" target="_blank" class="profile-link">
                        View Profile <i data-lucide="external-link"></i>
                    </a>
                </td>
                <td>
                    <span class="status-badge ${statusClass}" title="${c.logs || ''}">
                        <i data-lucide="${statusIcon}"></i> ${c.status}
                    </span>
                </td>
                <td class="date-cell">
                    ${dateStr}
                </td>
                <td style="text-align: center;">
                    <button class="btn-icon-only delete-contact-btn" data-url="${c.profile_url}" title="Delete contact">
                        <i data-lucide="trash-2" style="width: 15px; height: 15px;"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    tableBody.innerHTML = html;
    
    // Re-render Lucide Icons in table cells dynamically
    lucide.createIcons();
}

// ==========================================================================
// CONSOLE LOGGER PANELS
// ==========================================================================
function updateLogsPanel(logs) {
    // Check if new logs arrived
    if (logs.length === localLogs.length) return;
    
    // Find new indices
    const freshLogs = logs.slice(localLogs.length);
    localLogs = logs;
    
    freshLogs.forEach(entry => {
        const line = document.createElement("div");
        line.className = `log-line ${entry.type}`;
        line.innerHTML = `<span class="log-time">[${entry.time}]</span> ${entry.message}`;
        consoleOutput.appendChild(line);
    });
    
    // Auto Scroll to bottom
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

function appendLogToConsole(message, type = "info") {
    const timestamp = new Date().toTimeString().split(' ')[0];
    const line = document.createElement("div");
    line.className = `log-line ${type}`;
    line.innerHTML = `<span class="log-time">[${timestamp}]</span> ${message}`;
    consoleOutput.appendChild(line);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

function clearLogsPanel() {
    consoleOutput.innerHTML = `<div class="log-line info"><span class="log-time">[${new Date().toTimeString().split(' ')[0]}]</span> Console log cleared by user.</div>`;
}

// Note template helper character counter
function updateCharCounter() {
    const len = noteTemplateTextarea.value.length;
    charCountSpan.textContent = len;
    
    if (len >= 300) {
        charCountSpan.style.color = "var(--status-danger)";
        charCountSpan.style.fontWeight = "bold";
    } else if (len >= 260) {
        charCountSpan.style.color = "var(--status-warning)";
    } else {
        charCountSpan.style.color = "var(--text-muted)";
        charCountSpan.style.fontWeight = "normal";
    }
}

// Add a single contact profile URL directly
async function addSingleContact() {
    const url = quickUrlInput.value.trim();
    const name = quickNameInput.value.trim();
    
    if (!url) {
        alert("Please paste a LinkedIn profile URL.");
        return;
    }
    
    btnQuickAdd.disabled = true;
    appendLogToConsole(`Adding single profile: ${url}...`, "info");
    
    try {
        const response = await fetch(`${API_BASE}/contacts/add`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                profile_url: url,
                name: name
            })
        });
        
        const res = await response.json();
        btnQuickAdd.disabled = false;
        
        if (res.status === "success") {
            appendLogToConsole(res.message, "success");
            quickUrlInput.value = "";
            quickNameInput.value = "";
            fetchContacts();
        } else {
            appendLogToConsole(`Failed to add contact: ${res.error}`, "error");
            alert(`Error: ${res.error}`);
        }
    } catch (error) {
        appendLogToConsole("Network error adding contact.", "error");
        btnQuickAdd.disabled = false;
    }
}

// Handle single contact row deletion clicks
async function handleTableClick(e) {
    const deleteBtn = e.target.closest(".delete-contact-btn");
    if (!deleteBtn) return;
    
    if (isSystemRunning) {
        alert("Cannot delete contacts while automation is running.");
        return;
    }
    
    const profileUrl = deleteBtn.getAttribute("data-url");
    if (!profileUrl) return;
    
    const tr = deleteBtn.closest("tr");
    const name = tr.querySelector(".lead-name").textContent;
    
    if (!confirm(`Are you sure you want to delete "${name}" from the database?`)) return;
    
    deleteBtn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/contacts/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ profile_url: profileUrl })
        });
        
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole(`Deleted profile: ${name}`, "warning");
            fetchContacts(); // Reload contacts & update stats
        } else {
            appendLogToConsole(`Failed to delete profile: ${res.error}`, "error");
            alert(`Error: ${res.error}`);
            deleteBtn.disabled = false;
        }
    } catch (error) {
        appendLogToConsole("Network error deleting contact.", "error");
        deleteBtn.disabled = false;
    }
}

