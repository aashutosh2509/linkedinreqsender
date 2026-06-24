// Leads CRM Logic
const API_BASE = `${window.location.origin}/api`;
let accountsRegistry = [];
let leadsData = [];
let currentAccountId = "";
// DOM Elements
const sidebarAccountsList = document.getElementById("sidebar-accounts-list");
const tableBody = document.getElementById("leads-table-body");
const searchInput = document.getElementById("search-input");
const statusFilter = document.getElementById("status-filter");
const btnRefresh = document.getElementById("btn-refresh");
const btnTempExtract = document.getElementById("btn-temp-extract");
const statTotal = document.getElementById("stat-total-leads");
const statConnected = document.getElementById("stat-connected");
const statMessaged = document.getElementById("stat-messaged");
const statExtracted = document.getElementById("stat-extracted");

if (btnTempExtract) {
    btnTempExtract.addEventListener("click", async () => {
        if (!currentAccountId) return alert("Select an account first.");
        if (!confirm("Start extracting 15 new connections now?")) return;
        
        try {
            const res = await fetch(`${API_BASE}/extract-connections-temp`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ account_id: currentAccountId })
            });
            const data = await res.json();
            alert(data.message || "Extraction started.");
        } catch (e) {
            console.error(e);
            alert("Error starting extraction.");
        }
    });
}

// Initialize
async function init() {
    await fetchAccounts();
    if (accountsRegistry.length > 0) {
        // Find the default account and click it, or just use the first
        const firstBtn = sidebarAccountsList.querySelector(".account-item");
        if (firstBtn) firstBtn.click();
    } else {
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">No accounts found.</td></tr>';
    }
}
// Fetch Accounts for sidebar
async function fetchAccounts() {
    try {
        const response = await fetch(`${API_BASE}/accounts`);
        accountsRegistry = await response.json();
        
        sidebarAccountsList.innerHTML = "";
        accountsRegistry.forEach(acc => {
            let gradClass = "bg-blue";
            if (acc.id.includes("dhananjay")) gradClass = "bg-purple";
            else if (acc.id.includes("sneha")) gradClass = "bg-pink";
            else if (acc.id.includes("neha")) gradClass = "bg-teal";
            else if (acc.id.includes("sadnya")) gradClass = "bg-yellow";
            
            const btn = document.createElement("button");
            btn.className = "account-item";
            btn.dataset.accountId = acc.id;
            
            btn.innerHTML = `
                <div class="item-icon ${gradClass}"><i data-lucide="user"></i></div>
                <div class="item-info">
                    <span class="acc-name">${acc.name}</span>
                    <span class="acc-status"><span class="status-dot grey"></span> Idle</span>
                </div>
            `;
            
            btn.addEventListener("click", () => {
                // Update active state
                document.querySelectorAll("#sidebar-accounts-list .account-item").forEach(b => b.classList.remove("active"));
                btn.classList.add("active");
                
                currentAccountId = acc.id;
                fetchLeads();
                
                // Populate Scheduler UI
                if (schedulerEnabled) {
                    const cfg = acc.config || {};
                    const sched = cfg.extract_schedule || {};
                    const isEnabled = sched.enabled || false;
                    
                    schedulerEnabled.checked = isEnabled;
                    schedulerConfig.style.display = isEnabled ? "block" : "none";
                    schedulerTime.value = sched.time || "10:00";
                    
                    const activeDays = sched.days || [];
                    dayButtons.forEach(db => {
                        const dayVal = parseInt(db.getAttribute("data-day"));
                        if (activeDays.includes(dayVal)) db.classList.add("active");
                        else db.classList.remove("active");
                    });
                    
                    btnSaveSchedule.disabled = true;
                }
            });
            
            sidebarAccountsList.appendChild(btn);
        });
        
        lucide.createIcons();
    } catch (e) {
        console.error("Error fetching accounts:", e);
    }
}
// Fetch Leads Data
async function fetchLeads() {
    if (!currentAccountId) return;
    
    tableBody.innerHTML = `<tr><td colspan="5" class="empty-state"><i data-lucide="loader" class="animate-spin" style="margin: 0 auto; display: block; margin-bottom: 12px; color: var(--accent-blue);"></i><p>Loading Leads...</p></td></tr>`;
    lucide.createIcons();
    
    try {
        const response = await fetch(`${API_BASE}/contacts?account_id=${currentAccountId}`);
        const rawData = await response.json();
        
        // strictly filter to ONLY Hot Pipeline (Connected or Extracted)
        leadsData = rawData.filter(l => l.status === "Connected" || l.status === "Extracted");
        
        renderTable();
    } catch (e) {
        console.error("Error fetching leads:", e);
        tableBody.innerHTML = '<tr><td colspan="5" class="empty-state">Error loading leads data.</td></tr>';
    }
}
// Render Table
function renderTable() {
    const searchTerm = searchInput.value.toLowerCase();
    const filterStatus = statusFilter.value;
    
    let filtered = leadsData.filter(lead => {
        const name = (lead.name || "").toLowerCase();
        const title = (lead.title || "").toLowerCase();
        const stat = lead.status || "Not Started";
        
        if (searchTerm && !name.includes(searchTerm) && !title.includes(searchTerm)) return false;
        if (filterStatus !== "all" && stat !== filterStatus) return false;
        return true;
    });
    
    // Update Metrics
    statTotal.textContent = filtered.length;
    statConnected.textContent = filtered.filter(l => l.status === "Connected").length;
    statMessaged.textContent = filtered.filter(l => l.message_sent).length;
    statExtracted.textContent = filtered.filter(l => l.status === "Extracted").length;
    
    tableBody.innerHTML = "";
    
    if (filtered.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="5" class="empty-state">No leads found matching your criteria.</td></tr>`;
        return;
    }
    
    filtered.forEach((lead, idx) => {
        const status = lead.status || "Not Started";
        let statusClass = "";
        let statusIcon = "circle";
        
        if (status === "Connected") { statusClass = "success"; statusIcon = "check-circle2"; }
        else if (status === "Extracted") { statusClass = "hot"; statusIcon = "flame"; }
        else if (status === "Failed") { statusClass = "danger"; statusIcon = "x-circle"; }
        else if (status === "Pending") { statusClass = "warning"; statusIcon = "clock"; }
        else if (status === "Not Started") { statusClass = "info"; statusIcon = "minus-circle"; }
        
        let logsHtml = lead.logs || "-";
        if (lead.message_sent) {
            logsHtml += `<br><span style="color:var(--status-success); font-size: 0.8rem; margin-top: 4px; display: inline-block;"><i data-lucide="message-square" style="width: 12px; height: 12px;"></i> AI Message Sent</span>`;
        }
        
        let contactInfoHtml = "";
        if (lead.email && lead.email !== "Not Shared" && lead.email !== "") {
            contactInfoHtml += `<div style="margin-top: 6px; font-size: 0.8rem; color: var(--accent-blue); display: flex; align-items: center; gap: 4px;"><i data-lucide="mail" style="width:12px; height:12px;"></i> ${lead.email}</div>`;
        }
        if (lead.phone && lead.phone !== "Not Shared" && lead.phone !== "") {
            contactInfoHtml += `<div style="margin-top: 2px; font-size: 0.8rem; color: var(--status-success); display: flex; align-items: center; gap: 4px;"><i data-lucide="phone" style="width:12px; height:12px;"></i> ${lead.phone}</div>`;
        }
        if (lead.dob) {
            contactInfoHtml += `<div style="margin-top: 2px; font-size: 0.8rem; color: var(--text-muted); display: flex; align-items: center; gap: 4px;"><i data-lucide="gift" style="width:12px; height:12px;"></i> ${lead.dob}</div>`;
        }
        
        const dateAction = lead.date_accepted || lead.date_sent || "-";
        
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${idx + 1}</td>
            <td>
                <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 2px;">
                    <a href="${lead.profile_url}" target="_blank" style="color: inherit; text-decoration: none;">${lead.name || "Unknown"} <i data-lucide="external-link" style="width: 12px; height: 12px; opacity: 0.5;"></i></a>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); line-height: 1.3; margin-bottom: 4px;">
                    ${lead.company || lead.title || "No Title/Company"}
                </div>
                ${contactInfoHtml}
            </td>
            <td>
                <div class="status-badge ${statusClass}">
                    <i data-lucide="${statusIcon}"></i> ${status}
                </div>
            </td>
            <td style="font-size: 0.85rem; max-width: 300px;">${logsHtml}</td>
            <td style="font-size: 0.85rem; color: var(--text-secondary);">
                <div style="display:flex; align-items:center; gap:4px;"><i data-lucide="calendar" style="width:12px; height:12px;"></i> ${dateAction}</div>
            </td>
        `;
        tableBody.appendChild(tr);
    });
    
    lucide.createIcons();
}

// -------------------- SCHEDULER LOGIC --------------------
const schedulerEnabled = document.getElementById("scheduler-enabled");
const schedulerConfig = document.getElementById("scheduler-config-container");
const schedulerTime = document.getElementById("scheduler-time");
const btnSaveSchedule = document.getElementById("btn-save-schedule");
const dayButtons = document.querySelectorAll(".day-btn");

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
dayButtons.forEach(btn => {
    btn.addEventListener("click", () => {
        btn.classList.toggle("active");
        btnSaveSchedule.disabled = false;
    });
});

async function saveWorkspaceSchedule() {
    if (!currentAccountId) return alert("Select an account first");
    
    const selectedDays = [];
    dayButtons.forEach(btn => {
        if (btn.classList.contains("active")) {
            selectedDays.push(parseInt(btn.getAttribute("data-day")));
        }
    });
    
    const payload = {
        id: currentAccountId,
        config: {
            extract_schedule: {
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
    
    try {
        const res = await fetch(`${API_BASE}/accounts/update-config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === "success") {
            btnSaveSchedule.innerHTML = `<i data-lucide="check" style="width:14px; height:14px; margin-right:6px;"></i> Saved`;
            btnSaveSchedule.style.backgroundColor = "#22c55e";
            await fetchAccounts(); // Refresh accounts registry to get latest config
            setTimeout(() => {
                btnSaveSchedule.disabled = true;
                btnSaveSchedule.innerHTML = originalContent;
                btnSaveSchedule.style.backgroundColor = "";
                lucide.createIcons();
            }, 2000);
        } else {
            throw new Error(data.error);
        }
    } catch (e) {
        btnSaveSchedule.disabled = false;
        btnSaveSchedule.innerHTML = originalContent;
        lucide.createIcons();
        alert(`Error updating schedule: ${e.message}`);
    }
}

if (btnSaveSchedule) {
    btnSaveSchedule.addEventListener("click", saveWorkspaceSchedule);
}

const btnToggleScheduler = document.getElementById("btn-toggle-scheduler");
const mainGridContainer = document.getElementById("main-grid-container");
const schedulerCard = document.getElementById("scheduler-card");

if (btnToggleScheduler && mainGridContainer && schedulerCard) {
    btnToggleScheduler.addEventListener("click", () => {
        if (schedulerCard.style.display === "none") {
            schedulerCard.style.display = "block";
            mainGridContainer.style.gridTemplateColumns = "350px 1fr";
        } else {
            schedulerCard.style.display = "none";
            mainGridContainer.style.gridTemplateColumns = "1fr";
        }
    });
}

// Event Listeners
searchInput.addEventListener("input", renderTable);
statusFilter.addEventListener("change", renderTable);
btnRefresh.addEventListener("click", fetchLeads);

// Start
document.addEventListener("DOMContentLoaded", init);
