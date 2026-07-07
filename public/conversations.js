document.addEventListener("DOMContentLoaded", () => {
    const chatList = document.getElementById("chatList");
    const chatMain = document.getElementById("chatMain");
    const chatSearchInput = document.getElementById("chatSearchInput");
    let chatsData = {};
    let activeThreadUrl = null;

    // Fetch chats from API
    fetch('/api/chats')
        .then(response => response.json())
        .then(data => {
            chatsData = data;
            renderChatList();
        })
        .catch(err => console.error("Error fetching chats:", err));

    function renderChatList(filterText = "") {
        chatList.innerHTML = "";
        
        // Convert dict to array and sort by last_updated
        const chatsArray = Object.values(chatsData).sort((a, b) => b.last_updated - a.last_updated);
        
        if(chatsArray.length === 0) {
            chatList.innerHTML = `<div class="chat-list-empty">No conversations found.</div>`;
            return;
        }

        chatsArray.forEach(chat => {
            if (filterText && !chat.lead_name.toLowerCase().includes(filterText.toLowerCase())) {
                return;
            }

            const item = document.createElement("div");
            item.className = "chat-list-item";
            if (activeThreadUrl === chat.thread_url) {
                item.classList.add("active");
            }
            
            const lastMsg = chat.messages.length > 0 ? chat.messages[chat.messages.length - 1] : {content: ""};
            let snippet = lastMsg.content.substring(0, 45);
            if (lastMsg.content.length > 45) snippet += "...";

            // Add role prefix to snippet if we want, but let's keep it simple
            const rolePrefix = lastMsg.role === "assistant" ? "You: " : "";
            
            const timeStr = new Date(chat.last_updated * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
            
            const displayName = chat.full_name || chat.lead_name;

            item.innerHTML = `
                <div class="chat-avatar">${displayName.charAt(0).toUpperCase()}</div>
                <div class="chat-list-details">
                    <div class="chat-list-header">
                        <h4>${displayName} <span class="workspace-badge" style="font-size: 10px; background: var(--glow-purple); color: var(--accent-purple); padding: 2px 6px; border-radius: 4px; margin-left: 6px; vertical-align: middle;">${chat.account_name || chat.account_id || 'Unknown'}</span></h4>
                        <span class="chat-time">${timeStr}</span>
                    </div>
                    <div class="chat-snippet">${rolePrefix}${snippet}</div>
                </div>
            `;
            
            item.addEventListener("click", () => {
                activeThreadUrl = chat.thread_url;
                // Update active class without re-rendering the whole list and losing scroll position
                document.querySelectorAll('.chat-list-item').forEach(el => el.classList.remove('active'));
                item.classList.add("active");
                
                openChat(chat);
            });
            
            chatList.appendChild(item);
        });
    }

    function openChat(chat) {
        const displayName = chat.full_name || chat.lead_name;
        const displayHeadline = chat.headline ? `<div style="font-size: 13px; color: var(--text-muted); font-weight: 400; margin-top: 4px;">${chat.headline}</div>` : '';
        
        chatMain.innerHTML = `
            <div class="chat-header">
                <div class="chat-avatar">${displayName.charAt(0).toUpperCase()}</div>
                <div class="chat-header-info">
                    <h3>${displayName} <span class="workspace-badge" style="font-size: 12px; background: var(--glow-purple); color: var(--accent-purple); padding: 3px 8px; border-radius: 6px; margin-left: 8px; vertical-align: middle; font-weight: 500;">Workspace: ${chat.account_name || 'Unknown'}</span></h3>
                    ${displayHeadline}
                    <a href="${chat.thread_url}" target="_blank" class="linkedin-link"><i class="fa-brands fa-linkedin"></i> View on LinkedIn</a>
                </div>
            </div>
            <div class="chat-messages" id="chatMessages">
                <!-- Messages go here -->
            </div>
        `;
        
        const chatMessages = document.getElementById("chatMessages");
        
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

    chatSearchInput.addEventListener("input", (e) => {
        renderChatList(e.target.value);
    });
});
