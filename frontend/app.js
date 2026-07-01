const API_BASE = 'http://localhost:8000';

// State
let chatHistory = [];
let isGenerating = false;

// DOM Elements
const elements = {
    input: document.getElementById('user-input'),
    sendBtn: document.getElementById('send-btn'),
    messages: document.getElementById('messages-container'),
    modelSelect: document.getElementById('model-select'),
    statusText: document.getElementById('live-status-text'),
    statusProgress: document.getElementById('status-progress'),
    conceptsContainer: document.getElementById('concepts-container'),
    sourcesContainer: document.getElementById('sources-container'),
    statusIndicator: document.getElementById('connection-status'),

    // Modal
    modalOverlay: document.getElementById('modal-overlay'),
    modalTitle: document.getElementById('modal-title'),
    modalDomain: document.getElementById('modal-domain'),
    modalId: document.getElementById('modal-id'),
    modalSummary: document.getElementById('modal-summary'),
    modalContent: document.getElementById('modal-content'),
    modalClose: document.getElementById('modal-close')
};

// Init
async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
            elements.statusIndicator.classList.add('connected');
            elements.statusIndicator.querySelector('.text').textContent = 'System Online';
        }
    } catch (e) {
        console.warn('Backend not ready');
    }
}
checkHealth();

// Event Listeners
elements.input.addEventListener('input', () => {
    elements.sendBtn.disabled = !elements.input.value.trim();
});

elements.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

elements.sendBtn.addEventListener('click', sendMessage);

elements.modalClose.addEventListener('click', closeModal);
elements.modalOverlay.addEventListener('click', (e) => {
    if (e.target === elements.modalOverlay) closeModal();
});

// Logic
async function sendMessage() {
    const text = elements.input.value.trim();
    if (!text || isGenerating) return;

    isGenerating = true;
    elements.input.value = '';
    elements.input.disabled = true;
    elements.sendBtn.disabled = true;

    // Add User Message
    addMessage('user', text);
    chatHistory.push({ role: 'user', content: text });

    // Reset Side Panel
    resetSidePanel();

    // Create AI Message Placeholder
    const aiMessageContent = addMessage('ai', '');
    let fullAiResponse = "";

    try {
        const payload = {
            query: text,
            history: chatHistory,
            model_type: elements.modelSelect.value
        };

        const response = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Process complete lines
            const lines = buffer.split('\n\n');
            buffer = lines.pop() || ''; // Keep partial line

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.slice(6);
                    try {
                        const eventData = JSON.parse(jsonStr);
                        handleServerEvent(eventData, aiMessageContent, (currText) => {
                            fullAiResponse += currText;
                        });
                    } catch (e) {
                        console.error('JSON Parse Error', e);
                    }
                }
            }
        }

    } catch (e) {
        addMessage('system-message', `Error: ${e.message}`);
    } finally {
        isGenerating = false;
        elements.input.disabled = false;
        elements.input.focus();
        elements.statusText.textContent = "Idle";
        elements.statusProgress.classList.remove('active');

        chatHistory.push({ role: 'model', content: fullAiResponse });
    }
}

function handleServerEvent(eventMsg, messageEl, appendTextCallback) {
    const { event, data } = eventMsg;

    switch (event) {
        case 'status':
            elements.statusText.textContent = data;
            elements.statusProgress.classList.add('active');
            break;

        case 'concepts':
            renderConcepts(data);
            break;

        case 'sources':
            renderSources(data);
            break;

        case 'token':
            // Simple typing effect or direct append
            messageEl.innerHTML += data; // Using innerHTML to allow newlines/formatting if needed
            appendTextCallback(data);
            scrollToBottom();
            break;

        case 'error':
            const errMsg = eventMsg.message || data || 'Unknown error';
            console.error(errMsg);
            messageEl.innerHTML += `<br><span style="color:red">[Error: ${errMsg}]</span>`;
            break;
    }
}

// UI Helpers
function addMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    // For AI, we return the inner content div to append tokens
    if (role === 'ai') {
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        msgDiv.appendChild(contentDiv);
        elements.messages.appendChild(msgDiv);
        return contentDiv;
    } else {
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.textContent = text;
        msgDiv.appendChild(contentDiv);
        elements.messages.appendChild(msgDiv);
        scrollToBottom();
        return contentDiv;
    }
}

function scrollToBottom() {
    elements.messages.scrollTop = elements.messages.scrollHeight;
}

function resetSidePanel() {
    elements.statusText.textContent = "Initializing...";
    elements.statusProgress.classList.add('active');
    elements.conceptsContainer.innerHTML = '';
    elements.sourcesContainer.innerHTML = '';
}

function renderConcepts(concepts) {
    elements.conceptsContainer.innerHTML = '';
    if (!concepts || concepts.length === 0) {
        elements.conceptsContainer.innerHTML = '<span class="empty-state">No concepts found</span>';
        return;
    }

    concepts.forEach(c => {
        const tag = document.createElement('span');
        tag.className = 'concept-tag';
        tag.textContent = c;
        elements.conceptsContainer.appendChild(tag);
    });
}

function renderSources(sources) {
    elements.sourcesContainer.innerHTML = '';
    if (!sources || sources.length === 0) return;

    sources.forEach(source => {
        const card = document.createElement('div');
        card.className = 'source-card';
        card.onclick = () => openModal(source);

        const header = document.createElement('div');
        header.className = 'source-header';

        const idSpan = document.createElement('span');
        idSpan.className = 'source-id';
        idSpan.textContent = source.id;

        const domainSpan = document.createElement('span');
        domainSpan.className = 'source-domain';
        domainSpan.textContent = source.domain || 'N/A';

        header.appendChild(idSpan);
        header.appendChild(domainSpan);

        const summary = document.createElement('p');
        summary.className = 'source-summary';
        summary.textContent = source.summary || 'No summary available.';

        card.appendChild(header);
        card.appendChild(summary);

        elements.sourcesContainer.appendChild(card);
    });
}

// Modal Logic
function openModal(source) {
    elements.modalTitle.textContent = "Source Details";
    elements.modalId.textContent = source.id;
    elements.modalDomain.textContent = source.domain || 'Unknown';
    elements.modalSummary.textContent = source.summary;
    elements.modalContent.textContent = source.full_text || 'No transcript available.';

    elements.modalOverlay.classList.remove('hidden');
}

function closeModal() {
    elements.modalOverlay.classList.add('hidden');
}
