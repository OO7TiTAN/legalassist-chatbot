// ─── API Base + Auth ─────────────────────────────────────────────────────────
const API_BASE = localStorage.getItem('la_api_base') || 'https://legalassist-chatbot.onrender.com';
const TOKEN = localStorage.getItem('la_admin_token');

if (!TOKEN) window.location.href = 'index.html';

async function apiFetch(path, opts = {}) {
  const res = await fetch(API_BASE + path, {
    ...opts,
    headers: {
      'Authorization': 'Bearer ' + TOKEN,
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401) { logout(); return; }
  if (!res.ok) throw new Error('API error ' + res.status);
  return res.json();
}

function logout() {
  localStorage.removeItem('la_admin_token');
  localStorage.removeItem('la_api_base');
  window.location.href = 'index.html';
}

// Debounce helper
function debounce(fn, delay) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

// Toast notification
function showToast(msg, duration = 3000) {
  const t = document.getElementById('la-toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), duration);
}

// Format date
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function fmtDateShort(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

// Truncate text
function trunc(str, n = 60) {
  if (!str) return '—';
  return str.length > n ? str.slice(0, n) + '…' : str;
}
