document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    fetchStats();
    fetchLeads();

    // Tab Navigation Logic
    const navOverview = document.getElementById('nav-overview');
    const navLeads = document.getElementById('nav-leads');
    const overviewSection = document.getElementById('overview-section');
    const leadsSection = document.getElementById('leads-section');

    function showTab(tab) {
        if (tab === 'leads') {
            if(overviewSection) overviewSection.style.display = 'none';
            if(leadsSection) leadsSection.style.display = 'block';
            if(navOverview) navOverview.classList.remove('active');
            if(navLeads) navLeads.classList.add('active');
            window.location.hash = 'leads';
        } else {
            if(overviewSection) overviewSection.style.display = 'block';
            if(leadsSection) leadsSection.style.display = 'none';
            if(navLeads) navLeads.classList.remove('active');
            if(navOverview) navOverview.classList.add('active');
            window.location.hash = 'overview';
        }
    }

    if (navOverview) {
        navOverview.addEventListener('click', (e) => {
            e.preventDefault();
            showTab('overview');
        });
    }

    if (navLeads) {
        navLeads.addEventListener('click', (e) => {
            e.preventDefault();
            showTab('leads');
        });
    }

    // Check hash on load
    if (window.location.hash === '#leads') {
        showTab('leads');
    }

    document.getElementById('searchInput').addEventListener('input', filterLeads);
    document.getElementById('statusFilter').addEventListener('change', filterLeads);
    document.getElementById('profileFilter').addEventListener('change', filterLeads);
    document.getElementById('chatFilter').addEventListener('change', filterLeads);
    document.getElementById('themeToggleBtn').addEventListener('click', toggleTheme);
});

function initTheme() {
    const savedTheme = localStorage.getItem('crm_theme') || localStorage.getItem('admin-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    if (savedTheme === 'light') {
        document.body.classList.add('light-mode');
    } else {
        document.body.classList.remove('light-mode');
    }
    updateThemeIcon(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('crm_theme', newTheme);
    localStorage.setItem('admin-theme', newTheme);
    
    if (newTheme === 'light') {
        document.body.classList.add('light-mode');
    } else {
        document.body.classList.remove('light-mode');
    }
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const iconBtn = document.getElementById('themeToggleBtn');
    if (!iconBtn) return;
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
        
        document.getElementById('valTotalLeads').textContent = data.totalLeads || 0;
        document.getElementById('valActiveChats').textContent = data.activeConversations || 0;
        document.getElementById('valAvgScore').textContent = data.averageScore || 0;
        document.getElementById('valHotLeads').textContent = data.hotLeads || 0;
        document.getElementById('valConnectedPeople').textContent = (data.systemInfo && data.systemInfo.connected) || 0;
    } catch (error) {
        console.error("Error fetching stats:", error);
    }
}

async function fetchLeads() {
    try {
        const response = await fetch('/api/leads');
        allLeads = await response.json();
        
        // Populate profile filter
        const profiles = new Set(allLeads.map(lead => lead.source_profile || "Unknown"));
        const profileSelect = document.getElementById('profileFilter');
        profileSelect.innerHTML = '<option value="all">All Profiles</option>';
        Array.from(profiles).sort().forEach(profile => {
            const option = document.createElement('option');
            option.value = profile;
            option.textContent = profile;
            profileSelect.appendChild(option);
        });
        
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
        
        const profile = lead.source_profile || "Unknown";
        const profileFilterVal = document.getElementById('profileFilter').value;
        const matchesProfile = profileFilterVal === 'all' || profile === profileFilterVal;

        let matchesChat = true;
        const chatFilterVal = document.getElementById('chatFilter').value;
        if (chatFilterVal !== 'all') {
            const dateMessaged = lead.date_messaged || lead.date_accepted;
            if (!dateMessaged) {
                matchesChat = false;
            } else {
                const today = new Date();
                // Replace space with T to ensure cross-browser parsing if it's YYYY-MM-DD HH:MM:SS
                const messagedDate = new Date(dateMessaged.replace(' ', 'T'));
                
                if (chatFilterVal === 'today') {
                    matchesChat = messagedDate.toDateString() === today.toDateString();
                } else if (chatFilterVal === 'yesterday') {
                    const yesterday = new Date(today);
                    yesterday.setDate(yesterday.getDate() - 1);
                    matchesChat = messagedDate.toDateString() === yesterday.toDateString();
                }
            }
        }

        return matchesSearch && matchesStatus && matchesProfile && matchesChat;
    });

    renderLeads(filtered);
}

function getStatusClass(status) {
    if (status === 'SQL') return 'status-sql';
    if (status === 'Hot') return 'status-hot';
    if (status === 'Warm') return 'status-warm';
    if (status === 'Connected') return 'status-connected';
    if (status === 'Extracted') return 'status-extracted';
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
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No leads found.</td></tr>';
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
        const profile = lead.source_profile || 'Unknown';
        const score = lead.score || 0;
        
        const scoreColor = getScoreColor(score);
        const meetingDate = lead.meeting_date || '<span style="color:var(--text-muted)">-</span>';
        
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
                <span style="font-size: 13px; font-weight: 500; color: var(--text-muted); background: rgba(255,255,255,0.05); padding: 4px 10px; border-radius: 12px; border: 1px solid var(--border-color);">${profile}</span>
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
                <span style="font-size: 13px; font-weight: 500; color: var(--text-color);">${meetingDate}</span>
            </td>
            <td>
                <button class="action-btn" title="View Details"><i class="fa-solid fa-ellipsis-vertical"></i></button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// --- Notifications Logic ---
document.addEventListener('DOMContentLoaded', () => {
    const notifBtn = document.getElementById('notifBtn');
    const notifDropdown = document.getElementById('notifDropdown');
    const notifBadge = document.getElementById('notifBadge');
    const notifBody = document.getElementById('notifBody');

    if (!notifBtn) return;

    // Toggle dropdown
    notifBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        if (notifDropdown.style.display === 'none' || notifDropdown.style.display === '') {
            notifDropdown.style.display = 'block';
        } else {
            notifDropdown.style.display = 'none';
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!notifBtn.contains(e.target) && !notifDropdown.contains(e.target)) {
            notifDropdown.style.display = 'none';
        }
    });

    // Fetch Notifications
    fetch('/api/notifications')
        .then(r => r.json())
        .then(data => {
            if (data.length > 0) {
                notifBadge.textContent = data.length;
                notifBadge.style.display = 'inline-block';
                
                notifBody.innerHTML = '';
                data.forEach(notif => {
                    const item = document.createElement('a');
                    item.className = 'notif-item';
                    if (notif.profile_url) {
                        item.href = notif.profile_url;
                        item.target = '_blank';
                    } else {
                        item.href = '#';
                    }
                    
                    item.innerHTML = `
                        <div class="notif-item-icon birthday">
                            <i class="fa-solid fa-cake-candles"></i>
                        </div>
                        <div class="notif-item-content">
                            <h5>${notif.title}</h5>
                            <p>${notif.message}</p>
                        </div>
                    `;
                    notifBody.appendChild(item);
                });
            } else {
                notifBadge.style.display = 'none';
                notifBody.innerHTML = '<div class="notif-empty">No new notifications</div>';
            }
        })
        .catch(err => {
            console.error('Error fetching notifications:', err);
            notifBody.innerHTML = '<div class="notif-empty">Failed to load notifications</div>';
        });
});
