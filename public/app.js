// ==========================================================================
// LINKCONNECT FRONTEND CONTROLLER (app.js)
// Upgraded for Secure Multi-Account Automation & Aggregated Admin Analytics
// ==========================================================================

const API_BASE = `${window.location.origin}/api`;

// Current workspace session state
let currentAccountId = "admin"; // "admin" or registered profile ID e.g. "default"
let accountsRegistry = [];
let localContacts = [];
let localLogs = [];
let currentFilteredContacts = [];
let isSystemRunning = false;
let pollingInterval = null;
let selectedAccountIdsForBulk = new Set();
let accountsCustomOrder = null; // Stores shuffled/custom order of account IDs

// UI Elements: Navigation Sidebar
const accountsMenuList = document.getElementById("accounts-menu-list");
const itemAdminTab = document.getElementById("item-admin-tab");
const btnOpenAddAccountModal = document.getElementById("btn-open-add-account-modal");

// UI Elements: Headers & View Wrapper Toggles
const workspaceTitle = document.getElementById("workspace-title");
const workspaceSubtitle = document.getElementById("workspace-subtitle");
const systemStatusDot = document.getElementById("system-status-dot");
const systemStatusText = document.getElementById("system-status-text");
const viewAdmin = document.getElementById("view-admin");
const viewWorkspace = document.getElementById("view-workspace");

// Admin View Elements
const adminStatTotal = document.getElementById("admin-stat-total");
const adminStatSent = document.getElementById("admin-stat-sent");
const adminStatPending = document.getElementById("admin-stat-pending");
const adminStatConnected = document.getElementById("admin-stat-connected");
const adminStatAvgDay = document.getElementById("admin-stat-avg-day");
const adminStatAcceptRate = document.getElementById("admin-stat-accept-rate");
const adminAcceptRateBar = document.getElementById("admin-accept-rate-bar");
const adminAccountsTableBody = document.getElementById("admin-accounts-table-body");
const accountsCountTag = document.getElementById("accounts-count-tag");

// Workspace Session controls
const btnLaunchLogin = document.getElementById("btn-launch-login");
const btnCheckLogin = document.getElementById("btn-check-login");
const btnDeleteAccountWorkspace = document.getElementById("btn-delete-account-workspace");
const excelDropZone = document.getElementById("excel-drop-zone");
const excelFileInput = document.getElementById("excel-file-input");

// Quick Add Single Profile
const quickUrlInput = document.getElementById("quick-url-input");
const quickNameInput = document.getElementById("quick-name-input");
const btnQuickAdd = document.getElementById("btn-quick-add");

// Safe Settings
const delayMinInput = document.getElementById("delay-min");
const delayMaxInput = document.getElementById("delay-max");
const dailyLimitInput = document.getElementById("daily-limit");
const weeklyLimitInput = document.getElementById("weekly-limit");
const liUserInput = document.getElementById("workspace-li-user");
const liPassInput = document.getElementById("workspace-li-pass");
const workspaceProxyIndicator = document.getElementById("workspace-proxy-indicator");
const btnSaveSettings = document.getElementById("btn-save-settings");

// Inline workspace rename UI
const workspaceTitleDisplayRow = document.getElementById("workspace-title-display-row");
const workspaceTitleEditRow = document.getElementById("workspace-title-edit-row");
const workspaceTitleInput = document.getElementById("workspace-title-input");
const btnRenameWorkspace = document.getElementById("btn-rename-workspace");
const btnRenameConfirm = document.getElementById("btn-rename-confirm");
const btnRenameCancel = document.getElementById("btn-rename-cancel");

// Message Template
const sendWithNoteCheckbox = document.getElementById("send-with-note");
const noteTemplateContainer = document.getElementById("note-template-container");
const noteTemplateTextarea = document.getElementById("note-template");
const charCountSpan = document.getElementById("char-count");
const tagBadges = document.querySelectorAll(".tag-badge");

// Operational Buttons
const rangeStartInput = document.getElementById("range-start");
const rangeEndInput = document.getElementById("range-end");
const btnStart = document.getElementById("btn-start");
const btnStop = document.getElementById("btn-stop");
const btnSync = document.getElementById("btn-sync");
const btnClearLogs = document.getElementById("btn-clear-logs");
const consoleOutput = document.getElementById("console-output");

// Workspace Stats
const statTotal = document.getElementById("stat-total");
const statSent = document.getElementById("stat-sent");
const statPending = document.getElementById("stat-pending");
const statConnected = document.getElementById("stat-connected");
const statAvgDay = document.getElementById("stat-avg-day");
const statAcceptRate = document.getElementById("stat-accept-rate");
const acceptRateBar = document.getElementById("accept-rate-bar");

// Safe Quotas
const quotaDailyCurrent = document.getElementById("quota-daily-current");
const quotaDailyMax = document.getElementById("quota-daily-max");
const quotaDailyBar = document.getElementById("quota-daily-bar");
const quotaWeeklyCurrent = document.getElementById("quota-weekly-current");
const quotaWeeklyMax = document.getElementById("quota-weekly-max");
const quotaWeeklyBar = document.getElementById("quota-weekly-bar");

// Table Search & Filters
const contactsCountSpan = document.getElementById("contacts-count");
const tableSearchInput = document.getElementById("table-search");
const statusFilterSelect = document.getElementById("status-filter");
const dateFilterSelect = document.getElementById("date-filter");
const customDateContainer = document.getElementById("custom-date-container");
const customStartDateInput = document.getElementById("custom-start-date");
const customEndDateInput = document.getElementById("custom-end-date");
const btnApplyDate = document.getElementById("btn-apply-date");
const btnClearDate = document.getElementById("btn-clear-date");
const btnResetContacts = document.getElementById("btn-reset-contacts");
const btnAdminClearDb = document.getElementById("btn-admin-clear-db");
const tableBody = document.getElementById("table-body");

// Add Account Modal UI
const addAccountModal = document.getElementById("add-account-modal");
const btnCloseModal = document.getElementById("btn-close-modal");
const btnCancelModal = document.getElementById("btn-cancel-modal");
const btnSaveAccount = document.getElementById("btn-save-account");
const accIdInput = document.getElementById("acc-id-input");
const accNameInput = document.getElementById("acc-name-input");
const accProxyServer = document.getElementById("acc-proxy-server");
const accProxyUser = document.getElementById("acc-proxy-user");
const accProxyPass = document.getElementById("acc-proxy-pass");

// ==========================================================================
// INITIAL SETUP & MAIN ROUTINES
// ==========================================================================
document.addEventListener("DOMContentLoaded", () => {
    lucide.createIcons();
    
    // Wire up events
    setupEventListeners();
    setupResetModal();
    
    // Switch to initial Admin View
    switchWorkspace("admin");
    
    // Begin fast status polling
    startPolling(3000);
});

// Setup Page Click Handlers and Dynamic Form Updates
function setupEventListeners() {
    // Navigation swappers
    itemAdminTab.addEventListener("click", () => switchWorkspace("admin"));
    
    btnOpenAddAccountModal.addEventListener("click", quickCreateAndLoginAccount);
    
    btnCloseModal.addEventListener("click", () => addAccountModal.style.display = "none");
    btnCancelModal.addEventListener("click", () => addAccountModal.style.display = "none");
    btnSaveAccount.addEventListener("click", registerNewAccountProfile);
    
    // Browser Login Trigger
    btnLaunchLogin.addEventListener("click", launchLoginBrowser);
    btnCheckLogin.addEventListener("click", checkWorkspaceLoginSession);
    btnDeleteAccountWorkspace.addEventListener("click", () => deleteAccountProfile(currentAccountId));
    
    // Quick add contact
    btnQuickAdd.addEventListener("click", addSingleContact);
    
    // Excel Drag & Drop setup
    excelDropZone.addEventListener("click", () => excelFileInput.click());
    excelFileInput.addEventListener("change", (e) => {
        if (e.target.files.length > 0) uploadExcelFile(e.target.files[0]);
    });
    
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
    excelDropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        excelDropZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) uploadExcelFile(e.dataTransfer.files[0]);
    }, false);
    
    // Note builders character counter
    noteTemplateTextarea.addEventListener("input", updateCharCounter);
    sendWithNoteCheckbox.addEventListener("change", toggleNoteTemplateOpacity);
    
    // Tag badging system
    tagBadges.forEach(badge => {
        badge.addEventListener("click", () => {
            if (noteTemplateTextarea.disabled) return;
            const tag = badge.getAttribute("data-tag");
            const startPos = noteTemplateTextarea.selectionStart;
            const endPos = noteTemplateTextarea.selectionEnd;
            const text = noteTemplateTextarea.value;
            
            noteTemplateTextarea.value = text.substring(0, startPos) + tag + text.substring(endPos, text.length);
            noteTemplateTextarea.focus();
            noteTemplateTextarea.selectionStart = startPos + tag.length;
            noteTemplateTextarea.selectionEnd = startPos + tag.length;
            updateCharCounter();
        });
    });
    
    // Workspace Controls
    btnStart.addEventListener("click", startWorkspaceAutomation);
    btnStop.addEventListener("click", stopWorkspaceAutomation);
    btnSync.addEventListener("click", syncAcceptedRequests);
    btnClearLogs.addEventListener("click", clearLogsPanel);
    btnSaveSettings.addEventListener("click", saveWorkspaceSettings);
    
    // Inline workspace rename handlers
    btnRenameWorkspace.addEventListener("click", () => startInlineRename());
    btnRenameConfirm.addEventListener("click", () => confirmInlineRename());
    btnRenameCancel.addEventListener("click", () => cancelInlineRename());
    workspaceTitleInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") confirmInlineRename();
        if (e.key === "Escape") cancelInlineRename();
    });
    
    // Database modifications
    btnResetContacts.addEventListener("click", resetProspectsStatus);
    if (btnAdminClearDb) btnAdminClearDb.addEventListener("click", adminClearDatabases);
    
    // Prospect search & filter events
    tableSearchInput.addEventListener("input", renderWorkspaceTable);
    statusFilterSelect.addEventListener("change", renderWorkspaceTable);
    
    dateFilterSelect.addEventListener("change", () => {
        if (dateFilterSelect.value === "custom") {
            customDateContainer.style.display = "flex";
        } else {
            customDateContainer.style.display = "none";
            customStartDateInput.value = "";
            customEndDateInput.value = "";
            renderWorkspaceTable();
        }
    });
    
    btnApplyDate.addEventListener("click", renderWorkspaceTable);
    btnClearDate.addEventListener("click", () => {
        customStartDateInput.value = "";
        customEndDateInput.value = "";
        renderWorkspaceTable();
    });
    
    // Admin Date Filter events
    const adminDateFilterSelect = document.getElementById("admin-date-filter");
    const adminStatusFilterSelect = document.getElementById("admin-status-filter");
    const adminCustomDateContainer = document.getElementById("admin-custom-date-container");
    const adminCustomStartDateInput = document.getElementById("admin-custom-start-date");
    const adminCustomEndDateInput = document.getElementById("admin-custom-end-date");
    const adminBtnApplyDate = document.getElementById("admin-btn-apply-date");
    const adminBtnClearDate = document.getElementById("admin-btn-clear-date");
    
    if (adminStatusFilterSelect) {
        adminStatusFilterSelect.addEventListener("change", fetchAccountsRegistry);
    }
    
    if (adminDateFilterSelect) {
        adminDateFilterSelect.addEventListener("change", () => {
            if (adminDateFilterSelect.value === "custom") {
                adminCustomDateContainer.style.display = "flex";
            } else {
                adminCustomDateContainer.style.display = "none";
                if (adminCustomStartDateInput) adminCustomStartDateInput.value = "";
                if (adminCustomEndDateInput) adminCustomEndDateInput.value = "";
                fetchAccountsRegistry();
            }
        });
    }
    
    if (adminBtnApplyDate) {
        adminBtnApplyDate.addEventListener("click", fetchAccountsRegistry);
    }
    
    if (adminBtnClearDate) {
        adminBtnClearDate.addEventListener("click", () => {
            if (adminCustomStartDateInput) adminCustomStartDateInput.value = "";
            if (adminCustomEndDateInput) adminCustomEndDateInput.value = "";
            fetchAccountsRegistry();
        });
    }
    
    // Table action triggers (deletions)
    tableBody.addEventListener("click", handleProspectTableClick);
    
    // Settings limit hooks for reactive calculations
    dailyLimitInput.addEventListener("input", refreshWorkspaceStats);
    weeklyLimitInput.addEventListener("input", refreshWorkspaceStats);

    // Master checkbox bulk routing & run button listener
    const masterCheckbox = document.getElementById("checkbox-select-all-accounts");
    if (masterCheckbox) {
        masterCheckbox.addEventListener("change", () => {
            const checked = masterCheckbox.checked;
            document.querySelectorAll(".account-select-checkbox").forEach(cb => {
                cb.checked = checked;
                const id = cb.getAttribute("data-id");
                if (checked) {
                    selectedAccountIdsForBulk.add(id);
                } else {
                    selectedAccountIdsForBulk.delete(id);
                }
            });
        });
    }

    const btnRunSelectedSeq = document.getElementById("btn-run-selected-seq");
    if (btnRunSelectedSeq) {
        btnRunSelectedSeq.addEventListener("click", runSelectedSequentially);
    }

    // Drag-and-drop manual shuffle event handling is wired up dynamically inside renderAdminDashboardView

    // Scheduler UI Event Handlers
    const schedulerEnabled = document.getElementById("scheduler-enabled");
    const schedulerConfig = document.getElementById("scheduler-config-container");
    const schedulerTime = document.getElementById("scheduler-time");
    const btnSaveSchedule = document.getElementById("btn-save-schedule");
    
    if (schedulerEnabled) {
        schedulerEnabled.addEventListener("change", () => {
            schedulerConfig.style.display = schedulerEnabled.checked ? "block" : "none";
            btnSaveSchedule.disabled = false;
        });
    }
    
    if (schedulerTime) {
        schedulerTime.addEventListener("change", () => {
            btnSaveSchedule.disabled = false;
        });
    }
    
    const dayButtons = document.querySelectorAll(".day-btn");
    dayButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            btn.classList.toggle("active");
            btnSaveSchedule.disabled = false;
        });
    });
    
    const schedulerStartIdx = document.getElementById("scheduler-start-idx");
    const schedulerEndIdx = document.getElementById("scheduler-end-idx");
    
    if (schedulerStartIdx) {
        schedulerStartIdx.addEventListener("input", () => {
            btnSaveSchedule.disabled = false;
        });
    }
    
    if (schedulerEndIdx) {
        schedulerEndIdx.addEventListener("input", () => {
            btnSaveSchedule.disabled = false;
        });
    }
    
    if (btnSaveSchedule) {
        btnSaveSchedule.addEventListener("click", saveWorkspaceSchedule);
    }
}

// Start Background Loop
function startPolling(ms) {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = setInterval(pollBackendRoutines, ms);
}

// Aggregated loop fetching registry list & current workspace
async function pollBackendRoutines() {
    await fetchAccountsRegistry();
    if (currentAccountId !== "admin") {
        await fetchWorkspaceState();
        await fetchWorkspaceContacts();
    }
}

// ==========================================================================
// WORKSPACE NAVIGATION SWITCHER
// ==========================================================================
async function switchWorkspace(accountId) {
    currentAccountId = accountId;
    
    // Clear console panel logs when changing views
    consoleOutput.innerHTML = "";
    localLogs = [];
    
    if (currentAccountId === "admin") {
        // Toggle view active states
        viewAdmin.classList.add("active");
        viewWorkspace.classList.remove("active");
        viewWorkspace.style.display = "none";
        viewAdmin.style.display = "block";
        
        // Navigation styling active state
        itemAdminTab.classList.add("active");
        
        workspaceTitle.textContent = "Admin Dashboard";
        workspaceSubtitle.textContent = "Aggregated system-wide analytics & stats";
        
        // Hide rename pencil when on admin dashboard
        btnRenameWorkspace.style.display = "none";
        workspaceTitleDisplayRow.style.display = "flex";
        workspaceTitleEditRow.style.display = "none";
        systemStatusDot.className = "pulse-dot grey-pulse";
        systemStatusText.textContent = "Multi-Account Manager Active";
        
        await fetchAccountsRegistry();
    } else {
        // Find selected account configurations
        const acc = accountsRegistry.find(a => a.id === currentAccountId);
        if (!acc) return;
        
        // Toggle view active states
        viewAdmin.classList.remove("active");
        viewAdmin.style.display = "none";
        viewWorkspace.classList.add("active");
        viewWorkspace.style.display = "grid";
        
        // Navigation styling state
        itemAdminTab.classList.remove("active");
        
        workspaceTitle.textContent = `${acc.name} Workspace`;
        workspaceSubtitle.textContent = `Isolated profile workspace (Account ID: ${acc.id})`;
        
        // Show rename pencil icon on account workspace views only
        btnRenameWorkspace.style.display = "flex";
        workspaceTitleDisplayRow.style.display = "flex";
        workspaceTitleEditRow.style.display = "none";
        
        if (acc.id !== "default") {
            btnDeleteAccountWorkspace.style.display = "block";
        } else {
            btnDeleteAccountWorkspace.style.display = "none";
        }
        
        // Pre-fill settings
        const cfg = acc.config || {};
        delayMinInput.value = cfg.delay_min || 30;
        delayMaxInput.value = cfg.delay_max || 70;
        dailyLimitInput.value = cfg.daily_limit || 25;
        weeklyLimitInput.value = cfg.weekly_limit || 150;
        liUserInput.value = acc.li_username || "";
        liPassInput.value = acc.li_password || "";
        
        sendWithNoteCheckbox.checked = cfg.send_with_note || false;
        noteTemplateTextarea.value = cfg.note_template || "";
        updateCharCounter();
        toggleNoteTemplateOpacity();
        
        // Dynamic proxy badge routing visibility
        if (acc.proxy) {
            workspaceProxyIndicator.style.display = "inline-flex";
            workspaceProxyIndicator.title = `Routing through: ${acc.proxy}`;
        } else {
            workspaceProxyIndicator.style.display = "none";
        }
        
        // Pre-fill scheduler settings
        const schedulerEnabled = document.getElementById("scheduler-enabled");
        const schedulerConfig = document.getElementById("scheduler-config-container");
        const schedulerTime = document.getElementById("scheduler-time");
        const btnSaveSchedule = document.getElementById("btn-save-schedule");
        
        if (schedulerEnabled) {
            const sched = cfg.schedule || {};
            const isEnabled = sched.enabled || false;
            schedulerEnabled.checked = isEnabled;
            schedulerConfig.style.display = isEnabled ? "block" : "none";
            schedulerTime.value = sched.time || "10:00";
            
            const activeDays = sched.days || [];
            const dayButtons = document.querySelectorAll(".day-btn");
            dayButtons.forEach(btn => {
                const dayVal = parseInt(btn.getAttribute("data-day"));
                if (activeDays.includes(dayVal)) {
                    btn.classList.add("active");
                } else {
                    btn.classList.remove("active");
                }
            });
            const schedulerStartIdx = document.getElementById("scheduler-start-idx");
            const schedulerEndIdx = document.getElementById("scheduler-end-idx");
            if (schedulerStartIdx) schedulerStartIdx.value = cfg.start_index || "";
            if (schedulerEndIdx) schedulerEndIdx.value = cfg.end_index || "";
            
            btnSaveSchedule.disabled = true; // Reset unsaved changes flag
        }
        
        appendLogToConsole(`Swapped to account profile: ${acc.name}. Synchronizing database...`, "info");
        
        // Perform fast data load
        await fetchWorkspaceState();
        await fetchWorkspaceContacts();
        
        // Synchronize navigation highlight active state
        highlightActiveSidebarItem();
    }
    
    lucide.createIcons();
}

function highlightActiveSidebarItem() {
    const items = accountsMenuList.querySelectorAll(".account-item");
    items.forEach(it => {
        if (it.getAttribute("data-account-id") === currentAccountId) {
            it.classList.add("active");
        } else {
            it.classList.remove("active");
        }
    });
}

function toggleNoteTemplateOpacity() {
    const checked = sendWithNoteCheckbox.checked;
    noteTemplateTextarea.disabled = !checked;
    if (checked) {
        noteTemplateContainer.style.opacity = "1";
        noteTemplateContainer.style.pointerEvents = "auto";
    } else {
        noteTemplateContainer.style.opacity = "0.4";
        noteTemplateContainer.style.pointerEvents = "none";
    }
}

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

// ==========================================================================
// REGISTRY API ENDPOINTS (GET /api/accounts, POST /api/accounts/add etc)
// ==========================================================================
function getAdminDateParams() {
    const queryParts = [];
    
    // Status Filter
    const statusFilterEl = document.getElementById("admin-status-filter");
    const statusFilter = statusFilterEl ? statusFilterEl.value : "all";
    if (statusFilter !== "all") {
        queryParts.push(`status=${statusFilter}`);
    }
    
    // Date Filter
    const filter = document.getElementById("admin-date-filter");
    const dateFilter = filter ? filter.value : "all";
    
    if (dateFilter !== "all") {
        const now = new Date();
        let startDate = null;
        let endDate = null;
        
        const formatDate = (d) => {
            const year = d.getFullYear();
            const month = String(d.getMonth() + 1).padStart(2, '0');
            const day = String(d.getDate()).padStart(2, '0');
            return `${year}-${month}-${day}`;
        };
        
        if (dateFilter === "today") {
            startDate = formatDate(now);
            endDate = formatDate(now);
        } else if (dateFilter === "yesterday") {
            const yesterday = new Date();
            yesterday.setDate(now.getDate() - 1);
            startDate = formatDate(yesterday);
            endDate = formatDate(yesterday);
        } else if (dateFilter === "week") {
            const weekAgo = new Date();
            weekAgo.setDate(now.getDate() - 7);
            startDate = formatDate(weekAgo);
            endDate = formatDate(now);
        } else if (dateFilter === "month") {
            const monthAgo = new Date();
            monthAgo.setDate(now.getDate() - 30);
            startDate = formatDate(monthAgo);
            endDate = formatDate(now);
        } else if (dateFilter === "custom") {
            const startInput = document.getElementById("admin-custom-start-date");
            const endInput = document.getElementById("admin-custom-end-date");
            if (startInput && startInput.value) startDate = startInput.value;
            if (endInput && endInput.value) endDate = endInput.value;
        }
        
        if (startDate) queryParts.push(`start_date=${startDate}`);
        if (endDate) queryParts.push(`end_date=${endDate}`);
    }
    
    return queryParts.length > 0 ? "?" + queryParts.join("&") : "";
}

async function fetchAccountsRegistry() {
    try {
        const queryParams = getAdminDateParams();
        const sep = queryParams ? "&" : "?";
        const response = await fetch(`${API_BASE}/accounts${queryParams}${sep}_t=${Date.now()}`);
        if (!response.ok) return;
        
        const fetchedAccounts = await response.json();
        if (accountsCustomOrder) {
            fetchedAccounts.sort((a, b) => {
                const idxA = accountsCustomOrder.indexOf(a.id);
                const idxB = accountsCustomOrder.indexOf(b.id);
                if (idxA === -1 && idxB === -1) return 0;
                if (idxA === -1) return 1;
                if (idxB === -1) return -1;
                return idxA - idxB;
            });
        }
        accountsRegistry = fetchedAccounts;
        
        // Populate accounts lists in sidebar switcher
        renderSidebarAccounts();
        
        if (currentAccountId === "admin") {
            renderAdminDashboardView();
        } else {
            // If in active account workspace, keep its header status synchronized
            const activeAcc = accountsRegistry.find(a => a.id === currentAccountId);
            if (activeAcc) {
                isSystemRunning = activeAcc.is_running;
                if (isSystemRunning) {
                    systemStatusDot.className = "pulse-dot running";
                    systemStatusText.textContent = `Running: ${activeAcc.current_action}`;
                } else {
                    systemStatusDot.className = "pulse-dot";
                    systemStatusText.textContent = "System Idle";
                }
            }
        }
    } catch (e) {
        console.error("Failed fetching accounts registry:", e);
    }
}

// Build LHS switcher items
function renderSidebarAccounts() {
    let html = "";
    accountsRegistry.forEach(acc => {
        const isActive = acc.id === currentAccountId ? "active" : "";
        
        // Format account status descriptions
        let stClass = "grey-pulse";
        let statusDesc = "Idle";
        if (acc.is_running) {
            stClass = "running";
            statusDesc = acc.current_action || "Running";
        } else if (acc.status === "Login Setup") {
            stClass = "teal-pulse";
            statusDesc = "Manual Login Active";
        }
        
        // Assign beautiful unique gradient icons per account
        let gradClass = "bg-blue";
        if (acc.id === "default") gradClass = "bg-purple";
        else if (acc.id.includes("sales")) gradClass = "bg-pink";
        else if (acc.id.includes("recruit")) gradClass = "bg-teal";
        else if (acc.id.includes("manager")) gradClass = "bg-yellow";
        
        html += `
            <button class="account-item ${isActive}" data-account-id="${acc.id}">
                <div class="item-icon ${gradClass}"><i data-lucide="user"></i></div>
                <div class="item-info">
                    <span class="acc-name">${acc.name}</span>
                    <span class="acc-status">
                        <span class="pulse-dot ${stClass}" style="display:inline-block; width:6px; height:6px; margin-right:4px;"></span>
                        ${statusDesc}
                    </span>
                </div>
            </button>
        `;
    });
    
    accountsMenuList.innerHTML = html;
    
    // Bind click swap events
    const items = accountsMenuList.querySelectorAll(".account-item");
    items.forEach(it => {
        it.addEventListener("click", () => {
            const accId = it.getAttribute("data-account-id");
            switchWorkspace(accId);
        });
    });
    
    lucide.createIcons();
}

// Process Admin dashboard view counts & registered tables
function renderAdminDashboardView() {
    let totalProfiles = 0;
    let totalSent = 0;
    let totalPending = 0;
    let totalConnected = 0;
    let totalActiveDays = 0;
    
    // Compute aggregations across all registry items
    accountsRegistry.forEach(acc => {
        const s = acc.stats || {};
        totalProfiles += s.total || 0;
        totalSent += s.sent || 0;
        totalPending += s.pending || 0;
        totalConnected += s.connected || 0;
        totalActiveDays += s.active_days_count || 1;
    });
    
    // Draw central stats counts
    adminStatTotal.textContent = totalProfiles;
    adminStatSent.textContent = totalSent;
    adminStatPending.textContent = totalPending;
    adminStatConnected.textContent = totalConnected;
    
    const avgSentDay = totalActiveDays > 0 ? (totalSent / totalActiveDays).toFixed(1) : "0.0";
    const avgDayNumEl = adminStatAvgDay.childNodes[0];
    if (avgDayNumEl) avgDayNumEl.textContent = avgSentDay;
    
    const acceptRate = totalSent > 0 ? Math.round((totalConnected / totalSent) * 100) : 0;
    const acceptRateNumEl = adminStatAcceptRate.childNodes[0];
    if (acceptRateNumEl) acceptRateNumEl.textContent = acceptRate;
    
    adminAcceptRateBar.style.width = `${acceptRate}%`;
    
    // Update Registered Accounts Count Badge
    if (accountsCountTag) {
        accountsCountTag.textContent = `${accountsRegistry.length} account${accountsRegistry.length === 1 ? '' : 's'}`;
    }
    
    // Update Admin Table Header Title with Selected Filters
    const adminTableTitle = document.getElementById("admin-table-title");
    if (adminTableTitle) {
        const dateFilterSelect = document.getElementById("admin-date-filter");
        const dateFilter = dateFilterSelect ? dateFilterSelect.value : "all";
        
        const statusFilterSelect = document.getElementById("admin-status-filter");
        const statusFilter = statusFilterSelect ? statusFilterSelect.value : "all";
        
        const dateLabels = {
            all: "All Time",
            today: "Today",
            yesterday: "Yesterday",
            week: "Past Week",
            month: "Past Month",
            custom: "Custom Range"
        };
        
        const statusLabels = {
            all: "All Prospects",
            "Not Started": "Not Started Only",
            "Pending": "Pending Only",
            "Connected": "Connected Only",
            "Failed": "Failed Only"
        };
        
        const dLabel = dateLabels[dateFilter] || "All Time";
        const sLabel = statusLabels[statusFilter] || "All Prospects";
        
        adminTableTitle.textContent = `Registered LinkedIn Profiles (${sLabel} - ${dLabel})`;
    }
    
    // Keep master checkbox state in sync
    const masterCheckbox = document.getElementById("checkbox-select-all-accounts");
    if (masterCheckbox) {
        masterCheckbox.checked = accountsRegistry.length > 0 && accountsRegistry.every(acc => selectedAccountIdsForBulk.has(acc.id));
    }
    
    // Draw Accounts grid rows
    let tableHtml = "";
    accountsRegistry.forEach(acc => {
        const s = acc.stats || {};
        const isRunning = acc.is_running;
        
        let stText = "Idle";
        let stDotClass = "grey-pulse";
        if (isRunning) {
            stDotClass = "running";
            stText = "Running";
        } else if (acc.status === "Login Setup") {
            stDotClass = "teal-pulse";
            stText = "Login Setup";
        }
        
        const proxyStr = acc.proxy ? acc.proxy : "None";
        const proxyBadge = acc.proxy 
            ? `<span class="proxy-badge-indicator" title="${acc.proxy}"><i data-lucide="globe"></i> Active</span>`
            : `<span class="count-tag" style="color:var(--text-muted);">Disabled</span>`;
            
        const isChecked = selectedAccountIdsForBulk.has(acc.id) ? "checked" : "";
            
        tableHtml += `
            <tr draggable="true" class="draggable-row" data-id="${acc.id}">
                <td style="text-align: center; vertical-align: middle;">
                    <div class="drag-handle" style="cursor: grab; color: var(--text-muted); opacity: 0.6; transition: opacity 0.2s;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.6">
                        <i data-lucide="grip-vertical" style="width: 14px; height: 14px;"></i>
                    </div>
                </td>
                <td style="text-align: center; vertical-align: middle;">
                    <input type="checkbox" class="account-select-checkbox custom-checkbox" data-id="${acc.id}" ${isChecked}>
                </td>
                <td style="font-weight: 700; vertical-align: middle;">${acc.name}</td>
                <td style="vertical-align: middle;">${proxyBadge}</td>
                <td style="vertical-align: middle;"><strong>${(acc.config && acc.config.daily_limit) || 25}</strong> / day</td>
                <td style="text-align: center; vertical-align: middle;"><strong>${s.total || 0}</strong></td>
                <td style="text-align: center; color: var(--accent-blue); font-weight:600; vertical-align: middle;">${s.sent || 0}</td>
                <td style="text-align: center; color: var(--status-success); font-weight:600; vertical-align: middle;">${s.connected || 0}</td>
                <td style="text-align: center; vertical-align: middle;">
                    <strong>${s.acceptance_rate || 0}%</strong>
                </td>
                <td style="font-size:0.75rem; color:var(--text-secondary); max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; vertical-align: middle;">
                    ${acc.current_action || 'Idle'}
                </td>
                <td style="text-align: center; vertical-align: middle;">
                    <span class="status-badge ${isRunning ? 'pending' : 'not-started'}">
                        <span class="pulse-dot ${stDotClass}" style="display:inline-block; width:6px; height:6px; margin-right:4px;"></span>
                        ${stText}
                    </span>
                </td>
                <td style="text-align: center; white-space: nowrap; vertical-align: middle;">
                    <button class="btn btn-secondary btn-sm workspace-swapper-btn" data-id="${acc.id}">
                        Open
                    </button>
                    ${acc.id !== 'default' ? `
                    <button class="btn btn-danger-outline btn-sm delete-account-btn" data-id="${acc.id}" title="Delete Account Profile" style="margin-left: 4px; padding: 4px 8px;">
                        <i data-lucide="trash-2" style="width: 14px; height: 14px; display: inline-block; vertical-align: middle;"></i>
                    </button>
                    ` : ''}
                </td>
            </tr>
        `;
    });
    
    adminAccountsTableBody.innerHTML = tableHtml;
    setupRowDragAndDrop();
    
    // Bind click/change hooks to individual checkboxes
    const rowCheckboxes = adminAccountsTableBody.querySelectorAll(".account-select-checkbox");
    rowCheckboxes.forEach(cb => {
        cb.addEventListener("change", () => {
            const id = cb.getAttribute("data-id");
            if (cb.checked) {
                selectedAccountIdsForBulk.add(id);
            } else {
                selectedAccountIdsForBulk.delete(id);
            }
            // Sync master checkbox state
            if (masterCheckbox) {
                masterCheckbox.checked = accountsRegistry.length > 0 && accountsRegistry.every(acc => selectedAccountIdsForBulk.has(acc.id));
            }
        });
    });
    
    // Bind click hooks to workspace swap buttons
    const swapBtns = adminAccountsTableBody.querySelectorAll(".workspace-swapper-btn");
    swapBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const accId = btn.getAttribute("data-id");
            switchWorkspace(accId);
        });
    });
    
    // Bind click hooks to workspace delete buttons
    const deleteBtns = adminAccountsTableBody.querySelectorAll(".delete-account-btn");
    deleteBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const accId = btn.getAttribute("data-id");
            deleteAccountProfile(accId);
        });
    });
    
    lucide.createIcons();
}

// POST new profile account creation
async function registerNewAccountProfile() {
    const id = accIdInput.value.trim().toLowerCase();
    const name = accNameInput.value.trim();
    const pServer = accProxyServer.value.trim();
    const pUser = accProxyUser.value.trim();
    const pPass = accProxyPass.value.trim();
    
    if (!id || !/^[a-z0-9_\-]+$/.test(id)) {
        alert("Account ID must contain only lowercase letters, numbers, dashes, or underscores.");
        return;
    }
    
    if (!name) {
        alert("Please enter a display name for the account profile.");
        return;
    }
    
    const payload = {
        id: id,
        name: name,
        proxy: pServer ? {
            server: pServer,
            username: pUser || null,
            password: pPass || null
        } : null
    };
    
    btnSaveAccount.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/accounts/add`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        btnSaveAccount.disabled = false;
        
        if (res.status === "success") {
            addAccountModal.style.display = "none";
            await fetchAccountsRegistry();
            // Automatically swap to newly created workspace and trigger login
            await switchWorkspace(id);
            launchLoginBrowser();
        } else {
            alert(`Failed registering profile: ${res.error}`);
        }
    } catch (e) {
        alert("Connection network error registering account.");
        btnSaveAccount.disabled = false;
    }
}

// Quick Auto-Create Account Profile and Trigger Login (no modals/safety credentials cards)
async function quickCreateAndLoginAccount() {
    // Calculate next index name
    const count = accountsRegistry.length;
    const nextNum = count + 1;
    const newId = `profile_${nextNum}_${Date.now().toString().slice(-4)}`;
    const newName = `Profile ${nextNum}`;
    
    btnOpenAddAccountModal.disabled = true;
    const originalContent = btnOpenAddAccountModal.innerHTML;
    btnOpenAddAccountModal.innerHTML = `<i data-lucide="loader" class="animate-spin" style="width:14px; height:14px; margin-right:6px; display:inline-block; vertical-align:middle;"></i> Creating...`;
    lucide.createIcons();
    
    const payload = {
        id: newId,
        name: newName,
        proxy: null
    };
    
    try {
        const response = await fetch(`${API_BASE}/accounts/add`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        
        btnOpenAddAccountModal.disabled = false;
        btnOpenAddAccountModal.innerHTML = originalContent;
        lucide.createIcons();
        
        if (res.status === "success") {
            await fetchAccountsRegistry();
            // Swap view focus and instantly spawn Chrome
            await switchWorkspace(newId);
            launchLoginBrowser();
        } else {
            alert(`Failed registering profile: ${res.error}`);
        }
    } catch (e) {
        alert("Network connection error creating account.");
        btnOpenAddAccountModal.disabled = false;
        btnOpenAddAccountModal.innerHTML = originalContent;
        lucide.createIcons();
    }
}

// POST bulk start selected accounts sequentially
async function runSelectedSequentially() {
    const selectedSet = selectedAccountIdsForBulk;
    if (selectedSet.size === 0) {
        alert("Please select at least one account to run sequentially.");
        return;
    }
    
    // Sort selected IDs based on their custom drag-and-drop index in accountsRegistry (manual sequence priority!)
    let selectedIds = accountsRegistry
        .map(a => a.id)
        .filter(id => selectedSet.has(id));
    
    const btn = document.getElementById("btn-run-selected-seq");
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="animate-spin" style="width:14px; height:14px; margin-right:6px; display:inline-block; vertical-align:middle;"></i> Queuing...`;
    lucide.createIcons();
    
    let successCount = 0;
    let failCount = 0;
    
    for (const accountId of selectedIds) {
        const acc = accountsRegistry.find(a => a.id === accountId);
        if (!acc) {
            failCount++;
            continue;
        }
        
        const cfg = acc.config || {};
        const payload = {
            account_id: accountId,
            note_template: cfg.note_template || "Hi {FirstName}, let's connect!",
            send_with_note: cfg.send_with_note || false,
            delay_min: cfg.delay_min || 30,
            delay_max: cfg.delay_max || 70,
            daily_limit: cfg.daily_limit || 25,
            weekly_limit: cfg.weekly_limit || 150
        };
        
        try {
            const response = await fetch(`${API_BASE}/start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const res = await response.json();
            if (response.ok && res.status === "success") {
                successCount++;
            } else {
                failCount++;
            }
        } catch (e) {
            failCount++;
        }
        await new Promise(r => setTimeout(r, 200));
    }
    
    selectedAccountIdsForBulk.clear();
    const masterCheckbox = document.getElementById("checkbox-select-all-accounts");
    if (masterCheckbox) masterCheckbox.checked = false;
    
    await fetchAccountsRegistry();
    
    btn.disabled = false;
    btn.innerHTML = originalText;
    lucide.createIcons();
    
    alert(`Bulk sequential run dispatched successfully!\n- Successfully Queued: ${successCount} profile(s)\n- Failed to Queue: ${failCount} profile(s)`);
}

// POST update specific workspace limits/note configs (delay, limits, note template)
async function saveWorkspaceSettings() {
    if (currentAccountId === "admin") return;
    
    const payload = {
        id: currentAccountId,
        li_username: liUserInput.value.trim(),
        li_password: liPassInput.value.trim(),
        config: {
            note_template: noteTemplateTextarea.value,
            send_with_note: sendWithNoteCheckbox.checked,
            delay_min: parseInt(delayMinInput.value) || 30,
            delay_max: parseInt(delayMaxInput.value) || 70,
            daily_limit: parseInt(dailyLimitInput.value) || 25,
            weekly_limit: parseInt(weeklyLimitInput.value) || 150
        }
    };
    
    const originalContent = btnSaveSettings.innerHTML;
    btnSaveSettings.disabled = true;
    btnSaveSettings.innerHTML = `<i data-lucide="loader" class="animate-spin" style="width:14px; height:14px; margin-right:6px;"></i> Saving...`;
    lucide.createIcons();
    
    appendLogToConsole("Updating account settings on backend registry...", "info");
    
    try {
        const response = await fetch(`${API_BASE}/accounts/update-config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        
        if (res.status === "success") {
            btnSaveSettings.innerHTML = `<i data-lucide="check" style="width:14px; height:14px; margin-right:6px;"></i> Saved`;
            btnSaveSettings.style.backgroundColor = "#22c55e";
            
            appendLogToConsole("Account settings updated successfully.", "success");
            await fetchAccountsRegistry();
            
            setTimeout(() => {
                btnSaveSettings.disabled = false;
                btnSaveSettings.innerHTML = originalContent;
                btnSaveSettings.style.backgroundColor = "";
                lucide.createIcons();
            }, 2000);
        } else {
            throw new Error(res.error);
        }
    } catch (e) {
        btnSaveSettings.disabled = false;
        btnSaveSettings.innerHTML = originalContent;
        lucide.createIcons();
        appendLogToConsole(`Failed updating config: ${e.message}`, "error");
        alert(`Error updating settings: ${e.message}`);
    }
}

// POST save workspace scheduling configuration
async function saveWorkspaceSchedule() {
    if (currentAccountId === "admin") return;
    
    const schedulerEnabled = document.getElementById("scheduler-enabled");
    const schedulerTime = document.getElementById("scheduler-time");
    const dayButtons = document.querySelectorAll(".day-btn");
    const btnSaveSchedule = document.getElementById("btn-save-schedule");
    
    const selectedDays = [];
    dayButtons.forEach(btn => {
        if (btn.classList.contains("active")) {
            selectedDays.push(parseInt(btn.getAttribute("data-day")));
        }
    });
    
    const startIdxVal = document.getElementById("scheduler-start-idx").value;
    const endIdxVal = document.getElementById("scheduler-end-idx").value;
    
    const payload = {
        id: currentAccountId,
        config: {
            start_index: startIdxVal ? parseInt(startIdxVal) : null,
            end_index: endIdxVal ? parseInt(endIdxVal) : null,
            schedule: {
                enabled: schedulerEnabled.checked,
                time: schedulerTime.value,
                days: selectedDays
            }
        }
    };
    
    const originalContent = btnSaveSchedule.innerHTML;
    btnSaveSchedule.disabled = true;
    btnSaveSchedule.innerHTML = `<i data-lucide="loader" class="animate-spin" style="width:14px; height:14px; margin-right:6px; display:inline-block; vertical-align:middle;"></i> Saving...`;
    lucide.createIcons();
    
    appendLogToConsole("Updating account schedule settings on backend...", "info");
    
    try {
        const response = await fetch(`${API_BASE}/accounts/update-config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const res = await response.json();
        
        if (res.status === "success") {
            btnSaveSchedule.innerHTML = `<i data-lucide="check" style="width:14px; height:14px; margin-right:6px;"></i> Saved`;
            btnSaveSchedule.style.backgroundColor = "#22c55e";
            
            appendLogToConsole("Account schedule settings updated successfully.", "success");
            await fetchAccountsRegistry();
            
            setTimeout(() => {
                btnSaveSchedule.disabled = true; // Disable until next change
                btnSaveSchedule.innerHTML = originalContent;
                btnSaveSchedule.style.backgroundColor = "";
                lucide.createIcons();
            }, 2000);
        } else {
            throw new Error(res.error);
        }
    } catch (e) {
        btnSaveSchedule.disabled = false;
        btnSaveSchedule.innerHTML = originalContent;
        lucide.createIcons();
        appendLogToConsole(`Failed updating schedule: ${e.message}`, "error");
        alert(`Error updating schedule: ${e.message}`);
    }
}

// ==========================================================================
// INLINE WORKSPACE RENAME FUNCTIONS
// ==========================================================================
function startInlineRename() {
    // Show edit row, hide display row
    workspaceTitleInput.value = workspaceTitle.textContent.replace(" Workspace", "").trim();
    workspaceTitleDisplayRow.style.display = "none";
    workspaceTitleEditRow.style.display = "flex";
    workspaceTitleInput.focus();
    workspaceTitleInput.select();
}

function cancelInlineRename() {
    workspaceTitleEditRow.style.display = "none";
    workspaceTitleDisplayRow.style.display = "flex";
}

async function confirmInlineRename() {
    const newName = workspaceTitleInput.value.trim();
    if (!newName) {
        workspaceTitleInput.style.borderColor = "#ef4444";
        workspaceTitleInput.focus();
        setTimeout(() => { workspaceTitleInput.style.borderColor = ""; }, 1500);
        return;
    }
    
    // Optimistically update the display
    cancelInlineRename();
    workspaceTitle.textContent = `${newName} Workspace`;
    
    // Persist to backend
    try {
        const response = await fetch(`${API_BASE}/accounts/update-config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: currentAccountId, name: newName })
        });
        const res = await response.json();
        
        if (res.status === "success") {
            appendLogToConsole(`Account renamed to "${newName}" successfully.`, "success");
            await fetchAccountsRegistry();
        } else {
            throw new Error(res.error);
        }
    } catch (e) {
        appendLogToConsole(`Failed renaming account: ${e.message}`, "error");
        // Revert title on error
        const acc = accountsRegistry.find(a => a.id === currentAccountId);
        if (acc) workspaceTitle.textContent = `${acc.name} Workspace`;
    }
}

// ==========================================================================
// WORKSPACE SPECIFIC ACTIVE POLLED STATES (GET /api/state?account_id=...)
// ==========================================================================
async function fetchWorkspaceState() {
    if (currentAccountId === "admin") return;
    try {
        const response = await fetch(`${API_BASE}/state?account_id=${currentAccountId}`);
        if (!response.ok) return;
        
        const state = await response.json();
        isSystemRunning = state.is_running;
        
        if (isSystemRunning) {
            systemStatusDot.className = "pulse-dot running";
            systemStatusText.textContent = `Running: ${state.current_action}`;
            btnStart.disabled = true;
            btnStop.disabled = false;
            btnLaunchLogin.disabled = true;
            btnSync.disabled = true;
            btnResetContacts.disabled = true;
            excelDropZone.style.pointerEvents = "none";
            excelDropZone.style.opacity = "0.5";
        } else {
            systemStatusDot.className = "pulse-dot";
            systemStatusText.textContent = "System Idle";
            btnStart.disabled = localContacts.length === 0;
            btnStop.disabled = true;
            btnLaunchLogin.disabled = false;
            btnSync.disabled = false;
            btnResetContacts.disabled = false;
            excelDropZone.style.pointerEvents = "auto";
            excelDropZone.style.opacity = "1";
        }
        
        // Refresh logging stream console
        updateLogsPanel(state.logs);
    } catch (e) {
        console.error("Error fetching workspace state:", e);
    }
}

// ==========================================================================
// EXCEL PARSING & SINGLE ADD API CALLS (Requires account_id param)
// ==========================================================================
async function uploadExcelFile(file) {
    if (currentAccountId === "admin") return;
    if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        alert("Invalid file format. Please upload an Excel sheet (.xlsx or .xls).");
        return;
    }
    
    appendLogToConsole(`Uploading spreadsheet: ${file.name}...`, "info");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("account_id", currentAccountId);
    
    try {
        excelDropZone.classList.add("dragover");
        excelDropZone.querySelector(".drop-zone-text").textContent = "Uploading & parsing sheet...";
        
        const response = await fetch(`${API_BASE}/upload`, {
            method: "POST",
            body: formData
        });
        const res = await response.json();
        
        excelDropZone.classList.remove("dragover");
        excelDropZone.querySelector(".drop-zone-text").textContent = "Drag & drop your Excel file here or click to browse";
        excelFileInput.value = "";
        
        if (res.status === "success") {
            const added = res.added_count || 0;
            const dups = res.skipped_duplicates || 0;
            const invalid = res.skipped_invalid || 0;
            
            let msg = `✅ Added: ${added} new contacts`;
            if (dups > 0) msg += `\n⚠️ Skipped ${dups} duplicates (already in database)`;
            if (invalid > 0) msg += `\n❌ Skipped ${invalid} invalid LinkedIn URLs`;
            
            appendLogToConsole(`Excel import done — Added: ${added} | Duplicates: ${dups} | Invalid: ${invalid}`, added > 0 ? "success" : "warning");
            alert(msg);
            await fetchWorkspaceContacts();
        } else {
            appendLogToConsole(`Import failed: ${res.error}`, "error");
            alert(`Excel loading failed: ${res.error}`);
        }
    } catch (e) {
        appendLogToConsole("Network error uploading Excel file.", "error");
        excelDropZone.classList.remove("dragover");
        excelDropZone.querySelector(".drop-zone-text").textContent = "Drag & drop your Excel file here or click to browse";
    }
}

async function addSingleContact() {
    if (currentAccountId === "admin") return;
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
                account_id: currentAccountId,
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
            await fetchWorkspaceContacts();
        } else {
            appendLogToConsole(`Failed to add profile: ${res.error}`, "error");
            alert(`Error: ${res.error}`);
        }
    } catch (e) {
        appendLogToConsole("Network connection error adding contact.", "error");
        btnQuickAdd.disabled = false;
    }
}

// ==========================================================================
// WORKSPACE OPERATIONAL QUEUE TRIGGERS
// ==========================================================================
async function launchLoginBrowser() {
    if (currentAccountId === "admin") return;
    btnLaunchLogin.disabled = true;
    appendLogToConsole("Requestingheaded Playwright browser launch for manual login setup...", "info");
    try {
        const response = await fetch(`${API_BASE}/launch-login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_id: currentAccountId })
        });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole("Playwright browser window spawned! Please login to your LinkedIn profile.", "success");
            await fetchWorkspaceState();
        } else {
            appendLogToConsole(`Browser launch failed: ${res.error}`, "error");
            btnLaunchLogin.disabled = false;
        }
    } catch (e) {
        appendLogToConsole("Network connection error spawning login browser.", "error");
        btnLaunchLogin.disabled = false;
    }
}

async function checkWorkspaceLoginSession() {
    if (currentAccountId === "admin") return;
    
    btnCheckLogin.disabled = true;
    const originalText = btnCheckLogin.innerHTML;
    btnCheckLogin.innerHTML = `<i data-lucide="loader" class="animate-spin" style="width:14px; height:14px; margin-right:6px; display:inline-block; vertical-align:middle;"></i> Checking...`;
    lucide.createIcons();
    
    appendLogToConsole("Requesting headless LinkedIn login status verification...", "info");
    
    try {
        const response = await fetch(`${API_BASE}/accounts/check-login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_id: currentAccountId })
        });
        const res = await response.json();
        
        btnCheckLogin.disabled = false;
        btnCheckLogin.innerHTML = originalText;
        lucide.createIcons();
        
        if (res.status === "success") {
            if (res.logged_in) {
                appendLogToConsole("LinkedIn Login Check: ACTIVE SESSION (Authenticated)", "success");
                alert("Session Check: Stored cookies are active and logged in!");
            } else {
                appendLogToConsole("LinkedIn Login Check: EXPIRED OR LOGGED OUT", "warning");
                alert("Session Check: Logged out! Please launch the browser and sign in again.");
            }
        } else {
            appendLogToConsole(`Login check failed: ${res.error}`, "error");
            alert(`Error checking session: ${res.error}`);
        }
    } catch (e) {
        appendLogToConsole("Network connection error checking login session.", "error");
        btnCheckLogin.disabled = false;
        btnCheckLogin.innerHTML = originalText;
        lucide.createIcons();
    }
}

async function deleteAccountProfile(accountId) {
    if (accountId === "default" || accountId === "admin") {
        alert("The primary default profile cannot be deleted.");
        return;
    }
    
    // Find account name
    const acc = accountsRegistry.find(a => a.id === accountId);
    const displayName = acc ? acc.name : accountId;
    
    if (!confirm(`Are you absolutely sure you want to delete account "${displayName}"?\nThis will permanently erase its session cookies and prospects database list!`)) {
        return;
    }
    
    appendLogToConsole(`Requesting registry deletion of account profile: ${displayName}...`, "warning");
    
    try {
        const response = await fetch(`${API_BASE}/accounts/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: accountId })
        });
        const res = await response.json();
        
        if (res.status === "success") {
            appendLogToConsole(`Account profile "${displayName}" successfully removed from the platform.`, "success");
            alert(`Successfully deleted account: ${displayName}`);
            
            // If deleting the currently viewed workspace, swap back to admin dashboard
            if (currentAccountId === accountId) {
                await switchWorkspace("admin");
            } else {
                await fetchAccountsRegistry();
            }
        } else {
            appendLogToConsole(`Failed deleting account profile: ${res.error}`, "error");
            alert(`Delete Error: ${res.error}`);
        }
    } catch (e) {
        appendLogToConsole("Network connection error deleting account profile.", "error");
    }
}

async function startWorkspaceAutomation() {
    if (currentAccountId === "admin") return;
    const minDelay = parseInt(delayMinInput.value) || 30;
    const maxDelay = parseInt(delayMaxInput.value) || 70;
    const dailyLimit = parseInt(dailyLimitInput.value) || 25;
    const weeklyLimit = parseInt(weeklyLimitInput.value) || 150;
    
    if (minDelay < 10) {
        alert("Minimum safe delay constraint cannot be less than 10 seconds.");
        return;
    }
    if (maxDelay < minDelay) {
        alert("Maximum delay must be equal to or greater than minimum delay.");
        return;
    }
    
    const sIdxText = rangeStartInput.value.trim();
    const eIdxText = rangeEndInput.value.trim();
    let startIndex = sIdxText !== "" ? parseInt(sIdxText) : null;
    let endIndex = eIdxText !== "" ? parseInt(eIdxText) : null;
    
    if (startIndex !== null && (isNaN(startIndex) || startIndex < 1)) {
        alert("Starting range index must be a positive integer.");
        return;
    }
    if (endIndex !== null && (isNaN(endIndex) || endIndex < 1)) {
        alert("Ending range index must be a positive integer.");
        return;
    }
    if (startIndex !== null && endIndex !== null && startIndex > endIndex) {
        alert("Starting index cannot be larger than ending index.");
        return;
    }
    
    btnStart.disabled = true;
    appendLogToConsole("Adding workspace automation task to sequential queue worker...", "info");
    
    const payload = {
        account_id: currentAccountId,
        note_template: noteTemplateTextarea.value,
        send_with_note: sendWithNoteCheckbox.checked,
        delay_min: minDelay,
        delay_max: maxDelay,
        daily_limit: dailyLimit,
        weekly_limit: weeklyLimit,
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
            appendLogToConsole("Task successfully queued. Playwright background process dispatched shortly.", "success");
            await fetchWorkspaceState();
        } else {
            appendLogToConsole(`Failed queueing worker: ${res.error}`, "error");
            alert(`Automation error: ${res.error}`);
            btnStart.disabled = false;
        }
    } catch (e) {
        appendLogToConsole("Network connection error starting automation queue.", "error");
        btnStart.disabled = false;
    }
}

async function stopWorkspaceAutomation() {
    if (currentAccountId === "admin") return;
    appendLogToConsole("Dispatching pause/stop signal to workspace thread...", "warning");
    try {
        const response = await fetch(`${API_BASE}/stop`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_id: currentAccountId })
        });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole("Stop signal acknowledged. Browser threads closing down.", "info");
        }
    } catch (e) {
        appendLogToConsole("Network connection error stopping automation.", "error");
    }
}

async function syncAcceptedRequests() {
    if (currentAccountId === "admin") return;
    btnSync.disabled = true;
    appendLogToConsole("Queueing acceptance synchronization session...", "info");
    try {
        const response = await fetch(`${API_BASE}/sync-acceptance`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_id: currentAccountId })
        });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole("Acceptance sync task added to sequential execution thread.", "info");
            await fetchWorkspaceState();
        } else {
            appendLogToConsole(`Failed dispatching sync: ${res.error}`, "error");
            btnSync.disabled = false;
        }
    } catch (e) {
        appendLogToConsole("Network connection error running sync.", "error");
        btnSync.disabled = false;
    }
}

// ==========================================================================
// WORKSPACE DATABASE UTILITIES & FILTERED RENDERS
// ==========================================================================
async function fetchWorkspaceContacts() {
    if (currentAccountId === "admin") return;
    try {
        const response = await fetch(`${API_BASE}/contacts?account_id=${currentAccountId}`);
        if (!response.ok) return;
        
        localContacts = await response.json();
        currentFilteredContacts = localContacts;
        
        refreshWorkspaceStats();
        renderWorkspaceTable();
        
        if (!isSystemRunning) {
            btnStart.disabled = localContacts.length === 0;
        }
    } catch (e) {
        console.error("Failed fetching contacts:", e);
    }
}

function refreshWorkspaceStats(contactsList = currentFilteredContacts) {
    const total = contactsList.length;
    const pending = contactsList.filter(c => c.status === "Pending").length;
    const connected = contactsList.filter(c => c.status === "Connected").length;
    
    // Total requests sent are computed from Sent, Pending, or Connected statuses
    const sent = contactsList.filter(c => ["Sent", "Pending", "Connected"].includes(c.status)).length;
    
    statTotal.textContent = total;
    statSent.textContent = sent;
    statPending.textContent = pending;
    statConnected.textContent = connected;
    
    // Average Sent/Day calculation
    const sentWithDates = contactsList.filter(c => ["Sent", "Pending", "Connected"].includes(c.status) && c.date_sent);
    const uniqueDays = new Set(sentWithDates.map(c => c.date_sent.split(" ")[0]).filter(Boolean));
    const activeDays = uniqueDays.size;
    const avgPerDay = activeDays > 0 ? (sent / activeDays).toFixed(1) : "0.0";
    
    const avgDayNumEl = statAvgDay.childNodes[0];
    if (avgDayNumEl) avgDayNumEl.textContent = avgPerDay;
    
    // Acceptance rate
    const acceptRate = sent > 0 ? Math.round((connected / sent) * 100) : 0;
    const acceptRateNumEl = statAcceptRate.childNodes[0];
    if (acceptRateNumEl) acceptRateNumEl.textContent = acceptRate;
    
    acceptRateBar.style.width = `${acceptRate}%`;
    contactsCountSpan.textContent = `${total} contact${total !== 1 ? 's' : ''}`;
    
    // Helper parsers for sent quotas
    function parseSentDate(c) {
        if (!c.date_sent) return null;
        const pts = c.date_sent.split(" ")[0].split("-");
        if (pts.length !== 3) return null;
        return new Date(parseInt(pts[0]), parseInt(pts[1]) - 1, parseInt(pts[2]));
    }
    
    const today = new Date();
    today.setHours(0,0,0,0);
    
    const sentTodayCount = localContacts.filter(c => {
        const d = parseSentDate(c);
        if (!d) return false;
        d.setHours(0,0,0,0);
        return d.toDateString() === today.toDateString();
    }).length;
    
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    sevenDaysAgo.setHours(0,0,0,0);
    
    const sentThisWeekCount = localContacts.filter(c => {
        const d = parseSentDate(c);
        if (!d) return false;
        d.setHours(0,0,0,0);
        return d >= sevenDaysAgo;
    }).length;
    
    // Draw Daily Quotas
    const dailyLimit = parseInt(dailyLimitInput.value) || 25;
    quotaDailyCurrent.textContent = sentTodayCount;
    quotaDailyMax.textContent = dailyLimit;
    
    const dailyPercent = Math.min((sentTodayCount / dailyLimit) * 100, 100);
    quotaDailyBar.style.width = `${dailyPercent}%`;
    if (dailyPercent >= 90) quotaDailyBar.style.background = "var(--status-danger)";
    else if (dailyPercent >= 70) quotaDailyBar.style.background = "var(--status-warning)";
    else quotaDailyBar.style.background = "linear-gradient(to right, var(--accent-blue), var(--accent-purple))";
    
    // Draw Weekly Quotas
    const weeklyLimit = parseInt(weeklyLimitInput.value) || 150;
    quotaWeeklyCurrent.textContent = sentThisWeekCount;
    quotaWeeklyMax.textContent = weeklyLimit;
    
    const weeklyPercent = Math.min((sentThisWeekCount / weeklyLimit) * 100, 100);
    quotaWeeklyBar.style.width = `${weeklyPercent}%`;
    if (weeklyPercent >= 90) quotaWeeklyBar.style.background = "var(--status-danger)";
    else if (weeklyPercent >= 70) quotaWeeklyBar.style.background = "var(--status-warning)";
    else quotaWeeklyBar.style.background = "linear-gradient(to right, var(--accent-blue), var(--accent-purple))";
}

function renderWorkspaceTable() {
    const query = tableSearchInput.value.toLowerCase().trim();
    const filter = statusFilterSelect.value;
    const dateFilter = dateFilterSelect.value;
    
    // Helper date parse
    function getProspectActionDate(c) {
        const raw = c.date_accepted || c.date_sent;
        if (!raw) return null;
        const pts = raw.split(" ")[0].split("-");
        if (pts.length !== 3) return null;
        return new Date(parseInt(pts[0]), parseInt(pts[1]) - 1, parseInt(pts[2]));
    }
    
    // 1. Filter dates matches first to get dateFiltered
    let dateFiltered = localContacts;
    if (dateFilter !== "all") {
        const now = new Date();
        now.setHours(0,0,0,0);
        
        dateFiltered = localContacts.filter(c => {
            const d = getProspectActionDate(c);
            if (!d) return false;
            d.setHours(0,0,0,0);
            
            if (dateFilter === "today") {
                return d.toDateString() === now.toDateString();
            } else if (dateFilter === "yesterday") {
                const yesterday = new Date();
                yesterday.setDate(yesterday.getDate() - 1);
                return d.toDateString() === yesterday.toDateString();
            } else if (dateFilter === "week") {
                const weekAgo = new Date();
                weekAgo.setDate(weekAgo.getDate() - 7);
                weekAgo.setHours(0,0,0,0);
                return d >= weekAgo;
            } else if (dateFilter === "month") {
                const monthAgo = new Date();
                monthAgo.setDate(monthAgo.getDate() - 30);
                monthAgo.setHours(0,0,0,0);
                return d >= monthAgo;
            } else if (dateFilter === "custom") {
                if (customStartDateInput.value) {
                    const sPts = customStartDateInput.value.split("-");
                    const startD = new Date(parseInt(sPts[0]), parseInt(sPts[1]) - 1, parseInt(sPts[2]));
                    startD.setHours(0,0,0,0);
                    if (d < startD) return false;
                }
                if (customEndDateInput.value) {
                    const ePts = customEndDateInput.value.split("-");
                    const endD = new Date(parseInt(ePts[0]), parseInt(ePts[1]) - 1, parseInt(ePts[2]));
                    endD.setHours(23,59,59,999);
                    if (d > endD) return false;
                }
                return true;
            }
            return true;
        });
    }
    
    // Update global reference and update statistics cards
    currentFilteredContacts = dateFiltered;
    refreshWorkspaceStats(currentFilteredContacts);
    
    // 2. Further filter the table view based on Status and Search Query
    let filtered = currentFilteredContacts;
    
    // Filter status matches
    if (filter !== "all") {
        filtered = filtered.filter(c => c.status === filter);
    }
    
    // Query string filters
    if (query) {
        filtered = filtered.filter(c => 
            c.name.toLowerCase().includes(query) ||
            (c.company && c.company.toLowerCase().includes(query)) ||
            (c.title && c.title.toLowerCase().includes(query)) ||
            c.profile_url.toLowerCase().includes(query) ||
            (c.email && c.email.toLowerCase().includes(query)) ||
            (c.phone && c.phone.toLowerCase().includes(query))
        );
    }
    
    if (filtered.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-table-state">
                    <div class="empty-state-content">
                        <i data-lucide="search-code"></i>
                        <p>${localContacts.length === 0 ? 'No prospect loaded yet.' : 'No matching results found.'}</p>
                        <span class="sub-text">${localContacts.length === 0 ? 'Drag and drop an Excel list into the sidebar controls to import.' : 'Adjust search terms or filters.'}</span>
                    </div>
                </td>
            </tr>
        `;
        lucide.createIcons();
        return;
    }
    
    // Construct Rows
    let html = "";
    filtered.forEach(c => {
        const originalIndex = localContacts.indexOf(c) + 1;
        const statusClass = c.status.toLowerCase().replace(" ", "-");
        
        let iconName = "help-circle";
        if (c.status === "Connected") iconName = "check-circle2";
        else if (c.status === "Pending") iconName = "clock";
        else if (c.status === "Sent") iconName = "send";
        else if (c.status === "Not Started") iconName = "play";
        else if (c.status === "Failed") iconName = "alert-triangle";
        
        let dateVal = "—";
        if (c.status === "Connected" && c.date_accepted) {
            dateVal = c.date_accepted.split(" ")[0];
        } else if (c.date_sent) {
            dateVal = c.date_sent.split(" ")[0];
        }
        
        html += `
            <tr>
                <td style="text-align: center; font-weight: 600; color: var(--text-muted);">${originalIndex}</td>
                <td>
                    <div class="lead-name-cell">
                        <span class="lead-name">${c.name}</span>
                        <span class="lead-title">${c.title || 'Prospect'}</span>
                    </div>
                </td>
                <td><span class="lead-company">${c.company || '—'}</span></td>
                <td>
                    <a href="${c.profile_url}" target="_blank" class="profile-link">
                        View Profile <i data-lucide="external-link"></i>
                    </a>
                </td>
                <td>
                    <div class="contact-details-cell">
                        <span class="contact-email" title="${c.email || 'No email shared'}">
                            <i data-lucide="mail"></i> ${c.email || '—'}
                        </span>
                        <span class="contact-phone" title="${c.phone || 'No phone number shared'}">
                            <i data-lucide="phone"></i> ${c.phone || '—'}
                        </span>
                    </div>
                </td>
                <td>
                    <span class="status-badge ${statusClass}" title="${c.logs || ''}">
                        <i data-lucide="${iconName}"></i> ${c.status}
                    </span>
                </td>
                <td class="date-cell">${dateVal}</td>
                <td style="text-align: center;">
                    <button class="btn-icon-only delete-prospect-btn" data-url="${c.profile_url}" title="Remove lead profile">
                        <i data-lucide="trash-2" style="width: 15px; height: 15px;"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    tableBody.innerHTML = html;
    lucide.createIcons();
}

// Opens the reset modal — no action until user clicks a button
function resetProspectsStatus() {
    if (currentAccountId === "admin") return;
    const overlay = document.getElementById("reset-modal-overlay");
    overlay.style.display = "flex";
    lucide.createIcons();
}

// Internal function that actually performs the reset after user picks a scope
async function executeReset(scope) {
    const overlay = document.getElementById("reset-modal-overlay");
    overlay.style.display = "none";
    
    const labels = { failed: "Failed", pending: "Pending", all: "ALL" };
    appendLogToConsole(`Resetting ${labels[scope]} contacts to "Not Started"...`, "warning");
    try {
        const response = await fetch(`${API_BASE}/contacts/reset`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_id: currentAccountId, scope: scope })
        });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole(`Reset complete. ${res.reset_count || ""} contacts updated.`, "success");
            await fetchWorkspaceContacts();
        } else {
            appendLogToConsole(`Reset failed: ${res.error}`, "error");
        }
    } catch (e) {
        appendLogToConsole("Network error resetting contacts.", "error");
    }
}

// Wire up reset modal buttons (called once in DOMContentLoaded)
function setupResetModal() {
    document.getElementById("btn-reset-failed-only").addEventListener("click", () => executeReset("failed"));
    document.getElementById("btn-reset-pending-only").addEventListener("click", () => executeReset("pending"));
    document.getElementById("btn-reset-all-confirm").addEventListener("click", () => executeReset("all"));
    document.getElementById("btn-reset-modal-cancel").addEventListener("click", () => {
        document.getElementById("reset-modal-overlay").style.display = "none";
    });
    document.getElementById("reset-modal-overlay").addEventListener("click", (e) => {
        if (e.target === document.getElementById("reset-modal-overlay")) {
            document.getElementById("reset-modal-overlay").style.display = "none";
        }
    });
}

async function adminClearDatabases() {
    const pass = prompt("Enter Administrator Password to delete databases:");
    if (pass !== "admin123") {
        alert("Permission Denied.");
        return;
    }
    
    if (selectedAccountIdsForBulk.size === 0) {
        alert("Please select at least one account to delete its database.");
        return;
    }

    if (!confirm(`Are you sure you want to permanently delete databases for ${selectedAccountIdsForBulk.size} selected account(s)?`)) return;
    
    const btn = document.getElementById("btn-admin-clear-db");
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader" class="animate-spin" style="width:14px; height:14px; margin-right:6px; display:inline-block; vertical-align:middle;"></i> Deleting...`;
    lucide.createIcons();

    try {
        for (const accountId of selectedAccountIdsForBulk) {
            await fetch(`${API_BASE}/contacts/clear`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ account_id: accountId })
            });
        }
        alert("Databases successfully deleted.");
        // Uncheck all and refresh
        selectedAccountIdsForBulk.clear();
        const selectAllCheckbox = document.getElementById("checkbox-select-all-accounts");
        if (selectAllCheckbox) selectAllCheckbox.checked = false;
        await refreshAccountsRegistry();
        renderAdminDashboardView();
    } catch (e) {
        alert("Network error while deleting databases.");
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
        lucide.createIcons();
    }
}


async function handleProspectTableClick(e) {
    const deleteBtn = e.target.closest(".delete-prospect-btn");
    if (!deleteBtn) return;
    
    if (isSystemRunning) {
        alert("Cannot delete contacts while automation is running.");
        return;
    }
    
    const profileUrl = deleteBtn.getAttribute("data-url");
    if (!profileUrl) return;
    
    const tr = deleteBtn.closest("tr");
    const name = tr.querySelector(".lead-name").textContent;
    
    if (!confirm(`Remove "${name}" from database list?`)) return;
    
    deleteBtn.disabled = true;
    try {
        const response = await fetch(`${API_BASE}/contacts/delete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ account_id: currentAccountId, profile_url: profileUrl })
        });
        const res = await response.json();
        if (res.status === "success") {
            appendLogToConsole(`Removed prospect profile: ${name}`, "warning");
            await fetchWorkspaceContacts();
        } else {
            alert(`Error: ${res.error}`);
            deleteBtn.disabled = false;
        }
    } catch (e) {
        appendLogToConsole("Network connection error deleting contact.", "error");
        deleteBtn.disabled = false;
    }
}

// ==========================================================================
// CONSOLE PANEL LOGGER STREAM
// ==========================================================================
function updateLogsPanel(logs) {
    if (logs.length === localLogs.length) return;
    const freshLogs = logs.slice(localLogs.length);
    localLogs = logs;
    
    freshLogs.forEach(entry => {
        const line = document.createElement("div");
        line.className = `log-line ${entry.type}`;
        line.innerHTML = `<span class="log-time">[${entry.time}]</span> ${entry.message}`;
        consoleOutput.appendChild(line);
    });
    
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
    consoleOutput.innerHTML = `<div class="log-line info"><span class="log-time">[${new Date().toTimeString().split(' ')[0]}]</span> Console logs cleared.</div>`;
}

// ==========================================================================
// DRAG AND DROP MANUAL ACCOUNT SHUFFLE / REORDER SYSTEM
// ==========================================================================
let dragSrcRow = null;

function setupRowDragAndDrop() {
    const rows = adminAccountsTableBody.querySelectorAll(".draggable-row");
    rows.forEach(row => {
        row.addEventListener('dragstart', handleDragStart, false);
        row.addEventListener('dragenter', handleDragEnter, false);
        row.addEventListener('dragover', handleDragOver, false);
        row.addEventListener('dragleave', handleDragLeave, false);
        row.addEventListener('drop', handleDrop, false);
        row.addEventListener('dragend', handleDragEnd, false);
    });
}

function handleDragStart(e) {
    dragSrcRow = this;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', this.getAttribute('data-id'));
    this.classList.add('drag-active');
}

function handleDragOver(e) {
    if (e.preventDefault) {
        e.preventDefault();
    }
    e.dataTransfer.dropEffect = 'move';
    return false;
}

function handleDragEnter(e) {
    this.classList.add('drag-over');
}

function handleDragLeave(e) {
    this.classList.remove('drag-over');
}

async function handleDrop(e) {
    e.stopPropagation();
    this.classList.remove('drag-over');
    
    if (dragSrcRow !== this) {
        const srcId = dragSrcRow.getAttribute('data-id');
        const targetId = this.getAttribute('data-id');
        
        const srcIndex = accountsRegistry.findIndex(a => a.id === srcId);
        const targetIndex = accountsRegistry.findIndex(a => a.id === targetId);
        
        if (srcIndex !== -1 && targetIndex !== -1) {
            // Reorder the local array
            const [movedAcc] = accountsRegistry.splice(srcIndex, 1);
            accountsRegistry.splice(targetIndex, 0, movedAcc);
            
            // Record custom order
            accountsCustomOrder = accountsRegistry.map(a => a.id);
            
            // Save to backend persistently
            await saveAccountsOrderToServer(accountsCustomOrder);
            
            // Re-render views immediately
            renderSidebarAccounts();
            renderAdminDashboardView();
        }
    }
    return false;
}

function handleDragEnd(e) {
    this.classList.remove('drag-active');
    document.querySelectorAll('.draggable-row').forEach(row => {
        row.classList.remove('drag-over');
    });
}

async function saveAccountsOrderToServer(orderList) {
    try {
        await fetch(`${API_BASE}/accounts/reorder`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ order: orderList })
        });
    } catch (e) {
        console.error("Failed persisting manual shuffle sequence to backend:", e);
    }
}
