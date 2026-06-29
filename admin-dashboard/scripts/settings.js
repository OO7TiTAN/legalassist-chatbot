// ─── Settings ─────────────────────────────────────────────────────────────────
async function loadSettings() {
  try {
    const data = await apiFetch('/admin/settings');

    document.getElementById('s-admin-email').value    = data.admin_email || '';
    document.getElementById('s-smtp-host').value      = data.smtp_host || '';
    document.getElementById('s-smtp-port').value      = data.smtp_port || '587';
    document.getElementById('s-smtp-user').value      = data.smtp_user || '';
    document.getElementById('s-smtp-password').value  = '';  // never pre-fill password
    document.getElementById('s-smtp-from-name').value = data.smtp_from_name || '';
    document.getElementById('s-bot-name').value       = data.chatbot_name || '';
    document.getElementById('s-greeting').value       = data.chatbot_greeting || '';
    document.getElementById('s-auto-transcripts').checked = data.auto_email_transcripts === 'true';

  } catch (e) {
    showSettingsAlert('❌ Failed to load settings.', 'error');
  }
}

async function saveSettings(e) {
  e.preventDefault();
  const btn = document.getElementById('save-btn');
  btn.textContent = '⏳ Saving...';
  btn.disabled = true;

  const payload = {
    admin_email:               document.getElementById('s-admin-email').value.trim(),
    smtp_host:                 document.getElementById('s-smtp-host').value.trim(),
    smtp_port:                 document.getElementById('s-smtp-port').value.trim(),
    smtp_user:                 document.getElementById('s-smtp-user').value.trim(),
    smtp_from_name:            document.getElementById('s-smtp-from-name').value.trim(),
    chatbot_name:              document.getElementById('s-bot-name').value.trim(),
    chatbot_greeting:          document.getElementById('s-greeting').value.trim(),
    auto_email_transcripts:    document.getElementById('s-auto-transcripts').checked ? 'true' : 'false',
    email_notifications_enabled: 'true',
  };

  // Only include password if user actually typed one
  const pass = document.getElementById('s-smtp-password').value;
  if (pass && pass !== '***') payload.smtp_password = pass;

  // Remove empty strings from payload (don't overwrite with blanks)
  Object.keys(payload).forEach(k => { if (payload[k] === '') delete payload[k]; });

  try {
    await apiFetch('/admin/settings', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    showSettingsAlert('✅ Settings saved successfully!', 'success');
    showToast('✅ Settings saved!');
  } catch (err) {
    showSettingsAlert('❌ Failed to save settings. Please try again.', 'error');
  } finally {
    btn.textContent = '💾 Save Settings';
    btn.disabled = false;
  }
}

function showSettingsAlert(msg, type) {
  const el = document.getElementById('settings-alert');
  el.className = `la-alert ${type}`;
  el.innerHTML = msg;
  el.style.display = 'flex';
  if (type === 'success') setTimeout(() => { el.style.display = 'none'; }, 4000);
}
