// ─── Analytics charts ─────────────────────────────────────────────────────────
let analyticsCharts = {};

async function loadAnalyticsCharts() {
  try {
    const [daily, queries] = await Promise.all([
      apiFetch('/admin/analytics/daily-sessions?days=30'),
      apiFetch('/admin/analytics/top-queries?limit=12'),
    ]);

    // Daily sessions chart
    const dailyCtx = document.getElementById('chart-analytics-daily').getContext('2d');
    if (analyticsCharts.daily) analyticsCharts.daily.destroy();
    analyticsCharts.daily = new Chart(dailyCtx, {
      type: 'bar',
      data: {
        labels: daily.map(d => { const [,m,day] = d.date.split('-'); return `${day}/${m}`; }),
        datasets: [{
          label: 'Conversations',
          data: daily.map(d => d.count),
          backgroundColor: 'rgba(30,95,153,0.75)',
          borderRadius: 6,
          borderSkipped: false,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#94a3b8', font: { size: 10 }, maxTicksLimit: 10 } },
          y: { grid: { color: '#f1f5f9' }, ticks: { color: '#94a3b8', font: { size: 11 } }, beginAtZero: true },
        },
      },
    });

    // Top queries horizontal bar
    const qCtx = document.getElementById('chart-queries').getContext('2d');
    if (analyticsCharts.queries) analyticsCharts.queries.destroy();
    const topN = queries.slice(0, 8);
    analyticsCharts.queries = new Chart(qCtx, {
      type: 'bar',
      data: {
        labels: topN.map(q => trunc(q.query, 30)),
        datasets: [{
          label: 'Count',
          data: topN.map(q => q.count),
          backgroundColor: topN.map((_, i) => {
            const colors = ['#0f3460','#1e5f99','#2d7dd2','#3b8fd9','#06b6d4','#0891b2','#0e7490','#155e75'];
            return colors[i % colors.length];
          }),
          borderRadius: 6,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { color: '#f1f5f9' }, ticks: { color: '#94a3b8', font: { size: 11 } } },
          y: { grid: { display: false }, ticks: { color: '#374151', font: { size: 11 } } },
        },
      },
    });

  } catch (e) {
    console.error('[Analytics] Error:', e);
  }
}

// ─── Traffic ──────────────────────────────────────────────────────────────────
async function loadTraffic() {
  const body = document.getElementById('traffic-body');
  body.innerHTML = '<div class="la-spinner"></div>';

  try {
    const data = await apiFetch('/admin/analytics/traffic?days=30');

    if (!data || data.length === 0) {
      body.innerHTML = `
        <div class="la-empty">
          <div class="la-empty-icon">🌐</div>
          <div class="la-empty-title">No traffic data yet</div>
          <div class="la-empty-sub">Page views are tracked when users visit pages with the chat widget open</div>
        </div>`;
      return;
    }

    const maxViews = Math.max(...data.map(d => d.views));
    body.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:14px">
        ${data.map((item, i) => {
          const pct = Math.round((item.views / maxViews) * 100);
          const shortUrl = item.url.replace('https://legalassist.co.uk', '') || '/';
          return `
            <div>
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
                <a href="${item.url}" target="_blank"
                   style="font-size:13px;color:#0f3460;font-weight:${i < 3 ? 600 : 500};text-decoration:none">
                  ${shortUrl}
                </a>
                <span style="font-size:13px;font-weight:700;color:#1e5f99">${item.views.toLocaleString()}</span>
              </div>
              <div style="height:6px;background:#eef2f7;border-radius:100px;overflow:hidden">
                <div style="height:100%;width:${pct}%;background:${i===0?'linear-gradient(90deg,#0f3460,#06b6d4)':'rgba(30,95,153,0.5)'};border-radius:100px;transition:width 0.6s ${i*0.05}s"></div>
              </div>
            </div>`;
        }).join('')}
      </div>
    `;
  } catch (e) {
    body.innerHTML = '<div class="la-alert error">❌ Failed to load traffic data.</div>';
  }
}

// ─── Content pages ────────────────────────────────────────────────────────────
let scrapePollingInterval = null;

async function loadContentPages() {
  const tbody = document.getElementById('content-tbody');
  const countBadge = document.getElementById('indexed-count');
  tbody.innerHTML = '<tr><td colspan="5"><div class="la-spinner"></div></td></tr>';

  try {
    const [pages, status] = await Promise.all([
      apiFetch('/admin/content-pages'),
      apiFetch('/admin/scrape-status'),
    ]);

    countBadge.textContent = `${pages.pages.length} pages • ${status.indexed_chunks} chunks`;

    if (status.last_run) {
      document.getElementById('scrape-last').textContent = `Last indexed: ${fmtDate(status.last_run)}`;
    }
    if (status.running) {
      document.getElementById('scrape-status-box').style.display = 'flex';
      document.getElementById('scrape-status-msg').textContent = 'Scraping in progress... this may take a few minutes.';
      startScrapePolling();
    }

    if (!pages.pages || pages.pages.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5">
        <div class="la-empty"><div class="la-empty-icon">📄</div>
          <div class="la-empty-title">No pages indexed yet</div>
          <div class="la-empty-sub">Click "Re-Index Now" to scrape and index the website</div>
        </div></td></tr>`;
      return;
    }

    tbody.innerHTML = pages.pages.map(p => `
      <tr>
        <td style="max-width:220px;font-size:12px">
          <a href="${p.url}" target="_blank" style="color:#1e5f99" title="${p.url}">${p.url.replace('https://legalassist.co.uk', '') || '/'}</a>
        </td>
        <td style="font-size:13px;font-weight:500">${trunc(p.title, 45)}</td>
        <td><span class="la-badge ${p.chunk_count > 0 ? 'blue' : 'gray'}">${p.chunk_count}</span></td>
        <td><span class="la-badge ${p.status === 'indexed' ? 'green' : p.status === 'error' ? 'red' : 'amber'}">${p.status}</span></td>
        <td style="font-size:12px;color:#94a3b8;white-space:nowrap">${p.last_scraped ? fmtDate(p.last_scraped) : '—'}</td>
      </tr>
    `).join('');

  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5"><div class="la-alert error">Failed to load content pages.</div></td></tr>';
  }
}

async function triggerScrape() {
  const btn = document.getElementById('scrape-btn');
  const box = document.getElementById('scrape-status-box');
  const msg = document.getElementById('scrape-status-msg');

  btn.disabled = true;
  btn.textContent = '⏳ Starting...';

  try {
    await apiFetch('/admin/scrape', { method: 'POST' });
    box.className = 'la-alert info';
    box.style.display = 'flex';
    msg.textContent = 'Scraping in progress... please wait 2–5 minutes.';
    showToast('🔄 Re-index started!');
    startScrapePolling();
  } catch (e) {
    box.className = 'la-alert error';
    box.style.display = 'flex';
    msg.textContent = 'Failed to start scrape. Check backend connection.';
    btn.disabled = false;
    btn.textContent = '🔄 Re-Index Now';
  }
}

function startScrapePolling() {
  if (scrapePollingInterval) return;
  scrapePollingInterval = setInterval(async () => {
    try {
      const status = await apiFetch('/admin/scrape-status');
      if (!status.running) {
        clearInterval(scrapePollingInterval);
        scrapePollingInterval = null;
        const box = document.getElementById('scrape-status-box');
        const msg = document.getElementById('scrape-status-msg');
        const btn = document.getElementById('scrape-btn');
        if (status.last_result && !status.last_result.error) {
          box.className = 'la-alert success';
          msg.textContent = `✅ Done! Indexed ${status.last_result.total_pages} pages, ${status.last_result.total_chunks} chunks.`;
        } else if (status.last_result?.error) {
          box.className = 'la-alert error';
          msg.textContent = '❌ Scrape failed: ' + status.last_result.error;
        }
        btn.disabled = false;
        btn.textContent = '🔄 Re-Index Now';
        // Reload page list
        setTimeout(loadContentPages, 500);
      }
    } catch (e) {}
  }, 5000);
}
