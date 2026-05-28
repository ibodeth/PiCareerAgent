# 🚀 PiCareerAgent (picareeragent)

Hey there! Welcome to **PiCareerAgent** – your smart, secure, server-oriented, and autonomous multi-user technology career assistant. 

Designed specifically with a **server-oriented architecture**, PiCareerAgent is lightweight, extremely resource-efficient, and **100% compatible with Raspberry Pi** and other ARM-based systems, making it the perfect daemon to run 24/7 silently in the background on your home server, VPS, or Pi.

If you are a developer, designer, or tech enthusiast who is tired of constantly monitoring dozens of websites for free bootcamps, hackathons, certifications, or CTFs, this project is built just for you. 

PiCareerAgent runs silently in the background, scans the web, monitors your emails, and instantly alerts you on **Telegram** whenever an amazing opportunity pops up. It comes with a built-in **AI Career Mentor** to provide CV advice and next-step actions for every opportunity it finds.

---

## ✨ Key Features

* **🌍 Autonomous Global Opportunity Hunting**: PiCareerAgent uses a advanced AI (like Gemini, ChatGPT, or Claude) to generate **10 highly-optimized search queries** daily, tailored to your region and language.
* **🗺️ Dual-Pipeline Crawling**: 
  * **General Search**: Runs on default, pre-configured high-quality career rules so you never miss global opportunities.
  * **Custom Tracked Sites**: Sourced from your `/add` commands and filtered strictly based on your personal `/prompt` rules!
* **📝 Customizable AI Filters (`/prompt`)**: Tell the AI exactly what to look for on your custom tracked sites (e.g., *“Only find internship posts, course schedules, or exam dates”*).
* **💡 AI Career Mentor Advice**: Every alert includes:
  * 🎯 **Skills to Practice**: Core technologies to learn.
  * 💼 **CV Value**: How to present this project/experience to tech recruiters.
  * 🏃 **First Step**: A concrete task you can tackle *today*.
* **📬 Smart Email Inbox Sync**: Scans your IMAP account using AI to spot bootcamps or career replies. It automatically updates the job tracker status if you get an interview request, accept, or reject mail!
* **🚫 AI-Powered One-Click Unsubscribe**: Automatically triggers unsubscribe requests for marketing/newsletter emails identified by AI.
* **🔒 Multi-User Secure DB**: Built on SQLite with WAL (Write-Ahead Logging) and thread-safe locks. Secured via `AUTHORIZED_CHAT_IDS` access list.

---

## 🛠️ Super Simple 3-Step Setup

### Step 1: Clone the Project
Download the project files into a folder on your machine.

### Step 2: Configure Your Settings (`.env`)
Create a `.env` file in the root directory:

```ini
# AI Provider (Gemini is highly recommended and offers a generous free tier!)
LLM_PROVIDER=gemini
LLM_MODEL=gemini-3.5-flash
LLM_API_KEY=your_gemini_api_key_here

# Default Target Region & Language
REGION=global
LANGUAGE=en

# Web Crawler API (Get a free key from firecrawl.dev)
FIRECRAWL_API_KEY=your_firecrawl_api_key_here

# Telegram Bot (Create one via @BotFather in 1 minute!)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here

# Multi-User Access Security (Comma-separated Telegram Chat IDs)
AUTHORIZED_CHAT_IDS=your_telegram_chat_id_here

# Email Integration (True/False)
EMAIL_ACTIVE=True
EMAIL_AUTO_UNSUBSCRIBE=True
EMAIL_1_IMAP_SERVER=imap.gmail.com
EMAIL_1_PORT=993
EMAIL_1_USER=yourname@gmail.com
EMAIL_1_PASSWORD=your_gmail_app_password_here
```

### Step 3: Run the Bot
Spin it up instantly using Docker:
```bash
docker compose up -d
```
Your local files are mounted dynamically for zero-rebuild runtime updates. You can watch what the bot is doing in real-time:
```bash
docker compose logs -f picareeragent
```

---

## 📱 Bot Commands

Interact directly with your agent on Telegram:

### ⚙️ Settings & Rules
* `/start` - Activate and register your profile.
* `/settings` - Start the step-by-step interactive wizard to customize language (EN, TR, ALL) and region (Global, Turkey, USA, Europe).
* `/prompt <instructions>` - Set custom AI filtering instructions for your tracked websites (e.g. `/prompt look for remote internships`).
* `/prompt reset` - Return to standard career opportunity filtering rules.

### 🔗 Custom Site Tracking
* `/add <URL>` - Track a custom announcements page or community board.
* `/list` - List all websites you are currently tracking.
* `/remove <ID>` - Stop tracking a website.

### 💼 Job Application Tracker
* `/apply <Company/Bootcamp>` - Log a new job application.
* `/applications` - View all registered applications and their current status.
* `/status <ID> <stage>` - Update status stage (e.g. `/status 1 interview` / accept / reject).
* `/delete <ID>` - Delete an application log.

---

## 🔑 Easy Guide to Getting Your Keys

1. **Gemini API Key**: Log in to [Google AI Studio](https://aistudio.google.com/), click **Get API Key**.
2. **Firecrawl API Key**: Sign up at [Firecrawl.dev](https://www.firecrawl.dev/) for a free API token.
3. **Telegram Bot Token**: Message `@BotFather` on Telegram, send `/newbot`, and copy the HTTP API Token.
4. **Telegram Chat ID**: Message `@userinfobot` to get your Chat ID. Remember to press **Start** on your own bot!
5. **Gmail App Password**: Go to Google Account Security, enable **2-Step Verification**, search **App Passwords**, name it `PiCareerAgent`, and copy the 16-character code.

---

## 📁 File Structure

```
picareeragent/
├── app.py              # Pure-python core engine
├── requirements.txt    # Light dependencies
├── Dockerfile          # ARM-compatible build steps
├── docker-compose.yml  # Volume-mounted daemon run config
├── .env                # Your credentials (keep safe!)
└── data/               # Persistent database directory
    └── careeragent.db  # Multi-user thread-safe SQLite database
```

---

Got ideas, bugs, or feature requests? Feel free to open a Pull Request! Let's land that dream tech role! 🚀
