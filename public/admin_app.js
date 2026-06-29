document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    fetchStats();
    fetchLeads();

    document.getElementById('searchInput').addEventListener('input', filterLeads);
    document.getElementById('statusFilter').addEventListener('change', filterLeads);
    document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);
});

function initTheme() {
    const savedTheme = localStorage.getItem('admin-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('admin-theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const iconBtn = document.getElementById('themeToggleBtn');
    if (theme === 'light') {
        iconBtn.innerHTML = '<i class="fa-solid fa-sun"></i>';
    } else {
        iconBtn.innerHTML = '<i class="fa-solid fa-moon"></i>';
    }
}

let allLeads = [];

async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();
        
        document.getElementById('valTotalLeads').innerText = data.totalLeads;
        document.getElementById('valHotLeads').innerText = data.hotLeads;
        document.getElementById('valActiveChats').innerText = data.activeConversations;
        document.getElementById('valAvgScore').innerText = data.averageScore;
    } catch (error) {
        console.error("Error fetching stats:", error);
    }
}

async function fetchLeads() {
    try {
        const response = await fetch('/api/leads');
        allLeads = await response.json();
        renderLeads(allLeads);
    } catch (error) {
        console.error("Error fetching leads:", error);
    }
}

function filterLeads() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;

    const filtered = allLeads.filter(lead => {
        const name = (lead.name || "").toLowerCase();
        const title = (lead.title || "").toLowerCase();
        const matchesSearch = name.includes(searchTerm) || title.includes(searchTerm);
        
        const status = lead.status || "Cold";
        const matchesStatus = statusFilter === 'all' || status === statusFilter;

        return matchesSearch && matchesStatus;
    });

    renderLeads(filtered);
}

function getStatusClass(status) {
    if (status === 'SQL') return 'status-sql';
    if (status === 'Hot') return 'status-hot';
    if (status === 'Warm') return 'status-warm';
    return 'status-cold';
}

function getScoreColor(score) {
    if (score >= 80) return 'var(--accent-purple)';
    if (score >= 60) return 'var(--accent-green)';
    if (score >= 30) return 'var(--accent-orange)';
    return 'var(--text-muted)';
}

function renderLeads(leads) {
    const tbody = document.getElementById('leadsTableBody');
    tbody.innerHTML = '';

    if (leads.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">No leads found.</td></tr>';
        return;
    }

    // Sort leads by score descending
    const sortedLeads = [...leads].sort((a, b) => (b.score || 0) - (a.score || 0));

    sortedLeads.forEach(lead => {
        const tr = document.createElement('tr');
        
        const name = lead.name || 'Unknown';
        const initials = name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();
        const title = lead.title || 'Unknown Title';
        const url = lead.url || '#';
        const status = lead.status || 'Cold';
        const score = lead.score || 0;
        
        const scoreColor = getScoreColor(score);
        
        tr.innerHTML = `
            <td>
                <div class="lead-info-cell">
                    <div class="lead-avatar">${initials}</div>
                    <div>
                        <div class="lead-name">${name}</div>
                        <div class="lead-job">${title.substring(0, 50)}${title.length > 50 ? '...' : ''}</div>
                    </div>
                </div>
            </td>
            <td>
                <a href="${url}" target="_blank" class="linkedin-link">
                    <i class="fa-brands fa-linkedin"></i> Profile
                </a>
            </td>
            <td>
                <span class="status-badge ${getStatusClass(status)}">${status}</span>
            </td>
            <td>
                <div class="score-wrapper">
                    <div class="score-bar-container">
                        <div class="score-bar" style="width: ${score}%; background-color: ${scoreColor}"></div>
                    </div>
                    <span class="score-text" style="color: ${scoreColor}">${score}</span>
                </div>
            </td>
            <td>
                <button class="action-btn" title="View Details"><i class="fa-solid fa-ellipsis-vertical"></i></button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}
