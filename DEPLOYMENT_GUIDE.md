# LegalAssist Chatbot — Deployment Guide

## What You've Built

A full-stack AI chatbot system with:
- **RAG chatbot** that answers questions based on your website's content
- **Email notifications** when users submit their contact details  
- **Admin dashboard** with analytics, conversation viewer, and settings
- **WordPress widget** that embeds into your site in one line of code
- **Auto-scraping** — the AI re-learns your site whenever you update it

---

## Step 1: Deploy Backend to Render.com

### 1.1 Push code to GitHub
Create a GitHub repository and push the entire `legalassist-chatbot/` folder to it.

```bash
git init
git add .
git commit -m "Initial chatbot deployment"
git remote add origin https://github.com/YOUR_USERNAME/legalassist-chatbot.git
git push -u origin main
```

### 1.2 Create Render Web Service
1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repository
3. Render will detect `render.yaml` automatically — click **Apply**
4. In **Environment Variables**, add:

| Key | Value |
|-----|-------|
| `OPENAI_API_KEY` | `sk-your-actual-openai-key` |
| `ADMIN_PASSWORD` | Choose a strong password (e.g. `Legal@2024!`) |

5. Click **Create Web Service**
6. Wait ~5 minutes for the first deploy
7. Your backend URL will be: `https://legalassist-chatbot.onrender.com`

> **Important:** The free Render tier "sleeps" after 15 minutes of inactivity.  
> Upgrade to the **$7/month Starter** plan to keep it always-on for a live site.

---

## Step 2: Update URLs in Widget & Dashboard

After deploying, update two files with your actual Render URL:

### In `wordpress-embed/chatbot-widget.js` (line ~12):
```js
backendUrl: 'https://legalassist-chatbot.onrender.com',
```

### In `wordpress-embed/chatbot-proxy.php` (line ~17):
```php
define('LA_BACKEND_URL', 'https://legalassist-chatbot.onrender.com');
```

### In `admin-dashboard/index.html` (last `<script>` block):
```js
const API_BASE = 'https://legalassist-chatbot.onrender.com';
```

---

## Step 3: Add Widget to WordPress

### Option A: Simple Embed (5 minutes)
1. In WordPress Admin → **Appearance** → **Theme File Editor**
2. Open `footer.php` (or your active theme's footer)
3. Before `</body>`, add:
```html
<script src="https://legalassist-chatbot.onrender.com/admin-ui/chatbot-widget.js"></script>
```

### Option B: Via PHP Proxy (Recommended for security)
1. Copy `chatbot-proxy.php` to your theme folder:
   `/wp-content/themes/YOUR-THEME/chatbot-proxy.php`
2. In `footer.php` before `</body>`:
```html
<script>
  window.LA_PROXY_URL = '<?php echo get_template_directory_uri(); ?>/chatbot-proxy.php';
</script>
<script src="/wp-content/themes/YOUR-THEME/chatbot-widget.js"></script>
```
3. Upload `chatbot-widget.js` to the same theme folder

### Option C: WordPress Plugin (Best long-term)
Create a file `/wp-content/plugins/legalassist-chatbot/legalassist-chatbot.php`:
```php
<?php
/**
 * Plugin Name: Legal Assist Chatbot
 * Description: AI chatbot for Legal Assist UK
 * Version: 1.0
 */
function la_add_chatbot() {
    echo '<script src="https://legalassist-chatbot.onrender.com/admin-ui/chatbot-widget.js"></script>';
}
add_action('wp_footer', 'la_add_chatbot');
```

---

## Step 4: Access Your Admin Dashboard

1. Upload the `admin-dashboard/` folder to your Render static files, OR  
   host it separately (e.g. on Cloudflare Pages — it's free!)
2. Navigate to your dashboard URL
3. Login with the `ADMIN_PASSWORD` you set in Render
4. Go to **Settings** → configure your admin email + SMTP details
5. Go to **Content Index** → click **Re-Index Now** to trigger the first scrape

---

## Step 5: Configure Email Notifications

In the Admin Dashboard → **Settings**:

| Field | Example |
|-------|---------|
| Admin Email | `admin@legalassist.co.uk` |
| SMTP Host | `smtp.gmail.com` |
| SMTP Port | `587` |
| SMTP Username | `your@gmail.com` |
| SMTP Password | Your Gmail App Password |

> For Gmail: Enable 2FA → Google Account → Security → App Passwords → Generate one for "Mail"

---

## How the Chatbot Works

```
User types question
    ↓
Widget sends to your backend (via PHP proxy)
    ↓
Backend searches ChromaDB for relevant content from legalassist.co.uk
    ↓
Top matching chunks sent to OpenAI GPT-4o with your site's context
    ↓
AI generates a relevant, site-specific answer
    ↓
Response returned to user with a suggested page link
    ↓
Conversation stored in SQLite database
    ↓
Admin can review all conversations in dashboard
```

---

## Keeping the AI Up-to-Date

Whenever you **add or update pages** on your website:
1. Go to Admin Dashboard → **Content Index**
2. Click **Re-Index Now**
3. The AI will re-learn your new content within 5 minutes

---

## File Structure

```
legalassist-chatbot/
├── backend/
│   ├── main.py              ← FastAPI app entry point
│   ├── config.py            ← Settings from env vars
│   ├── database.py          ← SQLite schema (SQLModel)
│   ├── auth.py              ← JWT admin authentication
│   ├── scraper.py           ← Website content scraper
│   ├── embeddings.py        ← ChromaDB vector store
│   ├── rag.py               ← RAG pipeline (OpenAI + ChromaDB)
│   ├── email_service.py     ← Email notifications
│   ├── requirements.txt     ← Python dependencies
│   ├── .env.example         ← Environment variable template
│   └── routers/
│       ├── chat.py          ← Chat, email capture, pageview endpoints
│       ├── admin.py         ← Admin CRUD, settings, scrape trigger
│       └── analytics.py     ← Stats, charts, traffic data
├── admin-dashboard/
│   ├── index.html           ← Login page
│   ├── dashboard.html       ← Main dashboard
│   ├── styles/admin.css     ← Dashboard styles
│   └── scripts/
│       ├── auth.js          ← Auth utilities
│       ├── dashboard.js     ← Overview + routing
│       ├── conversations.js ← Conversation + user tables
│       ├── analytics.js     ← Charts + traffic + content index
│       └── settings.js      ← Settings form
├── wordpress-embed/
│   ├── chatbot-widget.js    ← Drop-in chat widget
│   └── chatbot-proxy.php    ← WordPress security proxy
└── render.yaml              ← Render.com deployment config
```

---

## Cost Estimate

| Service | Cost |
|---------|------|
| Render Starter (backend) | ~$7/month |
| OpenAI GPT-4o | ~$0.005/message (very low) |
| Cloudflare Pages (admin dashboard) | Free |
| **Total** | **~$7–10/month** |

---

## Support

If you encounter any issues:
1. Check Render logs: Dashboard → Your Service → Logs
2. Test the API: `https://legalassist-chatbot.onrender.com/docs`
3. Test health: `https://legalassist-chatbot.onrender.com/health`
