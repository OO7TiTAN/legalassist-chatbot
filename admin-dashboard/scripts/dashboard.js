// ─── Section routing ─────────────────────────────────────────────────────────
let currentSection = 'overview';
const sectionLoaders = {
  overview:      loadOverview,
  conversations: () => loadConversations(1),
  users:         () => loadUsers(1),
  analytics:     loadAnalyticsCharts,
  traffic:       loadTraffic,
  content:       loadContentPages,
  settings:      loadSettings,
};

function showSection(name, el) {
  document.querySelectorAll('.la-nav-item').forEach(i => i.classList.remove('active'));
  if (el) el.classList.add('active');
  document.querySelectorAll('[id^="section-"]').forEach(s => s.style.display = 'none');
  document.getElementById('section-' + name).style.display = '';
  document.getElementById('page-title').textContent = el ? el.textContent.trim() : name;
  currentSection = name;
  if (sectionLoaders[name]) sectionLoaders[name]();
  updateTimestamp();
}

function refreshCurrentSection() {
  if (sectionLoaders[currentSection]) sectionLoaders[currentSection]();
  updateTimestamp();
}

function updateTimestamp() {
  const el = document.getElementById('last-updated');
  if (el) el.textContent = 'Updated ' + new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

// ─── Overview ────────────────────────────────────────────────────────────────
let dailyChart = null, hourlyChart = null;

async function loadOverview() {
  try {
    const [stats, daily, hourly, queries] = await Promise.all([
      apiFetch('/admin/analytics/overview'),
      apiFetch('/admin/analytics/daily-sessions?days=30'),
      apiFetch('/admin/analytics/hourly-traffic?days=7'),
      apiFetch('/admin/analytics/top-queries?limit=10'),
    ]);

    // Stat cards
    document.getElementById('stat-sessions').textContent = stats.total_sessions.toLocaleString();
    document.getElementById('stat-messages').textContent = stats.total_messages.toLocaleString();
    document.getElementById('stat-users').textContent = stats.total_users_collected.toLocaleString();
    document.getElementById('stat-pageviews').textContent = stats.total_pageviews.toLocaleString();
    document.getElementById('stat-sessions-today').textContent = `${stats.sessions_today} today`;
    document.getElementById('stat-avg-msgs').textContent = `Avg ${stats.avg_messages_per_session} msgs/session`;

    // Daily chart
    const dailyCtx = document.getElementById('chart-daily').getContext('2d');
    if (dailyChart) dailyChart.destroy();
    dailyChart = new Chart(dailyCtx, {
      type: 'line',
      data: {
        labels: daily.map(d => {
          const [y, m, day] = d.date.split('-');
          return `${day}/${m}`;
        }),
        datasets: [{
          label: 'Conversations',
          data: daily.map(d => d.count),
          borderColor: '#1e5f99',
          backgroundColor: 'rgba(30,95,153,0.08)',
          borderWidth: 2.5,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#1e5f99',
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 11 }, maxTicksLimit: 10 } },
          y: { grid: { color: '#f1f5f9' }, ticks: { color: '#94a3b8', font: { size: 11 }, stepSize: 1 }, beginAtZero: true },
        },
      },
    });

    // Hourly chart
    const hourlyCtx = document.getElementById('chart-hourly').getContext('2d');
    if (hourlyChart) hourlyChart.destroy();
    hourlyChart = new Chart(hourlyCtx, {
      type: 'bar',
      data: {
        labels: hourly.map(h => h.hour + ':00'),
        datasets: [{
          label: 'Page Views',
          data: hourly.map(h => h.count),
          backgroundColor: hourly.map((h, i) => {
            const maxH = Math.max(...hourly.map(x => x.count));
            const alpha = maxH > 0 ? 0.3 + (h.count / maxH) * 0.7 : 0.3;
            return `rgba(6,182,212,${alpha})`;
          }),
          borderRadius: 6,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 }, maxTicksLimit: 8 } },
          y: { grid: { color: '#f1f5f9' }, ticks: { color: '#94a3b8', font: { size: 11 } }, beginAtZero: true },
        },
      },
    });

    // Top queries list
    const list = document.getElementById('top-queries-list');
    if (!queries || queries.length === 0) {
      list.innerHTML = '<div class="la-empty"><div class="la-empty-icon">🔍</div><div class="la-empty-title">No queries yet</div><div class="la-empty-sub">Queries will appear once users start chatting</div></div>';
      return;
    }
    const maxCount = Math.max(...queries.map(q => q.count));
    list.innerHTML = queries.map((q, i) => `
      <div style="margin-bottom:14px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:5px">
          <span style="font-size:13px;color:#1a202c;font-weight:500">${i + 1}. ${q.query}</span>
          <span style="font-size:12px;font-weight:600;color:#0f3460">${q.count}x</span>
        </div>
        <div style="height:6px;background:#eef2f7;border-radius:100px;overflow:hidden">
          <div style="height:100%;width:${Math.round((q.count / maxCount) * 100)}%;background:linear-gradient(90deg,#0f3460,#1e5f99);border-radius:100px;transition:width 0.5s"></div>
        </div>
      </div>
    `).join('');

  } catch (e) {
    console.error('[Dashboard] Overview error:', e);
  }
}

// ─── Conversation modal ───────────────────────────────────────────────────────
async function openConversation(sessionId, userEmail) {
  const modal = document.getElementById('conv-modal');
  const body  = document.getElementById('modal-body');
  const title = document.getElementById('modal-title');
  title.textContent = userEmail ? `Conversation — ${userEmail}` : `Conversation`;
  body.innerHTML = '<div class="la-spinner"></div>';
  modal.classList.add('open');

  try {
    const data = await apiFetch(`/admin/conversations/${sessionId}`);
    const s = data.session;
    body.innerHTML = `
      <div style="background:#f8fafc;border-radius:12px;padding:16px;margin-bottom:20px;font-size:13px">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div><span style="color:#64748b">Started:</span> <strong>${fmtDate(s.started_at)}</strong></div>
          <div><span style="color:#64748b">Messages:</span> <strong>${s.message_count}</strong></div>
          <div><span style="color:#64748b">Email:</span> <strong>${s.user_email || 'Not provided'}</strong></div>
          <div><span style="color:#64748b">Name:</span> <strong>${s.user_name || 'Anonymous'}</strong></div>
          <div style="grid-column:1/-1"><span style="color:#64748b">Page:</span> <a href="${s.page_url}" target="_blank" style="color:#1e5f99">${trunc(s.page_url, 80)}</a></div>
        </div>
      </div>
      <div class="la-chat-log" id="chat-log">
        ${data.messages.map(m => `
          <div class="la-chat-msg ${m.role === 'user' ? 'user' : 'bot'}">
            <div>
              <div class="la-chat-msg-bubble">${m.content.replace(/\n/g,'<br>').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>')}</div>
              <div class="la-chat-time">${m.role === 'user' ? '👤' : '🤖'} ${fmtDate(m.timestamp)}</div>
              ${m.suggested_url ? `<a href="${m.suggested_url}" target="_blank" style="font-size:12px;color:#1e5f99;display:block;margin-top:4px">📄 ${m.suggested_title || m.suggested_url}</a>` : ''}
            </div>
          </div>
        `).join('')}
      </div>
      ${s.user_email ? `<div style="margin-top:16px"><a href="mailto:${s.user_email}?subject=Re: Your Legal Enquiry" class="btn btn-primary btn-sm">Reply to ${s.user_email}</a></div>` : ''}
    `;
  } catch (e) {
    body.innerHTML = '<div class="la-alert error">❌ Failed to load conversation.</div>';
  }
}

function closeModal() {
  document.getElementById('conv-modal').classList.remove('open');
}

// Close modal on overlay click
document.getElementById('conv-modal').addEventListener('click', function(e) {
  if (e.target === this) closeModal();
});

// ─── Init ─────────────────────────────────────────────────────────────────────
loadOverview();
updateTimestamp();
