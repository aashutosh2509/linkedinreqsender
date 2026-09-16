document.addEventListener("DOMContentLoaded", () => {
    const chatList = document.getElementById("chatList");
    const chatMain = document.getElementById("chatMain");
    const chatSearchInput = document.getElementById("chatSearchInput");
    const chatListHeading = document.getElementById("chatListHeading");
    const chatCountBadge = document.getElementById("chatCountBadge");
    const tabAllChats = document.getElementById("tabAllChats");
    const tabStarredChats = document.getElementById("tabStarredChats");
    const navConversations = document.getElementById("navConversations");
    const navStarred = document.getElementById("navStarred");

    let chatsData = {};
    let activeThreadUrl = null;
    let currentFilter = "all"; // "all" or "starred"

    // Load starred threads from localStorage
    let starredThreads = new Set();
    try {
        const saved = localStorage.getItem("crm_starred_threads");
        if (saved) {
            starredThreads = new Set(JSON.parse(saved));
        }
    } catch (e) {
        console.error("Error reading starred threads:", e);
    }

    function saveStarredThreads() {
        try {
            localStorage.setItem("crm_starred_threads", JSON.stringify(Array.from(starredThreads)));
        } catch (e) {
            console.error("Error saving starred threads:", e);
        }
    }

    // Check URL parameters for initial view filter
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get("filter") === "starred" || window.location.hash === "#starred") {
        currentFilter = "starred";
    }

    updateFilterUI();

    // Fetch chats from API
    fetch('/api/chats')
        .then(response => response.json())
        .then(data => {
            chatsData = data;
            // Also sync any starred status sent by backend
            Object.values(chatsData).forEach(chat => {
                if (chat.is_starred && chat.thread_url) {
                    starredThreads.add(chat.thread_url);
                }
            });
            saveStarredThreads();
            renderChatList();
        })
        .catch(err => {
            console.error("Error fetching chats:", err);
            if (chatList) {
                chatList.innerHTML = `<div class="chat-list-empty">Error loading chats.</div>`;
            }
        });

    function isChatStarred(chat) {
        if (!chat) return false;
        return starredThreads.has(chat.thread_url);
    }

    function toggleStar(threadUrl, e) {
        if (e) e.stopPropagation();
        if (!threadUrl) return;

        if (starredThreads.has(threadUrl)) {
            starredThreads.delete(threadUrl);
        } else {
            starredThreads.add(threadUrl);
        }
        saveStarredThreads();

        // Sync with backend
        try {
            fetch('/api/chats/star', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ thread_url: threadUrl, is_starred: starredThreads.has(threadUrl) })
            }).catch(() => {});
        } catch (_) {}

        // Re-render chat list and update current chat header
        const currentSearch = chatSearchInput ? chatSearchInput.value : "";
        renderChatList(currentSearch);

        const currentChat = Object.values(chatsData).find(c => c.thread_url === activeThreadUrl);
        if (currentChat) {
            updateHeaderStarState(currentChat);
        }
    }

    function updateHeaderStarState(chat) {
        const starBtn = document.getElementById("headerStarBtn");
        if (!starBtn) return;

        const isStarred = starredThreads.has(chat.thread_url);
        if (isStarred) {
            starBtn.className = "btn-star-toggle active";
            starBtn.innerHTML = `<i class="fa-solid fa-star" style="color: #f59e0b;"></i> Starred`;
            starBtn.title = "Click to unstar chat";
        } else {
            starBtn.className = "btn-star-toggle";
            starBtn.innerHTML = `<i class="fa-regular fa-star"></i> Star Chat`;
            starBtn.title = "Click to star chat";
        }
    }

    function setFilter(filterType) {
        currentFilter = filterType;
        updateFilterUI();
        const currentSearch = chatSearchInput ? chatSearchInput.value : "";
        renderChatList(currentSearch);

        // Update URL query param cleanly without reload
        const newUrl = filterType === "starred" ? "conversations.html?filter=starred" : "conversations.html";
        try {
            window.history.replaceState({ filter: filterType }, "", newUrl);
        } catch (_) {}
    }

    function updateFilterUI() {
        if (currentFilter === "starred") {
            if (navStarred) navStarred.classList.add("active");
            if (navConversations) navConversations.classList.remove("active");
            if (tabStarredChats) tabStarredChats.classList.add("active");
            if (tabAllChats) tabAllChats.classList.remove("active");
            if (chatListHeading) chatListHeading.innerHTML = `<i class="fa-solid fa-star" style="color: #f59e0b; font-size: 16px;"></i> Starred Chats`;
        } else {
            if (navConversations) navConversations.classList.add("active");
            if (navStarred) navStarred.classList.remove("active");
            if (tabAllChats) tabAllChats.classList.add("active");
            if (tabStarredChats) tabStarredChats.classList.remove("active");
            if (chatListHeading) chatListHeading.textContent = "Chats";
        }
    }

    // Tab event listeners
    if (tabAllChats) {
        tabAllChats.addEventListener("click", () => setFilter("all"));
    }
    if (tabStarredChats) {
        tabStarredChats.addEventListener("click", () => setFilter("starred"));
    }
    if (navConversations) {
        navConversations.addEventListener("click", (e) => {
            e.preventDefault();
            setFilter("all");
        });
    }
    if (navStarred) {
        navStarred.addEventListener("click", (e) => {
            e.preventDefault();
            setFilter("starred");
        });
    }

    function renderChatList(filterText = "") {
        if (!chatList) return;
        chatList.innerHTML = "";

        // Convert dict to array and sort by last_updated descending
        const chatsArray = Object.values(chatsData).sort((a, b) => (b.last_updated || 0) - (a.last_updated || 0));

        let filtered = chatsArray;

        // Apply Starred Filter (only user-starred chats)
        if (currentFilter === "starred") {
            filtered = filtered.filter(chat => isChatStarred(chat));
        }

        // Apply Search Text Filter
        if (filterText) {
            const lowerFilter = filterText.toLowerCase();
            filtered = filtered.filter(chat => {
                const name = (chat.full_name || chat.lead_name || "").toLowerCase();
                const lastMsg = chat.messages && chat.messages.length > 0 ? (chat.messages[chat.messages.length - 1].content || "").toLowerCase() : "";
                return name.includes(lowerFilter) || lastMsg.includes(lowerFilter);
            });
        }

        // Update count badge
        if (chatCountBadge) {
            chatCountBadge.textContent = filtered.length;
        }

        if (filtered.length === 0) {
            if (currentFilter === "starred") {
                chatList.innerHTML = `
                    <div class="chat-list-empty" style="padding: 40px 20px;">
                        <i class="fa-solid fa-star" style="font-size: 32px; color: #f59e0b; margin-bottom: 12px; display: block; opacity: 0.7;"></i>
                        <p style="font-weight: 600; margin-bottom: 6px;">No Starred Chats</p>
                        <span style="font-size: 12px; color: var(--text-muted); line-height: 1.4; display: block;">
                            Click the star icon ⭐ on any conversation to add it to your Starred Chats.
                        </span>
                    </div>
                `;
            } else {
                chatList.innerHTML = `<div class="chat-list-empty">No conversations found.</div>`;
            }
            return;
        }

        filtered.forEach(chat => {
            const item = document.createElement("div");
            item.className = "chat-list-item";
            if (activeThreadUrl === chat.thread_url) {
                item.classList.add("active");
            }

            const isStarred = isChatStarred(chat);
            const displayName = chat.full_name || chat.lead_name || "Lead";

            const lastMsg = chat.messages && chat.messages.length > 0 ? chat.messages[chat.messages.length - 1] : { content: "" };
            let snippet = (lastMsg.content || "").substring(0, 45);
            if ((lastMsg.content || "").length > 45) snippet += "...";

            const rolePrefix = lastMsg.role === "assistant" ? "You: " : "";
            const timeStr = chat.last_updated ? new Date(chat.last_updated * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "";

            const workspaceBadge = chat.account_name || chat.account_id ? `<span class="workspace-badge" style="font-size: 10px; background: var(--glow-purple); color: var(--accent-purple); padding: 2px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle;">${chat.account_name || chat.account_id}</span>` : "";

            item.innerHTML = `
                <div class="chat-avatar">${displayName.charAt(0).toUpperCase()}</div>
                <div class="chat-list-details">
                    <div class="chat-list-header">
                        <h4>${displayName} ${workspaceBadge}</h4>
                        <div style="display: flex; align-items: center; gap: 6px;">
                            <span class="chat-time">${timeStr}</span>
                            <button class="btn-star-item ${isStarred ? 'starred' : ''}" title="${isStarred ? 'Unstar' : 'Star'}" data-thread="${chat.thread_url}">
                                <i class="${isStarred ? 'fa-solid' : 'fa-regular'} fa-star"></i>
                            </button>
                        </div>
                    </div>
                    <div class="chat-snippet">${rolePrefix}${snippet}</div>
                </div>
            `;

            // Star click
            const starBtn = item.querySelector(".btn-star-item");
            if (starBtn) {
                starBtn.addEventListener("click", (e) => {
                    toggleStar(chat.thread_url, e);
                });
            }

            // Item select click
            item.addEventListener("click", () => {
                activeThreadUrl = chat.thread_url;
                document.querySelectorAll(".chat-list-item").forEach(el => el.classList.remove("active"));
                item.classList.add("active");
                openChat(chat);
            });

            chatList.appendChild(item);
        });
    }

    function openChat(chat) {
        if (!chatMain) return;
        const displayName = chat.full_name || chat.lead_name || "Lead";
        const displayHeadline = chat.headline ? `<div style="font-size: 13px; color: var(--text-muted); font-weight: 400; margin-top: 4px;">${chat.headline}</div>` : '';
        const isStarred = isChatStarred(chat);

        const workspaceInfo = chat.account_name ? `<span class="workspace-badge" style="font-size: 12px; background: var(--glow-purple); color: var(--accent-purple); padding: 3px 8px; border-radius: 6px; margin-left: 8px; vertical-align: middle; font-weight: 500;">Workspace: ${chat.account_name}</span>` : '';

        chatMain.innerHTML = `
            <div class="chat-header">
                <div class="chat-avatar">${displayName.charAt(0).toUpperCase()}</div>
                <div class="chat-header-info" style="flex: 1;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <h3>${displayName} ${workspaceInfo}</h3>
                    </div>
                    ${displayHeadline}
                    <a href="${chat.profile_url || chat.thread_url}" target="_blank" class="linkedin-link"><i class="fa-brands fa-linkedin"></i> View on LinkedIn</a>
                </div>
                <div class="chat-header-actions">
                    <button id="headerStarBtn" class="btn-star-toggle ${isStarred ? 'active' : ''}" title="${isStarred ? 'Click to unstar' : 'Click to star'}">
                        <i class="${isStarred ? 'fa-solid' : 'fa-regular'} fa-star" ${isStarred ? 'style="color: #f59e0b;"' : ''}></i> ${isStarred ? 'Starred' : 'Star Chat'}
                    </button>
                </div>
            </div>
            <div class="chat-messages" id="chatMessages">
                <!-- Messages go here -->
            </div>
        `;

        const headerStarBtn = document.getElementById("headerStarBtn");
        if (headerStarBtn) {
            headerStarBtn.addEventListener("click", (e) => {
                toggleStar(chat.thread_url, e);
            });
        }

        const chatMessages = document.getElementById("chatMessages");
        if (chatMessages && chat.messages) {
            chat.messages.forEach(msg => {
                const bubbleWrap = document.createElement("div");
                bubbleWrap.className = `chat-bubble-wrapper ${msg.role === 'assistant' ? 'sent' : 'received'}`;

                const bubble = document.createElement("div");
                bubble.className = "chat-bubble";
                bubble.textContent = msg.content;

                bubbleWrap.appendChild(bubble);
                chatMessages.appendChild(bubbleWrap);
            });

            // Scroll to bottom
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    if (chatSearchInput) {
        chatSearchInput.addEventListener("input", (e) => {
            renderChatList(e.target.value);
        });
    }
});
