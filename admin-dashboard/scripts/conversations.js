// ─── Conversations list ────────────────────────────────────────────────────
let convPage = 1;
let convTotal = 0;
const PAGE_SIZE = 20;

async function loadConversations(page = 1) {
  convPage = page;
  const search = document.getElementById('conv-search')?.value || '';
  const hasEmail = document.getElementById('filter-email')?.value || '';
  const tbody = document.getElementById('conv-tbody');
  tbody.innerHTML = '<tr><td colspan="6"><div class="la-spinner"></div></td></tr>';

  try {
    let url = `/admin/conversations?page=${page}&page_size=${PAGE_SIZE}`;
    if (search) url += `&search=${encodeURIComponent(search)}`;
    if (hasEmail !== '') url += `&has_email=${hasEmail}`;

    const data = await apiFetch(url);
    convTotal = data.total;

    if (!data.sessions || data.sessions.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6">
        <div class="la-empty"><div class="la-empty-icon">💬</div>
          <div class="la-empty-title">No conversations yet</div>
          <div class="la-empty-sub">Conversations will appear here once users interact with the chatbot</div>
        </div></td></tr>`;
      renderConvPagination(0, 0);
      return;
    }

    tbody.innerHTML = data.sessions.map(s => `
      <tr>
        <td style="white-space:nowrap">${fmtDateShort(s.started_at)}</td>
        <td>
          ${s.user_email
            ? `<div style="font-weight:600;color:#0f3460">${s.user_email}</div><div style="font-size:12px;color:#94a3b8">${s.user_name || ''}</div>`
            : `<span style="color:#94a3b8;font-size:13px">Anonymous</span>`
          }
        </td>
        <td><span class="la-badge ${s.message_count > 5 ? 'blue' : 'gray'}">${s.message_count} msgs</span></td>
        <td style="max-width:160px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;color:#64748b">
          ${s.page_url ? `<a href="${s.page_url}" target="_blank" style="color:#1e5f99" title="${s.page_url}">${trunc(s.page_url.replace('https://legalassistglobal.com', ''), 35)}</a>` : '—'}
        </td>
        <td>
          ${s.user_email
            ? '<span class="la-badge green">✉ Has Email</span>'
            : '<span class="la-badge gray">Anonymous</span>'
          }
        </td>
        <td>
          <button class="btn btn-outline btn-sm" onclick="openConversation('${s.id}', '${s.user_email || ''}')">View →</button>
        </td>
      </tr>
    `).join('');

    renderConvPagination(convTotal, page);
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="6"><div class="la-alert error">Failed to load conversations.</div></td></tr>';
  }
}

function renderConvPagination(total, page) {
  const el = document.getElementById('conv-pagination');
  const totalPages = Math.ceil(total / PAGE_SIZE);
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  const start = (page - 1) * PAGE_SIZE + 1;
  const end = Math.min(page * PAGE_SIZE, total);
  el.innerHTML = `
    <span class="la-page-info">Showing ${start}–${end} of ${total}</span>
    <div class="la-page-btns">
      <button class="la-page-btn" onclick="loadConversations(${page - 1})" ${page <= 1 ? 'disabled' : ''}>←</button>
      ${Array.from({length: Math.min(totalPages, 7)}, (_, i) => {
        const p = i + 1;
        return `<button class="la-page-btn ${p === page ? 'active' : ''}" onclick="loadConversations(${p})">${p}</button>`;
      }).join('')}
      <button class="la-page-btn" onclick="loadConversations(${page + 1})" ${page >= totalPages ? 'disabled' : ''}>→</button>
    </div>
  `;
}

// ─── Users list ───────────────────────────────────────────────────────────────
let usersPage = 1;
let usersData = [];

async function loadUsers(page = 1) {
  usersPage = page;
  const tbody = document.getElementById('users-tbody');
  tbody.innerHTML = '<tr><td colspan="6"><div class="la-spinner"></div></td></tr>';

  try {
    const data = await apiFetch(`/admin/users?page=${page}&page_size=50`);
    usersData = data.users;

    if (!data.users || data.users.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6">
        <div class="la-empty"><div class="la-empty-icon">📧</div>
          <div class="la-empty-title">No leads collected yet</div>
          <div class="la-empty-sub">Email leads will appear here when users provide their details</div>
        </div></td></tr>`;
      document.getElementById('users-pagination').innerHTML = '';
      return;
    }

    tbody.innerHTML = data.users.map(u => `
      <tr>
        <td style="white-space:nowrap;font-size:12px">${fmtDateShort(u.collected_at)}</td>
        <td style="font-weight:600">${u.name || '—'}</td>
        <td><a href="mailto:${u.email}" style="color:#1e5f99;font-weight:500">${u.email}</a></td>
        <td style="max-width:200px;font-size:13px;color:#475569">${trunc(u.query, 70)}</td>
        <td style="max-width:140px;font-size:12px">
          ${u.page_url ? `<a href="${u.page_url}" target="_blank" style="color:#64748b">${trunc(u.page_url.replace('https://legalassistglobal.com', ''), 30)}</a>` : '—'}
        </td>
        <td>
          <a href="mailto:${u.email}?subject=Re: Your Legal Enquiry" class="btn btn-outline btn-sm">Reply ✉</a>
        </td>
      </tr>
    `).join('');

    const totalPages = Math.ceil(data.total / 50);
    const el = document.getElementById('users-pagination');
    if (totalPages <= 1) { el.innerHTML = ''; return; }
    el.innerHTML = `
      <span class="la-page-info">${data.total} total leads</span>
      <div class="la-page-btns">
        <button class="la-page-btn" onclick="loadUsers(${page-1})" ${page<=1?'disabled':''}>←</button>
        <button class="la-page-btn" onclick="loadUsers(${page+1})" ${page>=totalPages?'disabled':''}>→</button>
      </div>
    `;
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="6"><div class="la-alert error">Failed to load users.</div></td></tr>';
  }
}

function exportUsersCSV() {
  if (!usersData || !usersData.length) {
    showToast('No data to export');
    return;
  }
  const headers = ['Date', 'Name', 'Email', 'Query', 'Page URL', 'Session ID'];
  const rows = usersData.map(u => [
    fmtDateShort(u.collected_at), u.name || '', u.email,
    (u.query || '').replace(/,/g, ';'), u.page_url || '', u.session_id
  ]);
  const csv = [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `legalassist-leads-${new Date().toISOString().slice(0,10)}.csv`;
  a.click(); URL.revokeObjectURL(url);
  showToast('✅ CSV exported');
}
