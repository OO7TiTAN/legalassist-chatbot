/**
 * LegalAssist Chatbot Widget v1.0
 * Self-contained embeddable chat widget for legalassistglobal.com
 * Drop-in via <script src="chatbot-widget.js"></script>
 */
(function () {
  'use strict';

  // ─── Configuration ─────────────────────────────────────────────────────────
  const CONFIG = {
    // !! IMPORTANT: Update this URL after deploying your backend to Render !!
    backendUrl: 'https://legalassist-chatbot.onrender.com',
    proxyPath: '/wp-content/themes/hello-elementor/chatbot-proxy.php',
    botName: 'Legal Assist Bot',
    greeting: "Hello! I'm here to help with any legal queries you have. Whether it's a personal injury claim, housing disrepair, immigration, or any other legal matter — just ask!",
    quickReplies: [
      'How do I make a personal injury claim?',
      'What is No Win, No Fee?',
      'I need help with housing disrepair',
      'Tell me about immigration services',
    ],
    emailPromptAfterMessages: 4,   // Prompt for email after this many exchanges
    accentColor: '#0f3460',
    accentLight: '#1e5f99',
    storageKey: 'la_chat_session',
  };

  // Detect proxy URL (if on WordPress) vs direct backend
  const API_BASE = (() => {
    try {
      const host = window.location.hostname;
      if (host.includes('legalassistglobal.com') || host.includes('localhost')) {
        return window.location.origin + CONFIG.proxyPath;
      }
    } catch (e) {}
    return CONFIG.backendUrl + '/chat';
  })();

  // ─── State ─────────────────────────────────────────────────────────────────
  let sessionId = null;
  let messageCount = 0;
  let emailPrompted = false;
  let isOpen = false;
  let isTyping = false;
  let gdprAccepted = false;

  // Restore session
  try {
    const stored = localStorage.getItem(CONFIG.storageKey);
    if (stored) {
      const parsed = JSON.parse(stored);
      sessionId = parsed.sessionId || null;
      gdprAccepted = parsed.gdprAccepted || false;
      messageCount = parsed.messageCount || 0;
    }
  } catch (e) {}

  function saveSession() {
    try {
      localStorage.setItem(CONFIG.storageKey, JSON.stringify({ sessionId, gdprAccepted, messageCount }));
    } catch (e) {}
  }

  // ─── Styles ────────────────────────────────────────────────────────────────
  const STYLES = `
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    #la-chat-root * { box-sizing: border-box; font-family: 'Inter', system-ui, sans-serif; }

    /* Bubble */
    #la-bubble {
      position: fixed; bottom: 24px; right: 24px; z-index: 99999;
      width: 60px; height: 60px; border-radius: 50%;
      background: linear-gradient(135deg, #0f3460, #1e5f99);
      box-shadow: 0 4px 20px rgba(15,52,96,0.4);
      cursor: pointer; border: none; outline: none;
      display: flex; align-items: center; justify-content: center;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      animation: la-pulse 2.5s ease-in-out infinite;
    }
    #la-bubble:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(15,52,96,0.5); }
    #la-bubble svg { width: 28px; height: 28px; fill: #fff; transition: all 0.3s; }
    #la-bubble.open svg.chat-icon { display: none; }
    #la-bubble.open svg.close-icon { display: block !important; }
    @keyframes la-pulse {
      0%, 100% { box-shadow: 0 4px 20px rgba(15,52,96,0.4); }
      50% { box-shadow: 0 4px 28px rgba(15,52,96,0.65), 0 0 0 8px rgba(15,52,96,0.08); }
    }

    /* Notification badge */
    #la-badge {
      position: fixed; bottom: 74px; right: 24px; z-index: 99999;
      background: #e53e3e; color: #fff; font-size: 11px; font-weight: 600;
      border-radius: 100px; padding: 3px 8px;
      box-shadow: 0 2px 8px rgba(229,62,62,0.4);
      animation: la-badgein 0.4s ease;
    }
    @keyframes la-badgein { from { transform: scale(0); opacity: 0; } to { transform: scale(1); opacity: 1; } }

    /* Window */
    #la-window {
      position: fixed; bottom: 96px; right: 24px; z-index: 99998;
      width: 370px; max-width: calc(100vw - 32px);
      height: 580px; max-height: calc(100vh - 120px);
      background: #fff; border-radius: 20px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.18), 0 4px 16px rgba(0,0,0,0.1);
      display: flex; flex-direction: column; overflow: hidden;
      transform: translateY(20px) scale(0.95); opacity: 0; pointer-events: none;
      transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
    }
    #la-window.visible { transform: translateY(0) scale(1); opacity: 1; pointer-events: all; }

    /* Header */
    #la-header {
      background: linear-gradient(135deg, #0f3460 0%, #1e5f99 100%);
      padding: 16px 18px; display: flex; align-items: center; gap: 12px;
      flex-shrink: 0;
    }
    #la-avatar {
      width: 40px; height: 40px; border-radius: 50%;
      background: rgba(255,255,255,0.2); display: flex; align-items: center; justify-content: center;
      font-size: 20px; flex-shrink: 0;
    }
    #la-header-info { flex: 1; }
    #la-header-name { color: #fff; font-weight: 600; font-size: 15px; line-height: 1; }
    #la-status { color: rgba(255,255,255,0.75); font-size: 12px; margin-top: 3px; display: flex; align-items: center; gap: 5px; }
    .la-status-dot { width: 7px; height: 7px; background: #4ade80; border-radius: 50%; animation: la-blink 2s ease-in-out infinite; }
    @keyframes la-blink { 0%,100%{opacity:1} 50%{opacity:0.4} }
    #la-close-btn {
      background: rgba(255,255,255,0.15); border: none; color: #fff;
      width: 32px; height: 32px; border-radius: 50%; cursor: pointer;
      display: flex; align-items: center; justify-content: center; font-size: 18px;
      transition: background 0.2s;
    }
    #la-close-btn:hover { background: rgba(255,255,255,0.25); }

    /* GDPR notice */
    #la-gdpr {
      background: #f8fafc; padding: 14px 16px;
      border-bottom: 1px solid #eef2f7; font-size: 12px; color: #666;
      line-height: 1.5; flex-shrink: 0;
    }
    #la-gdpr a { color: #1e5f99; }
    #la-gdpr-btn {
      margin-top: 10px; background: #0f3460; color: #fff; border: none;
      padding: 7px 16px; border-radius: 8px; font-size: 12px; font-weight: 600;
      cursor: pointer; transition: background 0.2s;
    }
    #la-gdpr-btn:hover { background: #1e5f99; }

    /* Messages area */
    #la-messages {
      flex: 1; overflow-y: auto; padding: 16px; display: flex;
      flex-direction: column; gap: 10px; scroll-behavior: smooth;
    }
    #la-messages::-webkit-scrollbar { width: 4px; }
    #la-messages::-webkit-scrollbar-track { background: transparent; }
    #la-messages::-webkit-scrollbar-thumb { background: #d1d9e6; border-radius: 4px; }

    /* Messages */
    .la-msg { display: flex; flex-direction: column; max-width: 82%; animation: la-msgin 0.3s ease; }
    @keyframes la-msgin { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    .la-msg.user { align-self: flex-end; align-items: flex-end; }
    .la-msg.bot { align-self: flex-start; align-items: flex-start; }
    .la-bubble {
      padding: 10px 14px; border-radius: 16px; font-size: 14px;
      line-height: 1.55; word-break: break-word;
    }
    .la-msg.user .la-bubble {
      background: linear-gradient(135deg, #0f3460, #1e5f99);
      color: #fff; border-bottom-right-radius: 4px;
    }
    .la-msg.bot .la-bubble {
      background: #f0f4f9; color: #1a202c; border-bottom-left-radius: 4px;
    }
    .la-bubble strong { font-weight: 600; }
    .la-bubble ul { margin: 6px 0 0 16px; padding: 0; }
    .la-bubble li { margin-bottom: 3px; }
    .la-time { font-size: 10px; color: #aab; margin-top: 4px; padding: 0 2px; }

    /* Page suggestion card */
    .la-suggest-card {
      margin-top: 8px; background: #fff; border: 1px solid #d1e3f5;
      border-radius: 10px; padding: 10px 14px; display: flex;
      align-items: center; gap: 10px; cursor: pointer; transition: all 0.2s;
      text-decoration: none; color: inherit;
    }
    .la-suggest-card:hover { background: #eef5ff; border-color: #1e5f99; transform: translateY(-1px); }
    .la-suggest-icon { font-size: 18px; flex-shrink: 0; }
    .la-suggest-text { flex: 1; }
    .la-suggest-title { font-size: 13px; font-weight: 600; color: #0f3460; }
    .la-suggest-cta { font-size: 11px; color: #1e5f99; margin-top: 2px; }

    /* Quick replies */
    #la-quick-replies {
      padding: 8px 14px; display: flex; flex-wrap: wrap; gap: 6px; flex-shrink: 0;
    }
    .la-qr {
      background: #fff; border: 1.5px solid #c9daf0; color: #0f3460;
      padding: 6px 12px; border-radius: 100px; font-size: 12px; font-weight: 500;
      cursor: pointer; transition: all 0.2s; white-space: nowrap;
    }
    .la-qr:hover { background: #0f3460; color: #fff; border-color: #0f3460; }

    /* Typing indicator */
    #la-typing {
      display: none; align-items: center; gap: 4px; padding: 10px 14px;
      background: #f0f4f9; border-radius: 16px 16px 16px 4px;
      width: fit-content; align-self: flex-start;
    }
    #la-typing span {
      width: 7px; height: 7px; background: #8899aa; border-radius: 50%;
      animation: la-bounce 1.2s ease-in-out infinite;
    }
    #la-typing span:nth-child(2) { animation-delay: 0.2s; }
    #la-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes la-bounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }

    /* Email prompt */
    .la-email-prompt {
      background: linear-gradient(135deg, #f0f7ff, #e8f2ff);
      border: 1px solid #c0d8f5; border-radius: 12px;
      padding: 14px; margin: 4px 0;
    }
    .la-email-title { font-size: 13px; font-weight: 600; color: #0f3460; margin-bottom: 8px; }
    .la-email-input {
      width: 100%; padding: 8px 12px; border: 1.5px solid #c0d8f5;
      border-radius: 8px; font-size: 13px; outline: none; transition: border 0.2s;
      font-family: inherit;
    }
    .la-email-input:focus { border-color: #1e5f99; }
    .la-email-name { margin-bottom: 6px; }
    .la-email-submit {
      margin-top: 8px; background: #0f3460; color: #fff; border: none;
      padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600;
      cursor: pointer; transition: background 0.2s; width: 100%;
    }
    .la-email-submit:hover { background: #1e5f99; }
    .la-email-skip { font-size: 11px; color: #888; text-align: center; margin-top: 6px; cursor: pointer; }
    .la-email-skip:hover { color: #444; }

    /* Input area */
    #la-input-area {
      padding: 12px 14px; border-top: 1px solid #eef2f7;
      display: flex; gap: 8px; align-items: flex-end; flex-shrink: 0;
      background: #fff;
    }
    #la-input {
      flex: 1; border: 1.5px solid #d1dbe8; border-radius: 12px;
      padding: 10px 14px; font-size: 14px; outline: none; resize: none;
      min-height: 42px; max-height: 100px; font-family: inherit; line-height: 1.4;
      transition: border 0.2s; color: #1a202c; background: #f8fafc;
    }
    #la-input:focus { border-color: #1e5f99; background: #fff; }
    #la-input::placeholder { color: #aab; }
    #la-send {
      width: 42px; height: 42px; border-radius: 12px; border: none; flex-shrink: 0;
      background: linear-gradient(135deg, #0f3460, #1e5f99); color: #fff;
      cursor: pointer; display: flex; align-items: center; justify-content: center;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    #la-send:hover { transform: scale(1.05); box-shadow: 0 4px 12px rgba(15,52,96,0.3); }
    #la-send svg { width: 18px; height: 18px; fill: #fff; }
    #la-send:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

    /* Powered by */
    #la-powered { text-align: center; padding: 6px; font-size: 10px; color: #bbb; flex-shrink: 0; }
    #la-powered a { color: #bbb; text-decoration: none; }
  `;

  // ─── HTML Template ──────────────────────────────────────────────────────────
  function buildHTML() {
    return `
      <div id="la-chat-root">
        <style>${STYLES}</style>

        <!-- Notification badge (shown before first open) -->
        <div id="la-badge" style="display:none">1</div>

        <!-- Chat bubble -->
        <button id="la-bubble" aria-label="Open chat" title="Chat with Legal Assist Bot">
          <svg class="chat-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.477 2 2 6.477 2 12c0 1.89.525 3.66 1.438 5.168L2.05 21.95l4.782-1.388A9.955 9.955 0 0012 22c5.523 0 10-4.477 10-10S17.523 2 12 2zm-1 13H7v-2h4v2zm6 0h-4v-2h4v2zm0-4H7V9h10v2z"/>
          </svg>
          <svg class="close-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" style="display:none">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>

        <!-- Chat window -->
        <div id="la-window" role="dialog" aria-label="Legal Assist Chat">
          <!-- Header -->
          <div id="la-header">
            <div id="la-avatar">⚖️</div>
            <div id="la-header-info">
              <div id="la-header-name">${CONFIG.botName}</div>
              <div id="la-status">
                <span class="la-status-dot"></span>
                Online — typically replies instantly
              </div>
            </div>
            <button id="la-close-btn" aria-label="Close chat">✕</button>
          </div>

          <!-- GDPR notice -->
          <div id="la-gdpr">
            🔒 This chat collects conversation data to help answer your questions.
            See our <a href="https://legalassistglobal.com/privacy-policy/" target="_blank">Privacy Policy</a>.
            By continuing you agree to our use of this data.
            <br>
            <button id="la-gdpr-btn">I Understand — Start Chatting</button>
          </div>

          <!-- Messages -->
          <div id="la-messages">
            <div id="la-typing">
              <span></span><span></span><span></span>
            </div>
          </div>

          <!-- Quick replies -->
          <div id="la-quick-replies"></div>

          <!-- Input -->
          <div id="la-input-area">
            <textarea id="la-input" placeholder="Type your legal query..." rows="1" maxlength="2000" disabled></textarea>
            <button id="la-send" disabled aria-label="Send message">
              <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            </button>
          </div>

          <div id="la-powered">Powered by <a href="https://legalassistglobal.com" target="_blank">Legal Assist UK</a></div>
        </div>
      </div>
    `;
  }

  // ─── DOM Helpers ────────────────────────────────────────────────────────────
  function $(id) { return document.getElementById(id); }

  function formatTime() {
    return new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
  }

  function parseMarkdown(text) {
    return text
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
      .replace(/\n/g, '<br>');
  }

  function appendMessage(role, text, suggestedUrl, suggestedTitle) {
    const messages = $('la-messages');
    const typing = $('la-typing');

    const wrapper = document.createElement('div');
    wrapper.className = `la-msg ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'la-bubble';
    bubble.innerHTML = parseMarkdown(text);

    const time = document.createElement('div');
    time.className = 'la-time';
    time.textContent = formatTime();

    wrapper.appendChild(bubble);
    wrapper.appendChild(time);

    // Add suggestion card for bot messages with a URL
    if (role === 'bot' && suggestedUrl && suggestedTitle) {
      const card = document.createElement('a');
      card.className = 'la-suggest-card';
      card.href = suggestedUrl;
      card.target = '_blank';
      card.rel = 'noopener';
      card.innerHTML = `
        <span class="la-suggest-icon">📄</span>
        <div class="la-suggest-text">
          <div class="la-suggest-title">${suggestedTitle}</div>
          <div class="la-suggest-cta">Learn more →</div>
        </div>
      `;
      wrapper.appendChild(card);
    }

    messages.insertBefore(wrapper, typing);
    messages.scrollTop = messages.scrollHeight;
  }

  function showTyping(show) {
    const t = $('la-typing');
    t.style.display = show ? 'flex' : 'none';
    if (show) $('la-messages').scrollTop = $('la-messages').scrollHeight;
  }

  function clearQuickReplies() {
    $('la-quick-replies').innerHTML = '';
  }

  function showQuickReplies(replies) {
    const container = $('la-quick-replies');
    container.innerHTML = '';
    replies.forEach(reply => {
      const btn = document.createElement('button');
      btn.className = 'la-qr';
      btn.textContent = reply;
      btn.onclick = () => {
        clearQuickReplies();
        sendMessage(reply);
      };
      container.appendChild(btn);
    });
  }

  function enableInput(enable) {
    $('la-input').disabled = !enable;
    $('la-send').disabled = !enable;
  }

  // ─── Email prompt ───────────────────────────────────────────────────────────
  function showEmailPrompt() {
    if (emailPrompted) return;
    emailPrompted = true;

    const messages = $('la-messages');
    const typing = $('la-typing');
    const prompt = document.createElement('div');
    prompt.className = 'la-msg bot';
    prompt.innerHTML = `
      <div class="la-email-prompt">
        <div class="la-email-title">📬 Want us to follow up with you?</div>
        <input class="la-email-input la-email-name" type="text" placeholder="Your name (optional)" id="la-eprompt-name">
        <input class="la-email-input" type="email" placeholder="Your email address" id="la-eprompt-email">
        <button class="la-email-submit" id="la-eprompt-submit">Send me a callback</button>
        <div class="la-email-skip" id="la-eprompt-skip">No thanks, continue chatting</div>
      </div>
    `;
    messages.insertBefore(prompt, typing);
    messages.scrollTop = messages.scrollHeight;

    $('la-eprompt-submit').onclick = submitEmail;
    $('la-eprompt-skip').onclick = () => {
      prompt.style.display = 'none';
    };
  }

  async function submitEmail() {
    const email = $('la-eprompt-email').value.trim();
    const name = $('la-eprompt-name').value.trim();
    if (!email || !email.includes('@')) {
      $('la-eprompt-email').style.borderColor = '#e53e3e';
      return;
    }

    // Get last user message as query context
    const msgs = document.querySelectorAll('.la-msg.user .la-bubble');
    const query = msgs.length ? msgs[msgs.length - 1].textContent : '';

    try {
      await apiCall('/collect-email', {
        session_id: sessionId,
        email,
        name: name || null,
        query,
        page_url: window.location.href,
      });
      const container = document.querySelector('.la-email-prompt');
      if (container) {
        container.innerHTML = '<div style="text-align:center;color:#0f3460;font-weight:600;padding:8px">✅ Thank you! We\'ll be in touch shortly.</div>';
      }
    } catch (e) {
      console.warn('[LegalAssist] Email submission failed:', e);
    }
  }

  // ─── API ────────────────────────────────────────────────────────────────────
  async function apiCall(endpoint, body) {
    const url = API_BASE.endsWith('/collect-email') || API_BASE.endsWith('/pageview')
      ? API_BASE
      : API_BASE.replace(/\/$/, '') + endpoint;

    // Determine actual URL
    let fullUrl;
    if (API_BASE.includes('chatbot-proxy.php')) {
      fullUrl = API_BASE + '?endpoint=' + encodeURIComponent(endpoint);
    } else {
      fullUrl = CONFIG.backendUrl + '/chat' + endpoint;
    }

    const response = await fetch(fullUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!response.ok) throw new Error('API error: ' + response.status);
    return response.json();
  }

  // ─── Send message ───────────────────────────────────────────────────────────
  async function sendMessage(text) {
    const msg = (text || $('la-input').value).trim();
    if (!msg || isTyping) return;

    clearQuickReplies();
    $('la-input').value = '';
    $('la-input').style.height = 'auto';
    appendMessage('user', msg);
    messageCount++;
    saveSession();

    isTyping = true;
    enableInput(false);
    showTyping(true);

    try {
      const data = await apiCall('', {
        message: msg,
        session_id: sessionId,
        page_url: window.location.href,
      });

      sessionId = data.session_id;
      saveSession();

      showTyping(false);
      appendMessage('bot', data.message, data.suggested_url, data.suggested_title);

      // Show email prompt after N exchanges
      if (messageCount >= CONFIG.emailPromptAfterMessages && !emailPrompted) {
        setTimeout(showEmailPrompt, 1200);
      }

    } catch (err) {
      showTyping(false);
      appendMessage('bot', "I'm sorry, I'm having trouble connecting right now. Please try again in a moment, or call us on **0161 470 0727** for immediate assistance.");
      console.warn('[LegalAssist] Chat error:', err);
    } finally {
      isTyping = false;
      enableInput(true);
      $('la-input').focus();
    }
  }

  // ─── Pageview tracking ──────────────────────────────────────────────────────
  function trackPageView() {
    try {
      fetch(CONFIG.backendUrl + '/chat/pageview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          page_url: window.location.href,
          referrer: document.referrer || null,
        }),
        keepalive: true,
      }).catch(() => {});
    } catch (e) {}
  }

  // ─── Init & event wiring ────────────────────────────────────────────────────
  function init() {
    // Inject HTML
    const root = document.createElement('div');
    root.innerHTML = buildHTML();
    document.body.appendChild(root);

    // Show badge after 3s if not opened before
    if (!sessionId) {
      setTimeout(() => {
        if (!isOpen) $('la-badge').style.display = 'block';
      }, 3000);
    }

    // Bubble click
    $('la-bubble').onclick = toggleChat;
    $('la-close-btn').onclick = closeChat;

    // GDPR accept
    $('la-gdpr-btn').onclick = () => {
      gdprAccepted = true;
      saveSession();
      $('la-gdpr').style.display = 'none';
      enableInput(true);
      // Show greeting
      appendMessage('bot', CONFIG.greeting);
      setTimeout(() => showQuickReplies(CONFIG.quickReplies), 600);
    };

    // If already accepted GDPR
    if (gdprAccepted) {
      $('la-gdpr').style.display = 'none';
      enableInput(true);
    }

    // Send button
    $('la-send').onclick = () => sendMessage();

    // Enter key
    $('la-input').onkeydown = (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    };

    // Auto-resize textarea
    $('la-input').oninput = function () {
      this.style.height = 'auto';
      this.style.height = Math.min(this.scrollHeight, 100) + 'px';
    };

    // Track page view
    trackPageView();
  }

  function toggleChat() {
    if (isOpen) closeChat(); else openChat();
  }

  function openChat() {
    isOpen = true;
    $('la-window').classList.add('visible');
    $('la-bubble').classList.add('open');
    $('la-badge').style.display = 'none';
    if (gdprAccepted) $('la-input').focus();
  }

  function closeChat() {
    isOpen = false;
    $('la-window').classList.remove('visible');
    $('la-bubble').classList.remove('open');
  }

  // ─── Boot ───────────────────────────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
