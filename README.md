# 🚀 PiCareerAgent (picareeragent)

An autonomous, server-oriented, lightweight multi-user AI career assistant. 100% compatible with Raspberry Pi, Linux servers, and cloud daemons. Runs 24/7 silently to monitor custom announcement boards, perform smart proactive web-crawls, scan incoming emails using LLMs, auto-unsubscribe from spam newsletters, and notify you instantly on **Telegram** with ready-to-use career mentor suggestions!

*PiCareerAgent, 7/24 kesintisiz şekilde web duyuru panolarını izleyen, LLM gücüyle proaktif aramalar yapan, gelen e-postalarınızı analiz eden, spam bültenlerden otomatik abonelik iptali gerçekleştiren ve hazır CV/mülakat tavsiyeleriyle **Telegram** üzerinden anlık bildirim gönderen otonom, sunucu odaklı ve çok kullanıcılı bir yapay zeka kariyer asistanıdır.*

---

## 🗺️ Table of Contents / İçindekiler
1. [Key Features / Temel Özellikler](#-key-features--temel-özellikler)
2. [Architecture Design / Mimari Tasarım](#%EF%B8%8F-architecture-design--mimari-tasarım)
3. [Configuration Reference / Konfigürasyon Kılavuzu](#%EF%B8%8F-configuration-reference--konfig%C3%BCrasyon-k%C4%B1lavuzu)
4. [Deployment Steps / Dağıtım Adımları](#-deployment-steps--da%C4%9F%C4%B1t%C4%B1m-ad%C4%B1mlar%C4%B1)
5. [Bot Interactive Commands / Bot Komutları](#-bot-interactive-commands--bot-komutlar%C4%B1)
6. [Bilingual Guides / Detaylı Kurulum Rehberi](#-bilingual-guides--detayl%C4%B1-kurulum-rehberi)
7. [Production Best Practices & Monitoring / Canlı Ortam Tavsiyeleri](#-production-best-practices--monitoring--canl%C4%B1-ortam-tavsiyeleri)
8. [File Structure / Dosya Yapısı](#-file-structure--dosya-yap%C4%B1s%C4%B1)

---

## ✨ Key Features / Temel Özellikler

### 🇬🇧 English Features
* **🌍 Proactive AI-Driven Scans**: Generates 10 hyper-optimized local search queries daily based on user's target region (Global, TR, US, EU) and language.
* **📝 Dynamic Web Scraping Pipeline**: 
  * **Global Sweep**: Runs pre-configured high-probability career rules (bootcamps, fellowships, open-source challenges, certifications).
  * **Custom Sites Crawl**: Extracts full page markdowns using [Firecrawl](https://firecrawl.dev) and filters them strictly using customized system prompts (e.g. `look for remote internships`).
* **💼 Smart Job Application Tracker**: Fully automated database storage (`SQLite`) tracking your applications. Supports commands to view statistics, update application stages, or delete logs.
* **📬 LLM Email Analyzer**: Connects to your IMAP mailbox over secure SSL, parses incoming emails using AI, alerts you on Telegram for critical recruitment updates, and updates the application tracker status (applied ➡️ interview ➡️ accepted/rejected).
* **🚫 One-Click Spam Unsubscribe**: Identifies newsletter lists via AI and triggers programmatic unsubscribe loops immediately.
* **🔒 Multi-User Secure DB**: Secure multi-user environment locked behind `AUTHORIZED_CHAT_IDS`. Powered by SQLite with Write-Ahead Logging (WAL) and Python `threading.Lock` thread-safety guarantees.

### 🇹🇷 Türkçe Özellikler
* **🌍 Yapay Zeka Destekli Otonom Arama**: Seçtiğiniz hedef bölgeye (Global, TR, US, EU) ve dile göre günlük 10 adet hiper-optimize edilmiş arama sorgusu oluşturup webi tarar.
* **📝 Dinamik Web Tarama Hattı**:
  * **Genel Tarama**: Yüksek olasılıklı kariyer fırsatlarını (kamplar, burslar, açık kaynak programları, sertifikalar) takip eder.
  * **Özel Sayfa Takibi**: `/add` ile eklediğiniz sayfaları [Firecrawl](https://firecrawl.dev) ile kazır ve yazdığınız `/prompt` kurallarına göre filtreler.
* **💼 Akıllı İş Başvuru Takip Paneli**: SQLite tabanlı tamamen otomatik başvuru takip sistemi. Telegram üzerinden durum güncelleme, silme ve listeleme destekler.
* **📬 LLM E-Posta Analizcisi**: Gelen kutunuzu güvenli SSL üzerinden IMAP ile dinler, gelen mülakat davetlerini veya kararları AI ile yakalayıp durumu otomatik günceller.
* **🚫 Tek Tıkla Abonelik İptali**: Yapay zekanın reklam/bülten olarak tanımladığı e-postaların aboneliklerinden otomatik olarak çıkar.
* **🔒 Çok Kullanıcılı Güvenlik**: `AUTHORIZED_CHAT_IDS` ile sınırlandırılmış erişim yetkilendirmesi. SQLite WAL modu ve Python `threading.Lock` ile maksimum iş parçacığı güvenliği.

---

## 🏗️ Architecture Design / Mimari Tasarım

PiCareerAgent is written completely in modern Python and features a lightweight **bilingual edge service architecture**:

```mermaid
graph TD
    A[Telegram User] <-->|Interactive Slash Commands| B(Telegram Polling Thread)
    B <-->|Thread-Safe DB Lock| C[(SQLite DB + WAL)]
    D[Autonomous Main Loop] -->|Run every 30 mins| E[Proactive Search Sweep]
    D -->|Custom Announce Boards| F[Firecrawl Web Scraper]
    D -->|IMAP SSL Sync| G[Email Inbox Scanner]
    E & F & G -->|Unified AI Inference| H[LiteLLM Provider]
    H -->|Gemini / Llama 3 / Claude| I[Telegram Alert Dispatcher]
    I -->|Direct Message| A
```

### 🧠 Unified AI Completions (LiteLLM)
Instead of locking you into a single proprietary LLM endpoint, PiCareerAgent utilizes `litellm`. This allows seamless integration with any major AI provider:
* **Google Gemini** (Generous free tier via Google AI Studio)
* **OpenRouter** (Llama 3, DeepSeek, Qwen)
* **OpenAI** (GPT-4o, GPT-4o-mini)
* **Anthropic** (Claude 3.5 Sonnet)

---

## ⚙️ Configuration Reference / Konfigürasyon Kılavuzu

Configuration is managed strictly via environmental variables defined in the `.env` file:

| Variable / Değişken | Type | Required | Description / Açıklama |
| :--- | :--- | :--- | :--- |
| `LLM_PROVIDER` | String | Yes | Provider name: `gemini`, `openai`, `openrouter`, `anthropic`. |
| `LLM_MODEL` | String | Yes | Specific model name (e.g. `gemini/gemini-1.5-flash` or `meta-llama/llama-3.3-70b-instruct`). |
| `LLM_API_KEY` | String | Yes | API access key for your chosen provider. |
| `REGION` | String | Yes | Default proactive search region: `global`, `tr`, `us`, `eu`. |
| `LANGUAGE` | String | Yes | System messaging language: `en`, `tr`. |
| `FIRECRAWL_API_KEY` | String | Yes | Web scraping engine API key from `firecrawl.dev`. |
| `TELEGRAM_BOT_TOKEN` | String | Yes | Telegram API token obtained from `@BotFather`. |
| `TELEGRAM_CHAT_ID` | String | Yes | Primary Telegram chat ID for system alerts. |
| `AUTHORIZED_CHAT_IDS` | String | Yes | Comma-separated list of authorized chat IDs allowed to interact with the bot. |
| `EMAIL_ACTIVE` | Boolean | No | Set `True` to activate IMAP scanning daemon thread. |
| `EMAIL_AUTO_UNSUBSCRIBE` | Boolean | No | Set `True` to let AI unsubscribe from marketing lists. |
| `EMAIL_1_IMAP_SERVER` | String | No | Secure IMAP Server URL (e.g. `imap.gmail.com`). |
| `EMAIL_1_PORT` | Integer | No | IMAP Server Port (e.g. `993` for SSL). |
| `EMAIL_1_USER` | String | No | Your email address username. |
| `EMAIL_1_PASSWORD` | String | No | Email password or Gmail App-specific password. |
| `LOG_FILE_PATH` | String | No | Filepath to write logs to (default: `data/app.log`). |

---

## 🚀 Deployment Steps / Dağıtım Adımları

Deploying PiCareerAgent in a production environment takes less than 3 minutes.

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/ibodeth/PiCareerAgent.git
cd PiCareerAgent
```

### 2️⃣ Initialize Environment File
Create a new `.env` file in the root directory and configure your keys:
```ini
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-1.5-flash
LLM_API_KEY=AIzaSy...

REGION=tr
LANGUAGE=tr

FIRECRAWL_API_KEY=fc-...
TELEGRAM_BOT_TOKEN=8567...
TELEGRAM_CHAT_ID=7500...
AUTHORIZED_CHAT_IDS=7500...

EMAIL_ACTIVE=True
EMAIL_AUTO_UNSUBSCRIBE=True
EMAIL_1_IMAP_SERVER=imap.gmail.com
EMAIL_1_PORT=993
EMAIL_1_USER=your_email@gmail.com
EMAIL_1_PASSWORD=your_gmail_app_password
```

### 3️⃣ Build and Launch Service
Run the background daemon via Docker Compose:
```bash
docker compose up -d --build
```

### 4️⃣ Verify Startup Logs
Ensure everything initialized perfectly:
```bash
docker compose logs -f picareeragent
```

---

## 📱 Bot Interactive Commands / Bot Komutları

Interact directly with your agent on Telegram using these interactive slash commands:

### ⚙️ System & Rules / Sistem ve Ayarlar
* `/start` - Activate and register your profile on SQLite database.
* `/settings` - Start the step-by-step interactive wizard to customize language and targeted region.
* `/prompt <instructions>` - Set custom filtering rules for tracked sites (e.g. `/prompt look for remote internships`).
* `/prompt reset` - Return to standard career opportunity filtering rules.

### 🔗 Custom Site Tracking / Özel Sayfa Takibi
* `/add <URL>` - Track a custom announcements page, career site, or community board.
* `/list` - List all websites currently tracked under your account.
* `/remove <ID>` - Stop tracking a specific website.

### 💼 Application Tracker / Başvuru Takip Paneli
* `/apply <Company/Opportunity>` - Log a new job/bootcamp application.
* `/applications` - View all logged applications, stages, and stats.
* `/status <ID> <stage>` - Update application stage (e.g. `/status 1 interview`, `/status 1 accepted`).
* `/delete <ID>` - Delete an application log from database.

---

## 🔑 Easy Guide to Getting Your Keys / Anahtar Kılavuzu

1. **Google Gemini**: Sign up at [Google AI Studio](https://aistudio.google.com/), click **Get API Key**. Extremely fast, reliable, and free of charge.
2. **Firecrawl**: Sign up at [Firecrawl.dev](https://www.firecrawl.dev/) for a free API token allowing lightning-fast markdown extraction.
3. **Telegram Bot Token**: Send `/newbot` to the official `@BotFather` account on Telegram, name your bot, and copy the HTTP API Token.
4. **Telegram Chat ID**: Message `@userinfobot` to get your numeric Chat ID. Remember to press **Start** on your new bot!
5. **Gmail App Password**: Go to your Google Account Security, enable **2-Step Verification**, search **App Passwords**, name it `PiCareerAgent`, and copy the 16-character code.

---

## 🔒 Production Best Practices & Monitoring / Canlı Ortam Tavsiyeleri

When running PiCareerAgent 24/7 on servers or Raspberry Pi:
* **SQLite Persistence**: Ensure that `data/` directory is mounted correctly using Docker volumes. This guarantees database states survive container updates and re-builds.
* **Thread Safety**: The system applies strict `threading.Lock()` controls during SQLite operations to guarantee perfect database integrity under concurrent web sweeps and Telegram polling.
* **Rate Limits**: LiteLLM and Firecrawl are configured with strict timeouts and error handler loops to prevent indefinite hangs or API quota exhaustion.
* **OS Signals**: The container is equipped with clean signal handlers (`SIGINT`, `SIGTERM`) that release active threads, commit database transactions, and dispatch offline notifications via Telegram on shutdown.

---

## 📁 File Structure / Dosya Yapısı

```
PiCareerAgent/
├── app.py              # Pure-Python autonomous core engine
├── requirements.txt    # Production dependencies
├── Dockerfile          # Multi-architecture (ARM/AMD64) Docker file
├── docker-compose.yml  # Volume-mounted daemon run config
├── README.md           # This master documentation
└── data/               # Persistent database directory
    └── careeragent.db  # Multi-user thread-safe SQLite database
```

---

Got ideas, bugs, or feature requests? Feel free to open a Pull Request! Let's land that dream tech role! 🚀
*Bir fikir veya hata bildiriminiz mi var? Hemen bir Pull Request açmaktan çekinmeyin! Hayalinizdeki işe ulaşmanız dileğiyle!* 🚀
