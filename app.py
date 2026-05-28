import os
import sys
import time
import signal
import json
import logging
import sqlite3
import hashlib
import threading
import requests
import imaplib
import ssl
import email
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from email.header import decode_header
from urllib.parse import urlparse, urlunparse
from dotenv import load_dotenv

# Import LiteLLM for unified AI model completions across all providers
import litellm
from litellm import completion

# Set LiteLLM request timeout and retries globally to prevent indefinite hanging on slow API endpoints
litellm.request_timeout = 30
litellm.num_retries = 2

# Global lifecycle variables and thread safety locks
keep_running = True
db_lock = threading.Lock()

# Multi-lingual Localization Dictionary for pristine bilingual user experiences
LOCALIZATION = {
    "en": {
        "welcome_new": (
            "🚀 *Welcome to CareerAgent!* 🚀\n\n"
            "Your account has been registered successfully. Use the following commands to manage your targets:\n"
            "🔗 `/add <URL>` - Track a custom announcement page.\n"
            "📋 `/list` - List custom websites you are currently tracking.\n"
            "🗑️ `/remove <ID>` - Remove a website from tracking.\n"
            "⚙️ `/settings` - Open settings to change language & search region.\n\n"
            "💼 *JOB APPLICATION TRACKER:* \n"
            "📝 `/apply <Opportunity/Company Name>` - Register a job application.\n"
            "📊 `/applications` - List all your applications & current status.\n"
            "🚦 `/status <App_ID> <New_Status>` - Update application stage (e.g. applied, interview, accepted, rejected).\n"
            "🗑️ `/delete <App_ID>` - Delete a recorded job application."
        ),
        "welcome_back": (
            "👋 *Welcome Back!*\n\n"
            "CareerAgent is online. Send commands directly or type `/settings` to customize your crawler."
        ),
        "unauthorized": "❌ *Access Denied.* You do not have permissions to access this bot.",
        "start_first": "⚠️ Please activate your account first by sending the `/start` command.",
        "add_url_missing": "⚠️ *Error:* Please specify a URL.\nUsage: `/add https://example.com`",
        "add_url_success": "✅ *Added to Tracking List:*\n🔗 {url}\n\nAI will scan this website daily for announcements. You will only be notified when new announcements are detected!",
        "add_url_error": "❌ *Error:* Failed to add URL: {error}",
        "list_empty": "📭 *Your tracking list is empty.* Add a target announcement website using `/add <URL>`",
        "list_title": "📋 *Tracked Custom Websites:*\n\n{sites}",
        "remove_id_missing": "⚠️ *Error:* Please specify a target ID. Usage: `/remove <ID>`",
        "remove_success": "🗑️ *Removed from tracking.* (ID: {id})",
        "remove_not_found": "❌ Target ID not found under your account.",
        "apply_name_missing": "⚠️ *Error:* Please specify opportunity/company name. Usage: `/apply Google Cloud Bootcamp`",
        "apply_success": "📝 *Application Logged!* 🚀\n\n📌 *Opportunity:* `{name}`\n🚦 *Status:* `Applied` (Use `/status <ID> <stage>` to update)",
        "apps_empty": "📭 *No job applications logged yet.*\nStart tracking using: `/apply <Company Name>`",
        "apps_title": "💼 *JOB APPLICATION TRACKER* 💼\n\n{apps}",
        "status_missing": "⚠️ *Error:* Missing arguments.\nUsage: `/status <ID> <New_Status>`\nExample: `/status 1 interview`",
        "status_success": "🚦 *Application Status Updated!* (ID: {id})\n👉 Stage: *{status}*",
        "status_not_found": "❌ Target Application ID not found.",
        "delete_id_missing": "⚠️ *Error:* Please specify Application ID. Usage: `/delete <ID>`",
        "delete_success": "🗑️ *Application record deleted.* (ID: {id})",
        "delete_not_found": "❌ Target Application ID not found.",
        "settings_title": "⚙️ *CareerAgent Settings* ⚙️\n\nCustomize your localized AI search crawls and system language below:\n\n👤 *User ID:* `{chat_id}`\n🌐 *Target Region:* `{region}`\n🗣️ *System Language:* `{language}`",
        "settings_btn_lang": "Change Language",
        "settings_btn_region": "Change Region",
        "settings_lang_select": "🗣️ *Select System Language:*",
        "settings_region_select": "🌐 *Select Target Search Region:*",
        "settings_updated": "✅ Settings successfully updated!"
    },
    "tr": {
        "welcome_new": (
            "🚀 *CareerAgent Asistanına Hoş Geldiniz!* 🚀\n\n"
            "Hesabınız başarıyla oluşturuldu. Bota aşağıdaki komutlarla hükmedebilirsiniz:\n"
            "🔗 `/add <URL>` - Takip edilecek duyuru veya kariyer sayfası ekler.\n"
            "📋 `/list` - Takip ettiğiniz özel sayfaları listeler.\n"
            "🗑️ `/remove <ID>` - Sayfa takibini sonlandırır.\n"
            "⚙️ `/settings` - Dil ve hedef arama bölgesi ayarlarını açar.\n\n"
            "💼 *İŞ BAŞVURU TAKİP PANELİ:* \n"
            "📝 `/apply <Kurum/Fırsat Adı>` - Yeni bir iş başvurusu kaydeder.\n"
            "📊 `/applications` - Tüm başvurularınızı ve aşamalarını listeler.\n"
            "🚦 `/status <App_ID> <Yeni_Durum>` - Başvuru durumunu günceller (applied, interview, accepted, rejected).\n"
            "🗑️ `/delete <App_ID>` - Başvuru kaydını siler."
        ),
        "welcome_back": (
            "👋 *Tekrar Hoş Geldiniz!*\n\n"
            "Kariyer asistanınız arka planda çalışıyor. Tercihlerinizi özelleştirmek için `/settings` yazabilirsiniz."
        ),
        "unauthorized": "❌ *Erişim Engellendi.* Bu botu kullanma izniniz bulunmamaktadır.",
        "start_first": "⚠️ Lütfen önce `/start` komutunu göndererek hesabınızı aktifleştirin.",
        "add_url_missing": "⚠️ *Hata:* Lütfen bir URL belirtin.\nKullanım: `/add https://example.com`",
        "add_url_success": "✅ *Takip Listesine Eklendi:*\n🔗 {url}\n\nAI bu adresi günlük döngüde tarayacak. Sadece yeni bir duyuru/değişiklik tespit edildiğinde bilgilendirileceksiniz!",
        "add_url_error": "❌ *Hata:* Adres eklenirken sorun oluştu: {error}",
        "list_empty": "📭 *Takip listeniz boş.* `/add <URL>` ile takip edilecek site ekleyebilirsiniz.",
        "list_title": "📋 *Takip Edilen Özel Siteler:*\n\n{sites}",
        "remove_id_missing": "⚠️ *Hata:* Lütfen silinecek site ID'sini belirtin. Kullanım: `/remove <ID>`",
        "remove_success": "🗑️ *Takip listesinden kaldırıldı.* (ID: {id})",
        "remove_not_found": "❌ Belirtilen ID ile eşleşen takip edilen site bulunamadı.",
        "apply_name_missing": "⚠️ *Hata:* Lütfen başvurduğunuz kurum/fırsat adını girin. Kullanım: `/apply Google Cloud Kampı`",
        "apply_success": "📝 *Başvuru Kaydedildi!* 🚀\n\n📌 *Fırsat:* `{name}`\n🚦 *Durum:* `Applied` (Aşama değiştirmek için: `/status <ID> <aşama>` kullanın)",
        "apps_empty": "📭 *Kayıtlı herhangi bir başvurunuz bulunmamaktadır.*\nYeni eklemek için: `/apply <Firma Adı>`",
        "apps_title": "💼 *İŞ BAŞVURU TAKİP PANELİ* 💼\n\n{apps}",
        "status_missing": "⚠️ *Hata:* Eksik argüman.\nKullanım: `/status <ID> <Yeni_Durum>`\nÖrnek: `/status 1 interview`",
        "status_success": "🚦 *Başvuru Durumu Güncellendi!* (ID: {id})\n👉 Aşama: *{status}*",
        "status_not_found": "❌ Belirtilen ID ile eşleşen başvuru kaydı bulunamadı.",
        "delete_id_missing": "⚠️ *Hata:* Lütfen silinecek başvuru ID'sini belirtin. Kullanım: `/delete <ID>`",
        "delete_success": "🗑️ *Başvuru kaydı silindi.* (ID: {id})",
        "delete_not_found": "❌ Belirtilen ID ile eşleşen başvuru kaydı bulunamadı.",
        "settings_title": "⚙️ *CareerAgent Ayarları* ⚙️\n\nYapay zeka arama bölgenizi ve bot dilinizi aşağıdaki butonları kullanarak özelleştirebilirsiniz:\n\n👤 *Kullanıcı Chat ID:* `{chat_id}`\n🌐 *Hedef Arama Bölgesi:* `{region}`\n🗣️ *Sistem Dili:* `{language}`",
        "settings_btn_lang": "Dili Değiştir",
        "settings_btn_region": "Bölgeyi Değiştir",
        "settings_lang_select": "🗣️ *Sistem Dilini Seçin:*",
        "settings_region_select": "🌐 *Hedef Arama Bölgesini Seçin:*",
        "settings_updated": "✅ Ayarlar başarıyla güncellendi!"
    },
    "all": {
        "welcome_new": (
            "🚀 *Welcome to CareerAgent! / CareerAgent'a Hoş Geldiniz!* 🚀\n\n"
            "Your account has been registered successfully. / Hesabınız başarıyla oluşturuldu.\n\n"
            "🔗 `/add <URL>` - Track a custom announcement page. / Takip edilecek sayfa ekler.\n"
            "📋 `/list` - List custom websites. / Takip edilen sayfaları listeler.\n"
            "🗑️ `/remove <ID>` - Remove a website from tracking. / Sayfa takibini sonlandırır.\n"
            "⚙️ `/settings` - Open settings. / Ayarları açar.\n\n"
            "💼 *JOB APPLICATION TRACKER / İŞ BAŞVURU TAKİP PANELİ:* \n"
            "📝 `/apply <Name>` - Register a job application. / Yeni başvuru kaydeder.\n"
            "📊 `/applications` - List applications. / Başvuruları listeler.\n"
            "🚦 `/status <App_ID> <Stage>` - Update status. / Durumu günceller.\n"
            "🗑️ `/delete <App_ID>` - Delete job application. / Başvuruyu siler."
        ),
        "welcome_back": (
            "👋 *Welcome Back! / Tekrar Hoş Geldiniz!*\n\n"
            "CareerAgent is online / aktif. Send commands directly or type `/settings` to customize."
        ),
        "unauthorized": "❌ *Access Denied / Erişim Engellendi.* You do not have permissions to access this bot / Bu botu kullanma izniniz bulunmamaktadır.",
        "start_first": "⚠️ Please activate your account first by sending `/start` / Lütfen önce `/start` komutunu gönderin.",
        "add_url_missing": "⚠️ *Error / Hata:* Please specify a URL / Lütfen bir URL belirtin. Usage: `/add <URL>`",
        "add_url_success": "✅ *Added to Tracking List / Takip Listesine Eklendi:*\n🔗 {url}\n\nAI will scan this website daily for announcements. / AI bu adresi günlük döngüde tarayacak.",
        "add_url_error": "❌ *Error / Hata:* Failed to add URL / Adres eklenirken sorun oluştu: {error}",
        "list_empty": "📭 *Your tracking list is empty / Takip listeniz boş.* Use `/add <URL>` to add one.",
        "list_title": "📋 *Tracked Custom Websites / Takip Edilen Özel Siteler:*\n\n{sites}",
        "remove_id_missing": "⚠️ *Error / Hata:* Please specify target ID / Lütfen silinecek site ID'sini belirtin. Usage: `/remove <ID>`",
        "remove_success": "🗑️ *Removed from tracking / Takip listesinden kaldırıldı.* (ID: {id})",
        "remove_not_found": "❌ Target ID not found / Eşleşen takip edilen site bulunamadı.",
        "apply_name_missing": "⚠️ *Error / Hata:* Please specify name / Lütfen fırsat/kurum adı girin. Usage: `/apply <Name>`",
        "apply_success": "📝 *Application Logged / Başvuru Kaydedildi!* 🚀\n\n📌 *Opportunity:* `{name}`\n🚦 *Status:* `Applied` (Use `/status <ID> <stage>` to update)",
        "apps_empty": "📭 *No job applications logged yet / Kayıtlı başvurunuz bulunmamaktadır.*\nStart tracking using: `/apply <Company>`",
        "apps_title": "💼 *JOB APPLICATION TRACKER / İŞ BAŞVURU TAKİP PANELİ* 💼\n\n{apps}",
        "status_missing": "⚠️ *Error / Hata:* Missing arguments / Eksik argüman. Usage: `/status <ID> <New_Status>`",
        "status_success": "🚦 *Application Status Updated / Başvuru Durumu Güncellendi!* (ID: {id})\n👉 Stage / Aşama: *{status}*",
        "status_not_found": "❌ Target Application ID not found / Eşleşen başvuru kaydı bulunamadı.",
        "delete_id_missing": "⚠️ *Error / Hata:* Please specify Application ID / Lütfen silinecek başvuru ID'sini belirtin. Usage: `/delete <ID>`",
        "delete_success": "🗑️ *Application record deleted / Başvuru kaydı silindi.* (ID: {id})",
        "delete_not_found": "❌ Target Application ID not found / Eşleşen başvuru kaydı bulunamadı.",
        "settings_title": "⚙️ *CareerAgent Settings / CareerAgent Ayarları* ⚙️\n\nCustomize your localized AI search crawls and system language below:\n\n👤 *User ID:* `{chat_id}`\n🌐 *Target Region:* `{region}`\n🗣️ *System Language:* `{language}`",
        "settings_btn_lang": "Change Language / Dili Değiştir",
        "settings_btn_region": "Change Region / Bölgeyi Değiştir",
        "settings_lang_select": "🗣️ *Select System Language / Sistem Dilini Seçin:*",
        "settings_region_select": "🌐 *Select Target Search Region / Hedef Arama Bölgesini Seçin:*",
        "settings_updated": "✅ Settings successfully updated / Ayarlar başarıyla güncellendi!"
    }
}


# Thread-safe SQLite Database Manager with WAL (Write-Ahead Logging) concurrency enabled
class DatabaseManager:
    def __init__(self, db_path="data/careeragent.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.initialize_schema()
        self.migrate_old_json_data()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def initialize_schema(self):
        with db_lock:
            with self.get_connection() as conn:
                # Users table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        chat_id TEXT PRIMARY KEY,
                        language TEXT DEFAULT 'en',
                        region TEXT DEFAULT 'global',
                        email_active INTEGER DEFAULT 0,
                        email_imap_server TEXT,
                        email_port INTEGER DEFAULT 993,
                        email_user TEXT,
                        email_password TEXT,
                        email_auto_unsubscribe INTEGER DEFAULT 0,
                        last_run_date TEXT
                    )
                """)
                # Custom Tracked Sites - Added last_hash to prevent screaming on duplicate scans
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tracked_sites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        url TEXT,
                        last_hash TEXT,
                        UNIQUE(chat_id, url)
                    )
                """)
                # History of Sent Opportunities
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sent_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        title TEXT,
                        url TEXT,
                        sent_date TEXT
                    )
                """)
                # Processed Email Message IDs
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS processed_mails (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        message_id TEXT,
                        UNIQUE(chat_id, message_id)
                    )
                """)
                # Job Application Tracker Table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS applications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        opportunity_name TEXT,
                        organizer TEXT,
                        status TEXT DEFAULT 'Applied',
                        date_logged TEXT
                    )
                """)
                # Opportunities Table for tracking deadlines and start dates
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS opportunities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        title TEXT,
                        url TEXT,
                        deadline_date TEXT,
                        start_date TEXT,
                        notified_deadline INTEGER DEFAULT 0,
                        notified_start INTEGER DEFAULT 0,
                        created_date TEXT,
                        UNIQUE(chat_id, url)
                    )
                """)
                # Conversational Chat History Table for context-aware responses
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT,
                        role TEXT,
                        message TEXT,
                        timestamp TEXT
                    )
                """)
                # Migrate schema automatically to support custom system prompt per user
                try:
                    conn.execute("ALTER TABLE users ADD COLUMN custom_prompt TEXT DEFAULT NULL")
                except sqlite3.OperationalError:
                    pass
                conn.commit()

    def migrate_old_json_data(self):
        """Clean automatic migration of old JSON databases to SQLite on first startup."""
        primary_chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not primary_chat_id:
            return

        with db_lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM users WHERE chat_id = ?", (primary_chat_id,))
                exists = cursor.fetchone()
                
                if not exists:
                    logging.info(f"Creating default primary user account in SQLite for Chat ID: {primary_chat_id}")
                    email_active = 1 if os.getenv("EMAIL_ACTIVE", "False").lower() in ("true", "1", "yes") else 0
                    email_auto_unsubscribe = 1 if os.getenv("EMAIL_AUTO_UNSUBSCRIBE", "False").lower() in ("true", "1", "yes") else 0
                    
                    conn.execute("""
                        INSERT INTO users (chat_id, language, region, email_active, email_imap_server, email_port, email_user, email_password, email_auto_unsubscribe)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        primary_chat_id,
                        os.getenv("LANGUAGE", "en").lower().strip(),
                        os.getenv("REGION", "global").lower().strip(),
                        email_active,
                        os.getenv("EMAIL_1_IMAP_SERVER"),
                        int(os.getenv("EMAIL_1_PORT", "993")),
                        os.getenv("EMAIL_1_USER"),
                        os.getenv("EMAIL_1_PASSWORD"),
                        email_auto_unsubscribe
                    ))
                    conn.commit()

                # Migrate takip_siteleri.json
                sites_path = "data/takip_siteleri.json"
                if os.path.exists(sites_path):
                    try:
                        with open(sites_path, "r", encoding="utf-8") as f:
                            sites = json.load(f)
                            for site in sites:
                                conn.execute("INSERT OR IGNORE INTO tracked_sites (chat_id, url) VALUES (?, ?)", (primary_chat_id, site))
                        os.rename(sites_path, sites_path + ".imported")
                        logging.info("Migrated custom tracked sites from JSON to SQLite successfully.")
                    except Exception as e:
                        logging.error(f"Migration error for tracked sites JSON: {e}")

                # Migrate okunan_mailler.json
                mails_path = "data/okunan_mailler.json"
                if os.path.exists(mails_path):
                    try:
                        with open(mails_path, "r", encoding="utf-8") as f:
                            mails = json.load(f)
                            for mail_id in mails:
                                conn.execute("INSERT OR IGNORE INTO processed_mails (chat_id, message_id) VALUES (?, ?)", (primary_chat_id, mail_id))
                        os.rename(mails_path, mails_path + ".imported")
                        logging.info("Migrated processed email signatures from JSON to SQLite successfully.")
                    except Exception as e:
                        logging.error(f"Migration error for processed emails JSON: {e}")

                # Migrate gonderilen_etkinlikler.json
                history_path = "data/gonderilen_etkinlikler.json"
                if os.path.exists(history_path):
                    try:
                        with open(history_path, "r", encoding="utf-8") as f:
                            history = json.load(f)
                            for item in history:
                                conn.execute("""
                                    INSERT INTO sent_history (chat_id, title, url, sent_date)
                                    VALUES (?, ?, ?, ?)
                                """, (primary_chat_id, item.get("title"), item.get("url"), item.get("sent_date", datetime.now().strftime("%Y-%m-%d"))))
                        os.rename(history_path, history_path + ".imported")
                        logging.info("Migrated opportunity reporting history from JSON to SQLite successfully.")
                    except Exception as e:
                        logging.error(f"Migration error for sent history JSON: {e}")

                # Migrate etkinlik_kontrol.json
                state_path = "data/etkinlik_kontrol.json"
                if os.path.exists(state_path):
                    try:
                        with open(state_path, "r", encoding="utf-8") as f:
                            state = json.load(f)
                            today_str = datetime.now().strftime("%Y-%m")
                            today_day = datetime.now().strftime("%d")
                            if today_str in state and state[today_str].get(today_day) is True:
                                conn.execute("UPDATE users SET last_run_date = ? WHERE chat_id = ?", (datetime.now().strftime("%Y-%m-%d"), primary_chat_id))
                        os.rename(state_path, state_path + ".imported")
                        logging.info("Migrated run state calendar from JSON to SQLite successfully.")
                    except Exception as e:
                        logging.error(f"Migration error for state calendar JSON: {e}")
                conn.commit()


# Advanced LLM Client with Retry Resilience
class LLMClient:
    @staticmethod
    def call_llm(provider: str, model: str, api_key: str, prompt: str, system_instruction: str, response_format_json: bool = False) -> str:
        """Invokes LLM models dynamically using LiteLLM with unified format calls and retry resilience."""
        provider = provider.lower().strip()
        model = model.strip()
        
        # Build robust model string, ensuring openrouter/ prefix for OpenRouter provider models
        if provider == "openrouter" and not model.startswith("openrouter/"):
            model_str = f"openrouter/{model}"
        else:
            model_str = model if "/" in model else f"{provider}/{model}"
            
        # Guarantee OPENROUTER_API_KEY environment variable is configured for LiteLLM routing
        if "openrouter" in model_str:
            os.environ["OPENROUTER_API_KEY"] = api_key
            
        max_retries = 3
        base_backoff = 2
        
        for attempt in range(max_retries):
            try:
                messages = [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ]
                kwargs = {
                    "model": model_str,
                    "messages": messages,
                    "api_key": api_key,
                    "temperature": 0.1,
                    "timeout": 30
                }
                
                # Some providers/models (like OpenRouter free models) do not support response_format parameter.
                # We exclude it for OpenRouter models to prevent remote API Bad Request errors.
                if response_format_json and "openrouter" not in model_str and provider != "openrouter":
                    kwargs["response_format"] = {"type": "json_object"}
                    
                logging.info(f"Dispatching unified LiteLLM completion request (Attempt {attempt+1}/{max_retries}) for model: {model_str}")
                response = completion(**kwargs)
                return response.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"LiteLLM call attempt {attempt+1} failed for model {model_str}: {e}")
                if attempt == max_retries - 1:
                    raise
                sleep_time = base_backoff ** (attempt + 1)
                logging.info(f"Waiting {sleep_time} seconds before retrying LLM call...")
                time.sleep(sleep_time)

    @staticmethod
    def clean_json_response(res_text: str) -> str:
        """Strips markdown code block fences securely from JSON payloads."""
        res_text = res_text.strip()
        res_text = re.sub(r'^```json\s*', '', res_text)
        res_text = re.sub(r'\s*```$', '', res_text)
        return res_text.strip()


# Real-time search and fallback scraping routines
class FirecrawlClient:
    @staticmethod
    def firecrawl_search(query: str, api_key: str, limit: int = 15) -> list:
        if not api_key:
            logging.warning("Firecrawl API Key missing. Skipping web search step.")
            return []
            
        url = "https://api.firecrawl.dev/v2/search"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "query": query,
            "limit": limit,
            "scrapeOptions": {
                "formats": ["markdown"],
                "onlyMainContent": True,
                "removeBase64Images": True
            }
        }
        
        try:
            logging.info(f"Invoking Firecrawl v2 search for query: '{query}'")
            response = requests.post(url, json=payload, headers=headers, timeout=40)
            response.raise_for_status()
            
            data = response.json()
            if data.get("success") and "data" in data and "web" in data["data"]:
                return data["data"]["web"]
            return []
        except Exception as e:
            logging.error(f"Firecrawl search exception occurred: {e}")
            return []

    @staticmethod
    def firecrawl_agent(prompt: str, api_key: str) -> list:
        if not api_key:
            return []
            
        post_url = "https://api.firecrawl.dev/v2/agent"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {"prompt": prompt}
        
        try:
            logging.info("Initiating Firecrawl v2 asynchronous agent run...")
            response = requests.post(post_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            res_data = response.json()
            job_id = res_data.get("jobId") or res_data.get("id")
            if not job_id:
                return []
                
            poll_url = f"https://api.firecrawl.dev/v2/agent/{job_id}"
            for attempt in range(30):
                time.sleep(10)
                logging.info(f"Polling agent progress (Attempt {attempt + 1}/30)...")
                poll_resp = requests.get(poll_url, headers=headers, timeout=20)
                poll_resp.raise_for_status()
                
                poll_data = poll_resp.json()
                status = poll_data.get("status")
                
                if status == "completed":
                    return [{
                        "title": "Autonomous Agent Crawl Result",
                        "markdown": json.dumps(poll_data.get("data", {}), indent=2, ensure_ascii=False),
                        "url": "https://api.firecrawl.dev"
                    }]
                elif status == "failed":
                    break
            return []
        except Exception as e:
            logging.error(f"Firecrawl agent runtime exception: {e}")
            return []

    @staticmethod
    def scrape_tracked_site(url: str) -> dict:
        try:
            logging.info(f"Scraping custom tracked website: {url}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=25)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script.decompose()
                
            text = soup.get_text(separator=" ")
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            clean_text = "\n".join(chunk for chunk in chunks if chunk)
            
            title = soup.title.string.strip() if soup.title else "Custom Tracked Site"
            return {
                "title": f"Custom Tracked Site: {title}",
                "url": url,
                "markdown": clean_text[:4000]
            }
        except Exception as e:
            logging.error(f"Failed to scrape tracked custom site ({url}): {e}")
            return {
                "title": "Custom Tracked Site (Scraping Failed)",
                "url": url,
                "markdown": f"Automatic background scraping failed. Error details: {e}"
            }


# Core Email Scanner Module (IMAP scans & Auto-Unsubscribe)
class EmailScanner:
    @staticmethod
    def _decode_header_value(value: str) -> str:
        if not value:
            return ""
        try:
            decoded_parts = decode_header(value)
            decoded_str = ""
            for text, encoding in decoded_parts:
                if isinstance(text, bytes):
                    decoded_str += text.decode(encoding or "utf-8", errors="ignore")
                else:
                    decoded_str += str(text)
            return decoded_str
        except Exception:
            return value

    @staticmethod
    def get_email_body(msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body += part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
            except Exception:
                pass
        return body

    @staticmethod
    def unsubscribe_from_list(msg, username: str) -> bool:
        list_unsubscribe = msg.get("List-Unsubscribe")
        if not list_unsubscribe:
            return False
            
        urls = re.findall(r'<(https?://[^>]+)>', list_unsubscribe)
        if not urls:
            return False
            
        unsubscribe_url = urls[0].strip()
        logging.info(f"[{username}] Triggering auto-unsubscribe request to: {unsubscribe_url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "List-Unsubscribe": "One-Click"
        }
        
        try:
            response = requests.post(unsubscribe_url, data={"List-Unsubscribe": "One-Click"}, headers=headers, timeout=20)
            if response.status_code in (200, 201, 202, 204):
                logging.info(f"[{username}] Auto-unsubscribe triggered via POST!")
                return True
        except Exception:
            pass
            
        try:
            response = requests.get(unsubscribe_url, headers=headers, timeout=20)
            if response.status_code in (200, 201, 202, 204):
                logging.info(f"[{username}] Auto-unsubscribe triggered via GET!")
                return True
        except Exception:
            pass
        return False

    @classmethod
    def scan_inbox(cls, user_config: dict, db: DatabaseManager, provider: str, model: str, api_key: str, bot_token: str):
        chat_id = user_config["chat_id"]
        imap_server = user_config["email_imap_server"]
        port = int(user_config["email_port"] or 993)
        username = user_config["email_user"]
        password = user_config["email_password"]
        language = user_config["language"]
        auto_unsubscribe = bool(user_config["email_auto_unsubscribe"])
        
        if not imap_server or not username or not password:
            return
            
        logging.info(f"Scanning email inbox for {username} ({imap_server}) under User: {chat_id}")
        mail = None
        
        try:
            is_ssl = (port == 993 or port == 1143)
            if is_ssl:
                context = ssl.create_default_context()
                if imap_server in ("127.0.0.1", "localhost") or port == 1143:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                mail = imaplib.IMAP4_SSL(imap_server, port, ssl_context=context, timeout=30)
            else:
                mail = imaplib.IMAP4(imap_server, port, timeout=30)
                
            mail.login(username, password)
            mail.select("INBOX")
            
            date_str = (datetime.now() - timedelta(days=2)).strftime("%d-%b-%Y")
            status, messages = mail.search(None, f'(SINCE "{date_str}")')
            if status != "OK" or not messages[0]:
                return
                
            mail_ids = messages[0].split()
            
            # Query existing processed messages inside SQLite (Thread-Safe Reads)
            with db_lock:
                with db.get_connection() as conn:
                    rows = conn.execute("SELECT message_id FROM processed_mails WHERE chat_id = ?", (chat_id,)).fetchall()
                    processed_emails = {r["message_id"] for r in rows}
            
            for mail_id in reversed(mail_ids):
                if not keep_running:
                    break
                    
                status, header_data = mail.fetch(mail_id, "(BODY[HEADER.FIELDS (MESSAGE-ID)])")
                if status != "OK" or not header_data[0]:
                    continue
                    
                header_text = header_data[0][1].decode("utf-8", errors="ignore")
                msg_id_match = re.search(r'(?i)Message-ID:\s*(<.*?>)', header_text)
                msg_id = msg_id_match.group(1).strip() if msg_id_match else f"{username}_{mail_id.decode()}"
                
                if msg_id in processed_emails:
                    continue
                    
                status, msg_data = mail.fetch(mail_id, "(RFC822)")
                if status != "OK" or not msg_data[0]:
                    continue
                    
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                sender = cls._decode_header_value(msg.get("From", ""))
                subject = cls._decode_header_value(msg.get("Subject", ""))
                body = cls.get_email_body(msg)
                
                logging.info(f"Analyzing incoming email: '{subject}' | From: {sender}")
                
                analysis = cls.analyze_email_importance(sender, subject, body, provider, model, api_key, language)
                
                if analysis.get("important"):
                    reason = analysis.get("reason", "Important category match.")
                    summary = analysis.get("summary", "Summary compilation complete.")
                    urgency = analysis.get("urgency", "Medium")
                    urgency_emoji = "🔴" if urgency == "High" else ("🟡" if urgency == "Medium" else "🟢")
                    
                    # [AUTOMATED JOB TRACKER SYNC] Check if email is an application response and sync to database
                    tracker_sync_msg = ""
                    if analysis.get("is_job_update") and analysis.get("company_name") and analysis.get("extracted_status"):
                        company = analysis.get("company_name").strip()
                        extracted_status = analysis.get("extracted_status").strip()
                        
                        # Map internal standard statuses to visual emojified ones
                        db_status = "Applied"
                        if extracted_status.lower() in ("interview", "mülakat"):
                            db_status = "📞 Interview"
                        elif extracted_status.lower() in ("accepted", "kabul"):
                            db_status = "🎉 Accepted"
                        elif extracted_status.lower() in ("rejected", "red"):
                            db_status = "❌ Rejected"
                            
                        # Lookup user's recorded applications fuzzy-matching the company name
                        with db_lock:
                            with db.get_connection() as conn:
                                match_app = conn.execute(
                                    "SELECT id, opportunity_name, status FROM applications WHERE chat_id = ? AND (opportunity_name LIKE ? OR opportunity_name LIKE ?)",
                                    (chat_id, f"%{company}%", f"{company}%")
                                ).fetchone()
                                
                                if match_app:
                                    # Update application status in the database automatically!
                                    conn.execute(
                                        "UPDATE applications SET status = ? WHERE id = ?",
                                        (db_status, match_app["id"])
                                    )
                                    conn.commit()
                                    
                                    if language == "tr":
                                        tracker_sync_msg = (
                                            f"\n\n🚦 *BAŞVURU TAKİBİ SENKRONİZE EDİLDİ!* 💼\n"
                                            f"📌 *Fırsat:* `{match_app['opportunity_name']}`\n"
                                            f"👉 *Eski Durum:* `{match_app['status']}`\n"
                                            f"👉 *Yeni Durum:* `{db_status}` *(Otomatik Güncellendi)*"
                                        )
                                    else:
                                        tracker_sync_msg = (
                                            f"\n\n🚦 *APPLICATION TRACKER SYNCED!* 💼\n"
                                            f"📌 *Opportunity:* `{match_app['opportunity_name']}`\n"
                                            f"👉 *Old Status:* `{match_app['status']}`\n"
                                            f"👉 *New Status:* `{db_status}` *(Auto-Updated)*"
                                        )
                    
                    if language == "tr":
                        email_alert_msg = (
                            f"📬 *YENİ ÖNEMLİ E-POSTA BİLDİRİMİ* {urgency_emoji}\n\n"
                            f"📧 *Hesap:* `{username}`\n"
                            f"👤 *Gönderen:* `{sender}`\n"
                            f"📝 *Konu:* *{subject}*\n"
                            f"🎯 *Neden:* _{reason}_\n"
                            f"🔍 *Özet:* {summary}\n"
                            f"🚦 *Aciliyet Derecesi:* *{urgency}*"
                            f"{tracker_sync_msg}"
                        )
                    else:
                        email_alert_msg = (
                            f"📬 *NEW IMPORTANT EMAIL ALERT* {urgency_emoji}\n\n"
                            f"📧 *Account:* `{username}`\n"
                            f"👤 *From:* `{sender}`\n"
                            f"📝 *Subject:* *{subject}*\n"
                            f"🎯 *Reason:* _{reason}_\n"
                            f"🔍 *Summary:* {summary}\n"
                            f"🚦 *Urgency:* *{urgency}*"
                            f"{tracker_sync_msg}"
                        )
                    TelegramBot.send_message(email_alert_msg, bot_token, chat_id)
                else:
                    if auto_unsubscribe and analysis.get("unsubscribe"):
                        cls.unsubscribe_from_list(msg, username)
                
                # Write processed email record to database (Thread-Safe Write)
                with db_lock:
                    with db.get_connection() as conn:
                        conn.execute("INSERT OR IGNORE INTO processed_mails (chat_id, message_id) VALUES (?, ?)", (chat_id, msg_id))
                        conn.commit()
                processed_emails.add(msg_id)
                
        except Exception as e:
            logging.error(f"Error scanning IMAP account ({username}): {e}", exc_info=True)
        finally:
            if mail:
                try:
                    mail.close()
                except Exception:
                    pass
                try:
                    mail.logout()
                except Exception:
                    pass

    @staticmethod
    def analyze_email_importance(sender: str, subject: str, body: str, provider: str, model: str, api_key: str, language: str) -> dict:
        language = language.lower().strip()
        if language == "tr":
            system_instruction = (
                "Sen son derece akıllı ve otonom bir sekreter ajansın. Görevin, bir e-postayı inceleyerek "
                "kullanıcı için 'ÖNEMLİ' olup olmadığını tespit etmek, önemli değilse reklam/bülten listesi olup olmadığını belirlemektir.\n\n"
                "ÖNEMLİ E-POSTA KRİTERLERİ (Bunlar dışındakileri önemsiz say):\n"
                "1. YARIŞMA/PROGRAM: Hackathon, bootcamp, CTF, sertifika veya kariyer programı bildirimleri.\n"
                "2. PORTFOLYO: Portfolyo sitesinden atılan kişisel mesajlar.\n"
                "3. İŞ/KARİYER: İş teklifleri, mülakat davetleri, freelance proje talepleri.\n"
                "4. ACİL KİŞİSEL: Otomatik olmayan acil bildirimler.\n\n"
                "Yanıtında sadece saf JSON döndür, markdown kod blokları kullanma."
            )
            prompt = (
                f"E-POSTA DETAYLARI:\n"
                f"Gönderen: {sender}\n"
                f"Konu: {subject}\n"
                f"İçerik:\n{body[:2500]}\n\n"
                "GÖREVİN:\n"
                "E-postayı analiz et. ÖNEMLİ ise şu formatta JSON dön (is_job_update, company_name ve extracted_status alanlarını mutlaka analiz et):\n"
                "{\n"
                "  \"important\": true,\n"
                "  \"unsubscribe\": false,\n"
                "  \"reason\": \"Kısa gerekçe\",\n"
                "  \"summary\": \"Kısa özet\",\n"
                "  \"urgency\": \"Low\" veya \"Medium\" veya \"High\",\n"
                "  \"is_job_update\": true veya false (bu mail bir iş başvurusuna, mülakat davetine veya kabul/red bildirimine mi ait?),\n"
                "  \"company_name\": \"Ayıklanan şirket/düzenleyici adı veya null\",\n"
                "  \"extracted_status\": \"Interview\" veya \"Accepted\" veya \"Rejected\" veya null\n"
                "}\n\n"
                "ÖNEMSİZ bülten maili ise:\n"
                "{\n"
                "  \"important\": false,\n"
                "  \"unsubscribe\": true,\n"
                "  \"is_job_update\": false,\n"
                "  \"company_name\": null,\n"
                "  \"extracted_status\": null\n"
                "}\n\n"
                "Sıradan önemsiz mail ise:\n"
                "{\n"
                "  \"important\": false,\n"
                "  \"unsubscribe\": false,\n"
                "  \"is_job_update\": false,\n"
                "  \"company_name\": null,\n"
                "  \"extracted_status\": null\n"
                "}"
            )
        else:
            system_instruction = (
                "You are an extremely intelligent and autonomous secretary assistant. Your task is to inspect an email and determine if it is 'IMPORTANT' for the user.\n\n"
                "IMPORTANT EMAIL CRITERIA:\n"
                "1. COMPETITION/PROGRAM: Hackathons, bootcamps, CTFs, certificate programs.\n"
                "2. PORTFOLIO: Messages sent through the contact form.\n"
                "3. WORK/CAREER: Job offers, interview invitations, freelance work.\n"
                "4. PERSONAL URGENCY: Urgent direct updates.\n\n"
                "Return raw JSON only. Do not wrap in markdown tags."
            )
            prompt = (
                f"EMAIL DETAILS:\n"
                f"From: {sender}\n"
                f"Subject: {subject}\n"
                f"Content:\n{body[:2500]}\n\n"
                "YOUR TASK:\n"
                "Analyze the email. If IMPORTANT, return the following JSON structure. You must check if the email is a response/update to a job application or program subscription, and extract the company/opportunity name and the new status:\n"
                "{\n"
                "  \"important\": true,\n"
                "  \"unsubscribe\": false,\n"
                "  \"reason\": \"Short reason in English\",\n"
                "  \"summary\": \"Short summary in English\",\n"
                "  \"urgency\": \"Low\" or \"Medium\" or \"High\",\n"
                "  \"is_job_update\": true or false,\n"
                "  \"company_name\": \"Extracted company or organizer name (e.g. Google, BTK, AWS) or null\",\n"
                "  \"extracted_status\": \"Interview\" or \"Accepted\" or \"Rejected\" or null\n"
                "}\n\n"
                "If MARKETING/NEWSLETTER:\n"
                "{\n"
                "  \"important\": false,\n"
                "  \"unsubscribe\": true,\n"
                "  \"is_job_update\": false,\n"
                "  \"company_name\": null,\n"
                "  \"extracted_status\": null\n"
                "}\n\n"
                "Otherwise:\n"
                "{\n"
                "  \"important\": false,\n"
                "  \"unsubscribe\": false,\n"
                "  \"is_job_update\": false,\n"
                "  \"company_name\": null,\n"
                "  \"extracted_status\": null\n"
                "}"
            )

        try:
            raw_res = LLMClient.call_llm(provider, model, api_key, prompt, system_instruction, response_format_json=True)
            cleaned_res = LLMClient.clean_json_response(raw_res)
            return json.loads(cleaned_res)
        except Exception as e:
            logging.error(f"Failed email importance analysis: {e}")
            return {"important": False, "unsubscribe": False}


# Advanced Telegram Bot Client with Parallel Polling Thread & Interactive Dropdowns (Inline Keyboards)
class TelegramBot:
    @staticmethod
    def send_message(text: str, bot_token: str, chat_id: str, reply_markup: dict = None) -> bool:
        if not bot_token or not chat_id:
            return False
            
        max_length = 4000
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        try:
            response = requests.post(url, json=payload, timeout=20)
            if response.status_code != 200:
                payload.pop("parse_mode", None)
                fallback_resp = requests.post(url, json=payload, timeout=20)
                if fallback_resp.status_code != 200:
                    return False
            return True
        except Exception as e:
            logging.error(f"Telegram communication error: {e}")
            return False

    @classmethod
    def record_chat_history(cls, chat_id: str, role: str, message: str, db: DatabaseManager):
        try:
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with db_lock:
                with db.get_connection() as conn:
                    conn.execute(
                        "INSERT INTO chat_history (chat_id, role, message, timestamp) VALUES (?, ?, ?, ?)",
                        (chat_id, role, message, timestamp_str)
                    )
                    # Keep history capped at 50 messages per user to preserve space
                    conn.execute("""
                        DELETE FROM chat_history 
                        WHERE chat_id = ? AND id NOT IN (
                            SELECT id FROM chat_history 
                            WHERE chat_id = ? 
                            ORDER BY id DESC LIMIT 50
                        )
                    """, (chat_id, chat_id))
                    conn.commit()
        except Exception as e:
            logging.error(f"Failed to record chat history for role {role}: {e}")

    @classmethod
    def check_updates(cls, bot_token: str, db: DatabaseManager, authorized_ids: list):
        if not bot_token:
            return
            
        offset = 0
        with db_lock:
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE IF NOT EXISTS sys_config (key TEXT PRIMARY KEY, val TEXT)")
                row = cursor.execute("SELECT val FROM sys_config WHERE key = 'last_update_id'").fetchone()
                if row:
                    offset = int(row["val"]) + 1
                    
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        payload = {"timeout": 2}
        if offset > 1:
            payload["offset"] = offset
            
        try:
            response = requests.post(url, json=payload, timeout=5)
            if response.status_code != 200:
                return
                
            data = response.json()
            if not data.get("ok") or not data.get("result"):
                return
                
            updates = data["result"]
            max_update_id = offset - 1
            
            for update in updates:
                update_id = update.get("update_id", 0)
                if update_id > max_update_id:
                    max_update_id = update_id
                    
                try:
                    # Handle Inline Button Clicks (Callback Queries)
                    if "callback_query" in update:
                        cls.process_callback_query(update["callback_query"], bot_token, db, authorized_ids)
                        continue
                        
                    message = update.get("message")
                    if not message:
                        continue
                        
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    text = message.get("text", "").strip()
                    if not chat_id or not text:
                        continue
                        
                    # [ACCESS CONTROL RESTORED] Ensure only authorized Chat IDs can run commands
                    if authorized_ids and chat_id not in authorized_ids:
                        cls.send_message("❌ *Access Denied.* You do not have permission to access this CareerAgent.", bot_token, chat_id)
                        continue
                        
                    cls.process_command(chat_id, text, bot_token, db)
                except Exception as ex:
                    logging.error(f"Error processing single Telegram update {update_id}: {ex}", exc_info=True)
                
            if max_update_id >= offset:
                with db_lock:
                    with db.get_connection() as conn:
                        conn.execute("INSERT OR REPLACE INTO sys_config (key, val) VALUES ('last_update_id', ?)", (str(max_update_id),))
                        conn.commit()
        except Exception as e:
            logging.error(f"Error checking Telegram updates: {e}")

    @classmethod
    def process_callback_query(cls, callback: dict, bot_token: str, db: DatabaseManager, authorized_ids: list):
        query_id = callback["id"]
        chat_id = str(callback["from"]["id"])
        data = callback["data"]
        message_id = callback["message"]["message_id"]
        
        # [ACCESS CONTROL] Filter callback queries
        if authorized_ids and chat_id not in authorized_ids:
            return
            
        logging.info(f"Received settings callback: {data} from User: {chat_id}")
        
        with db_lock:
            with db.get_connection() as conn:
                user = conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
                
        if not user:
            return
            
        lang = user["language"]
        edit_url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        
        # WIZARD STEP 1 -> STEP 2: Language selected, now ask for Region
        if data in ("lang_en", "lang_tr", "lang_all"):
            new_lang = "en"
            if data == "lang_tr":
                new_lang = "tr"
            elif data == "lang_all":
                new_lang = "all"
                
            with db_lock:
                with db.get_connection() as conn:
                    conn.execute("UPDATE users SET language = ? WHERE chat_id = ?", (new_lang, chat_id))
                    conn.commit()
            lang = new_lang
            
            # Render Region select prompt dynamically based on new language choice
            text = LOCALIZATION[lang]["settings_region_select"]
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "🌍 All World / Tüm Dünya", "callback_data": "reg_all"},
                        {"text": "🇹🇷 Turkey / Türkiye", "callback_data": "reg_tr"}
                    ],
                    [
                        {"text": "🇺🇸 USA / ABD", "callback_data": "reg_us"},
                        {"text": "🇪🇺 Europe / Avrupa", "callback_data": "reg_eu"}
                    ]
                ]
            }
            
            requests.post(f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery", json={"callback_query_id": query_id, "text": LOCALIZATION[lang]["settings_updated"]})
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup
            }
            requests.post(edit_url, json=payload, timeout=20)
            
        # WIZARD STEP 2 -> CONFIRMATION: Region selected, show final Profile Card
        elif data.startswith("reg_"):
            new_region = data[4:]
            with db_lock:
                with db.get_connection() as conn:
                    conn.execute("UPDATE users SET region = ? WHERE chat_id = ?", (new_region, chat_id))
                    conn.commit()
                    user = conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
            
            text = LOCALIZATION[lang]["settings_title"].format(chat_id=chat_id, region=user["region"].upper(), language=user["language"].upper())
            # Single modify button to allow restarting the wizard
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "⚙️ Modify Settings / Ayarları Değiştir", "callback_data": "start_wizard"}]
                ]
            }
            
            requests.post(f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery", json={"callback_query_id": query_id, "text": LOCALIZATION[lang]["settings_updated"]})
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup
            }
            requests.post(edit_url, json=payload, timeout=20)
            
        # RESTART WIZARD: Modify settings clicked, show Language select again
        elif data == "start_wizard":
            text = "🗣️ *Select System Language / Sistem Dili Seçin:*"
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "🇬🇧 English", "callback_data": "lang_en"},
                        {"text": "🇹🇷 Türkçe", "callback_data": "lang_tr"},
                        {"text": "🌐 All / Her İkisi", "callback_data": "lang_all"}
                    ]
                ]
            }
            requests.post(f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery", json={"callback_query_id": query_id})
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": reply_markup
            }
            requests.post(edit_url, json=payload, timeout=20)

    @classmethod
    def handle_natural_language_code_mod(cls, chat_id: str, prompt_text: str, bot_token: str, db: DatabaseManager):
        global LLM_PROVIDER, LLM_MODEL, LLM_API_KEY

        # 1. Record the user's prompt in the conversational history
        cls.record_chat_history(chat_id, "user", prompt_text, db)

        # 2. Retrieve past conversation history from the database for context-aware responses
        past_context = ""
        try:
            with db_lock:
                with db.get_connection() as conn:
                    rows = conn.execute(
                        "SELECT role, message FROM chat_history WHERE chat_id = ? ORDER BY id DESC LIMIT 10", 
                        (chat_id,)
                    ).fetchall()
            # Reverse DESC order to show chronological order
            rows = list(reversed(rows))
            if rows:
                past_context = "\n".join([f"{r['role'].upper()}: {r['message']}" for r in rows])
        except Exception as e:
            logging.warning(f"Failed to retrieve chat history context: {e}")

        # Check if the user prompt is a simple greeting, conversational question, or general query.
        # We run a single fast LLM call without tool definition to reply directly, or output "__AGENT_REQUIRED__" if actual actions are needed.
        classification_instruction = (
            "You are a highly advanced autonomous AI systems administrator and software engineer running inside a Docker container.\n"
            "You possess full agentic access to the container with 5 powerful tools:\n"
            "1. execute_bash (running shell commands inside the container - including searching files using grep or python line counts)\n"
            "2. read_file (reading text files. By default, it reads the first 20,000 characters. If the file is large, you can specify start_line and end_line for range-based section-by-section reading.)\n"
            "3. write_file (creating/writing text files)\n"
            "4. query_database (querying the SQLite data/careeragent.db)\n"
            "5. modify_code (updating your own app.py source code via search-and-replace)\n\n"
            "Your task is to determine whether the user's message requires running any actual system operations (such as inspecting files, running commands, querying the database, or writing/executing scripts).\n\n"
            "CRITICAL PROTOCOLS:\n"
            "1. If the request requires any tool execution (e.g. running a script, searching files, querying databases, checking system state), "
            "you MUST output EXACTLY the word: __AGENT_REQUIRED__\n"
            "2. If the user asks about your capabilities, tools, or if you can execute code, you can answer directly and PROUDLY tell them that you HAVE these 5 tools (execute_bash, read_file, write_file, query_database, modify_code) and can run them inside this Docker container to perform active operations! Do NOT say you cannot execute code.\n"
            "3. If the user's request is a simple greeting, follow-up conversational question, or general query that does not require tool executions, "
            "respond to it directly in a polite, friendly, helpful, and natural way in the user's language, referencing the context if necessary.\n\n"
            "Here is the recent conversation history for context:\n"
            f"{past_context}\n"
        )
        try:
            logging.info(f"Classifying user natural language prompt: '{prompt_text}'")
            classification_resp = LLMClient.call_llm(LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, prompt_text, classification_instruction)
            classification_resp_cleaned = classification_resp.strip()
            
            if "__AGENT_REQUIRED__" not in classification_resp_cleaned:
                cls.send_message(classification_resp_cleaned, bot_token, chat_id)
                # Record response in history!
                cls.record_chat_history(chat_id, "assistant", classification_resp_cleaned, db)
                return
        except Exception as e:
            logging.warning(f"Pre-classification LLM check failed: {e}. Falling back to full ReAct agent.")

        cls.send_message("🤖 *Agentic CareerAgent is initializing... / Yapay zeka ajanı başlatılıyor...*", bot_token, chat_id)
        
        system_instruction = (
            "You are a highly advanced autonomous AI systems administrator and software engineer with full agentic access to the container.\n"
            "You can execute shell commands, read and write files, query the SQLite database, and modify your own source code (app.py) using search-and-replace.\n\n"
            "SAFETY & SELF-PRESERVATION PROTOCOL:\n"
            "1. Do NOT inject blocking infinite loops (like `while True` or `time.sleep`) directly into the global module scope of `app.py` or before system initialization, as this will lock the main thread, prevent system startup, and kill your process forever. Any repetitive tasks must be run in background threads or safe intervals.\n"
            "2. If you need to modify the code, you MUST use the 'read_file' tool first to read 'app.py' and inspect the exact lines of code you want to replace. Do NOT ask the user for line numbers or file structure; you are fully autonomous! If the file is large, read it section-by-section (e.g., 300 lines at a time) using 'start_line' and 'end_line' parameters to locate the exact target code block on your own, then proceed with the modification.\n\n"
            "PROACTIVE SEARCH PROTOCOL:\n"
            "If you need to locate, display, or modify a specific block of code, text, variable, or function in a large file (such as 'system_instruction' or 'classification_instruction' in `app.py`) and you do not know where it is, you should use the 'execute_bash' tool to run a quick search command (e.g. `grep -n \"system_instruction\" app.py` or `python3 -c \"for i, line in enumerate(open('app.py')): gd = 'system_instruction' in line; print(f'{i+1}: {line.strip()}') if gd else None\"`) to find the exact line numbers first. Then, call 'read_file' with those line numbers to fetch the exact code. Do NOT just read the start of the file or guess!\n\n"
            "ENVIRONMENT LIMITATIONS:\n"
            "You are running inside a headless Docker Linux container (Debian-based) with NO GUI, NO X server, and NO active desktop/GUI windows.\n"
            "Do NOT attempt to run commands like xdotool, wmctrl, x11, or other GUI/desktop window tools because they will fail or timeout.\n"
            "If the user asks about windows or GUI features, explain that you are running in a headless server container environment without a GUI.\n\n"
            "PROACTIVE ACTION PROTOCOL:\n"
            "If the user asks you to write and run a script (e.g. Python, Bash, SQL, etc.), you MUST ACTUALLY execute it!\n"
            "First write the script to a file using the 'write_file' tool, then execute it using the 'execute_bash' or appropriate tool.\n"
            "Do NOT just output the code in a chat response and claim you will run it. You are an agent; you must take the actual administrative action and report the execution output to the user!\n\n"
            "AVAILABLE TOOLS:\n"
            "1. execute_bash: Run a shell command in the container. Returns stdout, stderr. Args: {\"tool\": \"execute_bash\", \"command\": \"cmd\"}\n"
            "2. read_file: Read a text file. By default, it reads the first 20,000 characters to optimize token usage. If the file is large, it returns a truncation warning with the total size and line count. To read specific sections, you must specify \"start_line\" (int) and \"end_line\" (int) (e.g., read lines 1100-1300 to locate system prompts). Args: {\"tool\": \"read_file\", \"filepath\": \"path\", \"start_line\": 1, \"end_line\": 100}\n"
            "3. write_file: Write/overwrite a text file. Args: {\"tool\": \"write_file\", \"filepath\": \"path\", \"content\": \"data\"}\n"
            "4. query_database: Run a SQL query against the database (data/careeragent.db). Args: {\"tool\": \"query_database\", \"sql\": \"query\"}\n"
            "5. modify_code: Perform search-and-replace on app.py. Args: {\"tool\": \"modify_code\", \"find\": \"old\", \"replace\": \"new\"}\n"
            "6. final_answer: Provide the final conversational response to the user. Args: {\"tool\": \"final_answer\", \"message\": \"text\"}\n\n"
            "PROTOCOL:\n"
            "You must invoke exactly one tool at a time by returning a single JSON block. Do not output markdown code fences (like ```json), just raw JSON.\n"
            "Analyze the user request, call tools in a loop as needed, and deliver the final answer when done.\n\n"
            "CRITICAL: If the user request is conversational or does not require actual system operations, "
            "IMMEDIATELY invoke the final_answer tool with your response message."
        )
        
        history = []
        should_restart = False
        max_iterations = 6
        
        for iteration in range(max_iterations):
            llm_prompt = ""
            if past_context:
                llm_prompt += f"RECENT CONVERSATION HISTORY:\n{past_context}\n\n"
            llm_prompt += f"USER REQUEST:\n{prompt_text}\n\n"
            if history:
                llm_prompt += "PREVIOUS TOOL CALL EXECUTION HISTORY:\n"
                for idx, h in enumerate(history):
                    tool_res = h['result'] or ""
                    # Compact older tool results in the history loop if they are very large (> 4000 chars)
                    # The most recent result is kept 100% in full so the model has fresh context.
                    is_most_recent = (idx == len(history) - 1)
                    if not is_most_recent and len(tool_res) > 4000:
                        compacted_len = len(tool_res)
                        tool_res = (
                            f"{tool_res[:1000]}\n\n"
                            f"[... {compacted_len - 2000} characters COMPACTED/OMITTED by system to optimize token context ...]\n\n"
                            f"{tool_res[-1000:]}"
                        )
                    llm_prompt += f"Tool Called: {h['tool']}\nArguments: {json.dumps(h['args'])}\nResult:\n{tool_res}\n\n"
            
            try:
                raw_res = LLMClient.call_llm(LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, llm_prompt, system_instruction, response_format_json=True)
                cleaned_res = LLMClient.clean_json_response(raw_res)
                action = json.loads(cleaned_res)
            except Exception as e:
                cls.send_message(f"❌ *Failed to get next agent action:* `{e}`", bot_token, chat_id)
                return
                
            tool_name = action.get("tool")
            if not tool_name:
                cls.send_message("❌ *Agent returned an empty or invalid tool invocation.*", bot_token, chat_id)
                return
                
            if tool_name == "final_answer":
                message = action.get("message", "Task complete.")
                cls.send_message(message, bot_token, chat_id)
                # Record response in history!
                cls.record_chat_history(chat_id, "assistant", message, db)
                
                if should_restart:
                    cls.send_message("🔄 *Hot-reloading system daemon now... / Sistem kendini yeniden başlatıyor...*", bot_token, chat_id)
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                return
                
            cls.send_message(f"⚙️ *Agent running tool:* `{tool_name}`...", bot_token, chat_id)
            logging.info(f"[Agent Loop] Running tool: {tool_name} with args: {action}")
            tool_result = ""
            
            try:
                if tool_name == "execute_bash":
                    cmd = action.get("command", "")
                    logging.info(f"[Agent Tool execute_bash] Command: {cmd}")
                    import subprocess
                    try:
                        res = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=15)
                        tool_result = f"STDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\nEXIT CODE: {res.returncode}"
                    except subprocess.TimeoutExpired as te:
                        stdout = te.stdout.decode("utf-8", errors="ignore") if te.stdout else ""
                        stderr = te.stderr.decode("utf-8", errors="ignore") if te.stderr else ""
                        tool_result = f"ERROR: Command timed out after 15 seconds.\nSTDOUT SO FAR:\n{stdout}\nSTDERR SO FAR:\n{stderr}"
                    
                elif tool_name == "read_file":
                    path = action.get("filepath", "")
                    start_line = action.get("start_line")
                    end_line = action.get("end_line")
                    logging.info(f"[Agent Tool read_file] Path: {path}, Lines: {start_line}-{end_line}")
                    with open(path, "r", encoding="utf-8") as f:
                        if start_line is not None or end_line is not None:
                            lines = f.readlines()
                            start_num = int(start_line) if start_line is not None else 1
                            end_num = int(end_line) if end_line is not None else len(lines)
                            
                            # Clamp values to safe boundaries
                            start_num = max(1, min(start_num, len(lines)))
                            end_num = max(1, min(end_num, len(lines)))
                            if start_num > end_num:
                                start_num, end_num = end_num, start_num
                                
                            s = start_num - 1
                            e = end_num
                            
                            requested_lines = e - s
                            if requested_lines > 300:
                                s_first = s
                                e_first = s + 150
                                s_last = e - 150
                                e_last = e
                                first_part = "".join(lines[s_first:e_first])
                                last_part = "".join(lines[s_last:e_last])
                                tool_result = (
                                    f"{first_part}\n\n"
                                    f"[TRUNCATED: The range you requested (from line {start_num} to {end_num}) is too large ({requested_lines} lines).\n"
                                    f"To prevent API timeouts and token window congestion, the system has truncated the output.\n"
                                    f"Showing the first 150 lines ({start_num} to {start_num + 150}) and the last 150 lines ({end_num - 150} to {end_num}).\n"
                                    f"If you need to scan this entire section, please call 'read_file' systematically in smaller chunks of maximum 300 lines each (e.g. read lines {start_num} to {start_num + 300} first).]\n\n"
                                    f"{last_part}"
                                )
                            else:
                                tool_result = "".join(lines[s:e])
                        else:
                            # Smart autonomous chunking: default to reading 20,000 characters.
                            # If the file is larger, append a highly informative footer detailing total size/lines and guiding chunked reads.
                            content_data = f.read(20000)
                            f.seek(0)
                            total_lines = len(f.readlines())
                            f.seek(0, 2)
                            total_size = f.tell()
                            if total_size > 20000:
                                tool_result = (
                                    f"{content_data}\n\n"
                                    f"[TRUNCATED: Only first 20,000 characters shown. The file '{path}' is {total_size} bytes long (approximately {total_lines} lines).\n"
                                    f"To locate other sections or scan the codebase autonomously section-by-section, you MUST call 'read_file' again "
                                    f"using 'start_line' and 'end_line' parameters (e.g. start_line=350, end_line=700).]"
                                )
                            else:
                                tool_result = content_data
                        
                elif tool_name == "write_file":
                    path = action.get("filepath", "")
                    logging.info(f"[Agent Tool write_file] Path: {path}")
                    content = action.get("content", "")
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)
                    tool_result = f"Successfully wrote file: {path}"
                    
                elif tool_name == "query_database":
                    sql = action.get("sql", "")
                    logging.info(f"[Agent Tool query_database] SQL: {sql}")
                    with db_lock:
                        with db.get_connection() as conn:
                            rows = conn.execute(sql).fetchall()
                            tool_result = json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=2)
                            
                elif tool_name == "modify_code":
                    find_val = action.get("find", "")
                    replace_val = action.get("replace", "")
                    
                    file_path = "app.py"
                    with open(file_path, "r", encoding="utf-8") as f:
                        current_code = f.read()
                        
                    if find_val in current_code:
                        modified = current_code.replace(find_val, replace_val, 1)
                        temp_file = "app_temp.py"
                        with open(temp_file, "w", encoding="utf-8") as f:
                            f.write(modified)
                            
                        import py_compile
                        py_compile.compile(temp_file, doraise=True)
                        
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(modified)
                            
                        try:
                            os.remove(temp_file)
                        except Exception:
                            pass
                            
                        tool_result = "SUCCESS: Code modified successfully. System will hot-reload once final_answer is reached."
                        should_restart = True
                    else:
                        tool_result = "ERROR: Code block to replace was not matched in app.py."
                else:
                    tool_result = f"ERROR: Unknown tool name '{tool_name}'"
            except Exception as ex:
                tool_result = f"ERROR: Tool execution failed: {ex}"
                
            history.append({
                "tool": tool_name,
                "args": action,
                "result": tool_result
            })
            
        cls.send_message("⚠️ *Agent reached maximum ReAct loop iterations (6). Terminating run for safety.*", bot_token, chat_id)
        if should_restart:
            cls.send_message("🔄 *Hot-reloading system daemon now...*", bot_token, chat_id)
            os.execv(sys.executable, [sys.executable] + sys.argv)

    @classmethod
    def process_command(cls, chat_id: str, text: str, bot_token: str, db: DatabaseManager):
        with db_lock:
            with db.get_connection() as conn:
                user = conn.execute("SELECT * FROM users WHERE chat_id = ?", (chat_id,)).fetchone()
            
        if not text.startswith("/"):
            cls.handle_natural_language_code_mod(chat_id, text, bot_token, db)
            return

        if text.startswith("/start"):
            if not user:
                # Register new user immediately
                with db_lock:
                    with db.get_connection() as conn:
                        conn.execute("INSERT INTO users (chat_id, language, region) VALUES (?, 'en', 'global')", (chat_id,))
                        conn.commit()
                welcome = LOCALIZATION["en"]["welcome_new"]
            else:
                lang = user["language"]
                welcome = LOCALIZATION[lang]["welcome_back"]
            cls.send_message(welcome, bot_token, chat_id)
            return

        if not user:
            cls.send_message(LOCALIZATION["en"]["start_first"], bot_token, chat_id)
            return

        lang = user["language"]

        # 1. /settings sequential step-by-step dropdown wizard (Starts with Language Select)
        if text.startswith("/settings"):
            text_str = "🗣️ *Select System Language / Sistem Dili Seçin:*"
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "🇬🇧 English", "callback_data": "lang_en"},
                        {"text": "🇹🇷 Türkçe", "callback_data": "lang_tr"},
                        {"text": "🌐 All / Her İkisi", "callback_data": "lang_all"}
                    ]
                ]
            }
            cls.send_message(text_str, bot_token, chat_id, reply_markup=reply_markup)

        # 1.5 Custom Prompt Configuration Command
        elif text.startswith("/prompt"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                current_prompt = user["custom_prompt"] if "custom_prompt" in user.keys() and user["custom_prompt"] else "(None / Tanımlanmadı)"
                if lang == "tr":
                    msg = (
                        "📝 *Özel Filtreleme Promptu* 📝\n\n"
                        "Takip edilen sitelerde ve aramalarda yapay zekanın neye göre filtreleme yapacağını belirleyin! (Örn: Sadece stajlar, sadece Python ilanları vb.)\n\n"
                        f"👉 *Mevcut Ayar:* `{current_prompt}`\n\n"
                        "✍️ *Kullanım:* `/prompt <kurallarınız>`\n"
                        "🧹 *Sıfırlamak İçin:* `/prompt reset`"
                    )
                elif lang == "all":
                    msg = (
                        "📝 *Custom Filter Prompt / Özel Filtreleme Promptu* 📝\n\n"
                        "Set rules for AI to filter search and custom site crawls! / Yapay zekanın süzgeç kurallarını belirleyin!\n\n"
                        f"👉 *Current / Mevcut:* `{current_prompt}`\n\n"
                        "✍️ *Usage / Kullanım:* `/prompt <instructions / kurallar>`\n"
                        "🧹 *To Reset / Sıfırlamak İçin:* `/prompt reset`"
                    )
                else:
                    msg = (
                        "📝 *Custom AI Filtering Prompt* 📝\n\n"
                        "Configure your own AI filter rules for crawls! E.g. search only for remote internships, Python tools, or specific announcements.\n\n"
                        f"👉 *Current Prompt:* `{current_prompt}`\n\n"
                        "✍️ *Usage:* `/prompt <your instructions>`\n"
                        "🧹 *To Reset:* `/prompt reset`"
                    )
                cls.send_message(msg, bot_token, chat_id)
                return
                
            prompt_val = parts[1].strip()
            if prompt_val.lower() == "reset":
                with db_lock:
                    with db.get_connection() as conn:
                        conn.execute("UPDATE users SET custom_prompt = NULL WHERE chat_id = ?", (chat_id,))
                        conn.commit()
                if lang == "tr":
                    msg = "🧹 *Özel filtreleme kuralları sıfırlandı!* Standart kariyer fırsatı kurallarına geri dönüldü."
                elif lang == "all":
                    msg = "🧹 *Custom rules reset! / Özel filtreleme kuralları sıfırlandı!* Returned to standard filters."
                else:
                    msg = "🧹 *Custom prompt reset successfully!* Returned to standard technology career filters."
            else:
                with db_lock:
                    with db.get_connection() as conn:
                        conn.execute("UPDATE users SET custom_prompt = ? WHERE chat_id = ?", (prompt_val, chat_id))
                        conn.commit()
                if lang == "tr":
                    msg = f"✅ *Özel filtreleme kuralları güncellendi!*\nYeni Kural: `{prompt_val}`"
                elif lang == "all":
                    msg = f"✅ *Custom rules updated! / Filtreleme kuralları güncellendi!*\nRule: `{prompt_val}`"
                else:
                    msg = f"✅ *Custom filter rules updated!*\nRule: `{prompt_val}`"
            cls.send_message(msg, bot_token, chat_id)
            return

        # 2. Add Tracked Website
        elif text.startswith("/add"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                cls.send_message(LOCALIZATION[lang]["add_url_missing"], bot_token, chat_id)
                return
            target_url = parts[1].strip()
            if not target_url.startswith("http://") and not target_url.startswith("https://"):
                target_url = "https://" + target_url
            try:
                with db_lock:
                    with db.get_connection() as conn:
                        conn.execute("INSERT OR IGNORE INTO tracked_sites (chat_id, url) VALUES (?, ?)", (chat_id, target_url))
                        conn.commit()
                msg = LOCALIZATION[lang]["add_url_success"].format(url=target_url)
            except Exception as e:
                msg = LOCALIZATION[lang]["add_url_error"].format(error=e)
            cls.send_message(msg, bot_token, chat_id)

        # 3. List Tracked Websites
        elif text.startswith("/list"):
            with db_lock:
                with db.get_connection() as conn:
                    rows = conn.execute("SELECT id, url FROM tracked_sites WHERE chat_id = ?", (chat_id,)).fetchall()
            if not rows:
                cls.send_message(LOCALIZATION[lang]["list_empty"], bot_token, chat_id)
                return
            sites_str = "\n".join([f"🔹 *{r['id']}* - {r['url']}" for r in rows])
            cls.send_message(LOCALIZATION[lang]["list_title"].format(sites=sites_str), bot_token, chat_id)

        # 4. Remove Tracked Website
        elif text.startswith("/remove"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                cls.send_message(LOCALIZATION[lang]["remove_id_missing"], bot_token, chat_id)
                return
            target_id = parts[1].strip()
            with db_lock:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM tracked_sites WHERE chat_id = ? AND id = ?", (chat_id, target_id))
                    conn.commit()
                    deleted = cursor.rowcount
            if deleted > 0:
                cls.send_message(LOCALIZATION[lang]["remove_success"].format(id=target_id), bot_token, chat_id)
            else:
                cls.send_message(LOCALIZATION[lang]["remove_not_found"], bot_token, chat_id)

        # 5. Add Job Application
        elif text.startswith("/apply"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                cls.send_message(LOCALIZATION[lang]["apply_name_missing"], bot_token, chat_id)
                return
            name = parts[1].strip()
            date_logged = datetime.now().strftime("%Y-%m-%d")
            with db_lock:
                with db.get_connection() as conn:
                    conn.execute("""
                        INSERT INTO applications (chat_id, opportunity_name, organizer, status, date_logged)
                        VALUES (?, ?, ?, 'Applied', ?)
                    """, (chat_id, name, "Unknown", date_logged))
                    conn.commit()
            cls.send_message(LOCALIZATION[lang]["apply_success"].format(name=name), bot_token, chat_id)

        # 6. List Job Applications
        elif text.startswith("/applications"):
            with db_lock:
                with db.get_connection() as conn:
                    rows = conn.execute("SELECT id, opportunity_name, status, date_logged FROM applications WHERE chat_id = ?", (chat_id,)).fetchall()
            if not rows:
                cls.send_message(LOCALIZATION[lang]["apps_empty"], bot_token, chat_id)
                return
            
            list_str = ""
            for r in rows:
                status = r["status"].lower().strip()
                status_emoji = "📝"
                if "interview" in status or "mülakat" in status:
                    status_emoji = "📞"
                elif "accepted" in status or "kabul" in status:
                    status_emoji = "🎉"
                elif "reject" in status or "red" in status:
                    status_emoji = "❌"
                list_str += f"{status_emoji} *ID: {r['id']}* | `{r['opportunity_name']}`\n      🚦 Status: *{r['status']}* | 📅 {r['date_logged']}\n\n"
            
            cls.send_message(LOCALIZATION[lang]["apps_title"].format(apps=list_str), bot_token, chat_id)

        # 7. Update Job Status
        elif text.startswith("/status"):
            parts = text.split(maxsplit=2)
            if len(parts) < 3:
                cls.send_message(LOCALIZATION[lang]["status_missing"], bot_token, chat_id)
                return
            target_id = parts[1].strip()
            new_status = parts[2].strip()
            
            formatted_status = new_status.capitalize()
            if new_status.lower() in ("interview", "mülakat"):
                formatted_status = "📞 Interview"
            elif new_status.lower() in ("accepted", "kabul", "accept"):
                formatted_status = "🎉 Accepted"
            elif new_status.lower() in ("rejected", "red", "reject"):
                formatted_status = "❌ Rejected"
            elif new_status.lower() in ("applied", "başvuruldu"):
                formatted_status = "📝 Applied"

            with db_lock:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE applications SET status = ? WHERE chat_id = ? AND id = ?", (formatted_status, chat_id, target_id))
                    conn.commit()
                    updated = cursor.rowcount
            if updated > 0:
                cls.send_message(LOCALIZATION[lang]["status_success"].format(id=target_id, status=formatted_status), bot_token, chat_id)
            else:
                cls.send_message(LOCALIZATION[lang]["status_not_found"], bot_token, chat_id)

        # 8. Delete Job Application
        elif text.startswith("/delete"):
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                cls.send_message(LOCALIZATION[lang]["delete_id_missing"], bot_token, chat_id)
                return
            target_id = parts[1].strip()
            with db_lock:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM applications WHERE chat_id = ? AND id = ?", (chat_id, target_id))
                    conn.commit()
                    deleted = cursor.rowcount
            if deleted > 0:
                cls.send_message(LOCALIZATION[lang]["delete_success"].format(id=target_id), bot_token, chat_id)
            else:
                cls.send_message(LOCALIZATION[lang]["delete_not_found"], bot_token, chat_id)


# Telegram Bot Commands Menu Registration (Registers commands directly inside the Telegram Slash Dropdown Menu)
def set_bot_commands(bot_token: str):
    if not bot_token:
        return
    url = f"https://api.telegram.org/bot{bot_token}/setMyCommands"
    payload = {
        "commands": [
            {"command": "start", "description": "Initialize/Activate your CareerAgent profile"},
            {"command": "settings", "description": "Open settings panel (Language & Region settings)"},
            {"command": "prompt", "description": "Configure custom AI rules for crawling (e.g. /prompt your rules)"},
            {"command": "add", "description": "Track custom website for announcements (e.g. /add URL)"},
            {"command": "list", "description": "List custom websites you are currently tracking"},
            {"command": "remove", "description": "Stop tracking a site (e.g. /remove ID)"},
            {"command": "apply", "description": "Log new job application record (e.g. /apply Google)"},
            {"command": "applications", "description": "Open job application tracker board"},
            {"command": "status", "description": "Update application status stage (e.g. /status ID interview)"},
            {"command": "delete", "description": "Delete job application record (e.g. /delete ID)"}
        ]
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            logging.info("Telegram Slash commands dropdown menu registered successfully!")
        else:
            logging.warning(f"Failed to register slash commands menu: {resp.text}")
    except Exception as e:
        logging.error(f"Error registering Telegram commands menu: {e}")


# Telegram Bot Polling Thread Function
def telegram_polling_worker(bot_token: str, db: DatabaseManager, authorized_ids: list):
    logging.info("Starting concurrent Telegram Bot Polling Thread...")
    while keep_running:
        try:
            TelegramBot.check_updates(bot_token, db, authorized_ids)
        except Exception as e:
            logging.error(f"Error in Telegram Polling Thread: {e}")
        time.sleep(1.5)


# Main sweep cycles runner
def run_user_sweeps(db: DatabaseManager, firecrawl_key: str, provider: str, model: str, api_key: str, bot_token: str):
    logging.info("Initiating dynamic daily sweep checks for all users...")
    
    with db_lock:
        with db.get_connection() as conn:
            users = conn.execute("SELECT * FROM users").fetchall()
            
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    for user in users:
        if not keep_running:
            break
            
        chat_id = user["chat_id"]
        lang = user["language"]
        region = user["region"]
        
        # Check daily run logs
        if user["last_run_date"] == today_str:
            logging.info(f"Daily sweep already completed for User: {chat_id}. Skipping search.")
        else:
            logging.info(f"Triggering active search sweep for User: {chat_id}...")
            
            # --- PIPELINE 1: General Web Searches (Default Rules) ---
            queries = generate_search_queries_with_ai(region, lang, provider, model, api_key)
            search_results = []
            
            for idx, query in enumerate(queries):
                if not keep_running:
                    break
                # Apply optimized limits to fit within credit constraints (Niche queries get limit=7, General get limit=5)
                limit_val = 7 if idx >= 5 else 5
                res = FirecrawlClient.firecrawl_search(query, firecrawl_key, limit=limit_val)
                if res:
                    search_results.extend(res)
                    
            if not search_results and firecrawl_key:
                if keep_running:
                    agent_prompt = get_agent_prompt(region)
                    res = FirecrawlClient.firecrawl_agent(agent_prompt, firecrawl_key)
                    if res:
                        search_results.extend(res)
            
            # --- PIPELINE 2: Custom Tracked Sited Crawling (User Custom Prompt Rules) ---
            with db_lock:
                with db.get_connection() as conn:
                    user_sites = conn.execute("SELECT id, url, last_hash FROM tracked_sites WHERE chat_id = ?", (chat_id,)).fetchall()
            
            tracked_site_results = []
            for site in user_sites:
                if not keep_running:
                    break
                site_res = FirecrawlClient.scrape_tracked_site(site["url"])
                markdown_content = site_res.get("markdown", "")
                
                # Generate unique content MD5 hash
                content_hash = hashlib.md5(markdown_content.encode("utf-8", errors="ignore")).hexdigest()
                
                if site["last_hash"] == content_hash:
                    logging.info(f"[User {chat_id}] No changes detected on custom site: {site['url']}. Skipping AI analysis block to prevent spam.")
                else:
                    # Content updated! Append to LLM and update hash log
                    logging.info(f"[User {chat_id}] New updates/announcements detected on custom site: {site['url']}. Appending for AI review...")
                    tracked_site_results.append(site_res)
                    
                    with db_lock:
                        with db.get_connection() as conn:
                            conn.execute("UPDATE tracked_sites SET last_hash = ? WHERE id = ?", (content_hash, site["id"]))
                            conn.commit()

            # Retrieve sent history for de-duplication
            with db_lock:
                with db.get_connection() as conn:
                    history_rows = conn.execute("SELECT title, url FROM sent_history WHERE chat_id = ?", (chat_id,)).fetchall()
            
            normalized_sent_urls = {normalize_url(h["url"]) for h in history_rows if h["url"]}
            sent_titles = {h["title"].lower().strip() for h in history_rows if h["title"]}
            recent_sent_text = "\n".join([f"- {h['title']} ({h['url']})" for h in history_rows[-25:]])

            # --- PROCESS & SEND PIPELINE 1: General Web Searches ---
            if search_results:
                filtered_search = []
                for res in search_results:
                    url = res.get("url", "")
                    title = res.get("title", "").strip()
                    norm_url = normalize_url(url)
                    if (norm_url and norm_url in normalized_sent_urls) or (title and title.lower() in sent_titles):
                        continue
                    filtered_search.append(res)
                
                if filtered_search:
                    compiled_search = compile_data_to_prompt(filtered_search)
                    opps_search = filter_and_format_events(compiled_search, provider, model, api_key, lang, recent_sent_text, custom_prompt=None)
                    
                    if opps_search:
                        # 1. Save new opportunities in SQLite database
                        with db_lock:
                            with db.get_connection() as conn:
                                for opp in opps_search:
                                    conn.execute("""
                                        INSERT OR IGNORE INTO opportunities (chat_id, title, url, deadline_date, start_date, created_date)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """, (chat_id, opp["title"], opp["url"], opp.get("deadline"), opp.get("start_date"), today_str))
                                conn.commit()
                        
                        # 2. Build Telegram Markdown message
                        markdown_text = ""
                        for opp in opps_search:
                            markdown_text += (
                                f"🚀 *[{opp['title']}]* ({opp.get('type', 'Opportunity')})\n"
                                f"🏢 *Organizer:* {opp.get('organizer', 'N/A')}\n"
                                f"📅 *Deadline:* `{opp.get('deadline') or 'N/A'}` | *Start:* `{opp.get('start_date') or 'N/A'}`\n"
                                f"📝 *Summary:* {opp.get('summary')}\n"
                                f"💡 *Mentor Advice:*\n"
                                f"   *   🎯 *Skills:* {opp.get('skills')}\n"
                                f"   *   💼 *CV Value:* {opp.get('cv_value')}\n"
                                f"   *   🏃 *First Step:* {opp.get('first_step')}\n"
                                f"🔗 [Click Here for Details]({opp['url']})\n\n"
                            )
                        
                        if lang == "tr":
                            header = f"📢 *GÜNLÜK FIRSATLAR RAPORU* 📢\n\n"
                            footer = f"\n\n🤖 _CareerAgent otonom asistanı tarafından gönderildi._"
                        elif lang == "all":
                            header = f"📢 *DAILY OPPORTUNITIES / GÜNLÜK FIRSATLAR* 📢\n\n"
                            footer = f"\n\n🤖 _Sent automatically by CareerAgent daemon / Otonom asistan tarafından gönderildi._"
                        else:
                            header = f"📢 *DAILY TECH OPPORTUNITIES REPORT* 📢\n\n"
                            footer = f"\n\n🤖 _Sent automatically by CareerAgent daemon._"
                        
                        full_message = f"{header}{markdown_text}{footer}"
                        TelegramBot.send_message(full_message, bot_token, chat_id)
                        
                        # Store in sent history
                        with db_lock:
                            with db.get_connection() as conn:
                                for opp in opps_search:
                                    conn.execute("INSERT OR IGNORE INTO sent_history (chat_id, title, url, sent_date) VALUES (?, ?, ?, ?)", (chat_id, opp["title"], opp["url"], today_str))
                                conn.commit()
            
            # --- PROCESS & SEND PIPELINE 2: Custom Tracked Sites (User Custom Rules) ---
            if tracked_site_results:
                filtered_tracked = []
                for res in tracked_site_results:
                    url = res.get("url", "")
                    title = res.get("title", "").strip()
                    norm_url = normalize_url(url)
                    if (norm_url and norm_url in normalized_sent_urls) or (title and title.lower() in sent_titles):
                        continue
                    filtered_tracked.append(res)
                
                if filtered_tracked:
                    compiled_tracked = compile_data_to_prompt(filtered_tracked)
                    custom_prompt = None
                    try:
                        custom_prompt = user["custom_prompt"]
                    except Exception:
                        pass
                    
                    opps_tracked = filter_and_format_events(compiled_tracked, provider, model, api_key, lang, recent_sent_text, custom_prompt)
                    
                    if opps_tracked:
                        # 1. Save new opportunities in SQLite database
                        with db_lock:
                            with db.get_connection() as conn:
                                for opp in opps_tracked:
                                    conn.execute("""
                                        INSERT OR IGNORE INTO opportunities (chat_id, title, url, deadline_date, start_date, created_date)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """, (chat_id, opp["title"], opp["url"], opp.get("deadline"), opp.get("start_date"), today_str))
                                conn.commit()
                        
                        # 2. Build Telegram Markdown message
                        markdown_text = ""
                        for opp in opps_tracked:
                            markdown_text += (
                                f"🚀 *[{opp['title']}]* ({opp.get('type', 'Opportunity')})\n"
                                f"🏢 *Source/Organizer:* {opp.get('organizer', 'N/A')}\n"
                                f"📅 *Deadline:* `{opp.get('deadline') or 'N/A'}` | *Start:* `{opp.get('start_date') or 'N/A'}`\n"
                                f"📝 *Summary:* {opp.get('summary')}\n"
                                f"💡 *AI Insights:*\n"
                                f"   *   🎯 *Key Points:* {opp.get('skills')}\n"
                                f"   *   💼 *Value:* {opp.get('cv_value')}\n"
                                f"   *   🏃 *First Step:* {opp.get('first_step')}\n"
                                f"🔗 [Click Here for Details]({opp['url']})\n\n"
                            )
                        
                        if lang == "tr":
                            header = f"📢 *TAKİP EDİLEN SİTELER RAPORU* 📢\n\n"
                            footer = f"\n\n🤖 _CareerAgent otonom asistanı tarafından gönderildi._"
                        elif lang == "all":
                            header = f"📢 *TRACKED WEBSITES UPDATE / TAKİP EDİLEN SİTELER GÜNCELLEMESİ* 📢\n\n"
                            footer = f"\n\n🤖 _Sent automatically by CareerAgent daemon / Otonom asistan tarafından gönderildi._"
                        else:
                            header = f"📢 *TRACKED WEBSITES UPDATE REPORT* 📢\n\n"
                            footer = f"\n\n🤖 _Sent automatically by CareerAgent daemon._"
                        
                        full_message = f"{header}{markdown_text}{footer}"
                        TelegramBot.send_message(full_message, bot_token, chat_id)
                        
                        # Store in sent history
                        with db_lock:
                            with db.get_connection() as conn:
                                for opp in opps_tracked:
                                    conn.execute("INSERT OR IGNORE INTO sent_history (chat_id, title, url, sent_date) VALUES (?, ?, ?, ?)", (chat_id, opp["title"], opp["url"], today_str))
                                conn.commit()
            
            # --- 📅 PIPELINE 3: Active Reminders Check (Deadline & Activity Start Reminders) ---
            logging.info(f"Checking upcoming deadline and program start reminders for User: {chat_id}...")
            with db_lock:
                with db.get_connection() as conn:
                    opps_to_notify = conn.execute(
                        "SELECT * FROM opportunities WHERE chat_id = ? AND (deadline_date = ? OR start_date = ?)", 
                        (chat_id, today_str, today_str)
                    ).fetchall()
                    user_apps = conn.execute("SELECT opportunity_name FROM applications WHERE chat_id = ?", (chat_id,)).fetchall()
            
            app_names_lower = [a["opportunity_name"].lower().strip() for a in user_apps]
            
            for opp in opps_to_notify:
                opp_title_lower = opp["title"].lower().strip()
                
                already_applied = False
                for app_name in app_names_lower:
                    if opp_title_lower in app_name or app_name in opp_title_lower:
                        already_applied = True
                        break
                
                # 1. Son Başvuru Günü Hatırlatması (Deadline Reminder)
                if opp["deadline_date"] == today_str and opp["notified_deadline"] == 0:
                    if not already_applied:
                        if lang == "tr":
                            reminder_msg = (
                                "⚠️ *SON BAŞVURU GÜNÜ HATIRLATMASI!* ⚠️\n\n"
                                f"📌 *Fırsat:* [{opp['title']}]({opp['url']})\n"
                                f"📅 *Son Başvuru Tarihi:* BUGÜN! (`{opp['deadline_date']}`)\n\n"
                                "Bu fırsata henüz başvurmadınız gibi görünüyor. Kaçırmamak için hemen inceleyin! 🚀"
                            )
                        elif lang == "all":
                            reminder_msg = (
                                "⚠️ *APPLICATION DEADLINE REMINDER / SON BAŞVURU HATIRLATMASI!* ⚠️\n\n"
                                f"📌 *Opportunity / Fırsat:* [{opp['title']}]({opp['url']})\n"
                                f"📅 *Deadline / Son Başvuru:* TODAY / BUGÜN! (`{opp['deadline_date']}`)\n\n"
                                "You haven't logged an application for this yet. Don't miss out! / Kaçırmamak için hemen inceleyin! 🚀"
                            )
                        else:
                            reminder_msg = (
                                "⚠️ *APPLICATION DEADLINE REMINDER!* ⚠️\n\n"
                                f"📌 *Opportunity:* [{opp['title']}]({opp['url']})\n"
                                f"📅 *Deadline:* TODAY! (`{opp['deadline_date']}`)\n\n"
                                "It looks like you haven't applied to this opportunity yet. Don't miss out! 🚀"
                            )
                        TelegramBot.send_message(reminder_msg, bot_token, chat_id)
                    
                    with db_lock:
                        with db.get_connection() as conn:
                            conn.execute("UPDATE opportunities SET notified_deadline = 1 WHERE id = ?", (opp["id"],))
                            conn.commit()
                
                # 2. Faaliyet/Program Başlangıç Günü Hatırlatması (Start Date Reminder)
                if opp["start_date"] == today_str and opp["notified_start"] == 0:
                    if lang == "tr":
                        reminder_msg = (
                            "🎉 *PROGRAM BUGÜN BAŞLIYOR!* 🎉\n\n"
                            f"📌 *Fırsat:* [{opp['title']}]({opp['url']})\n"
                            f"📅 *Faaliyet Başlangıç Zamanı:* BUGÜN! (`{opp['start_date']}`)\n\n"
                            "Gelişim yolculuğunuzda başarılar dileriz! Harika bir süreç olsun! 💻💪"
                        )
                    elif lang == "all":
                        reminder_msg = (
                            "🎉 *PROGRAM STARTING TODAY / ETKİNLİK BUGÜN BAŞLIYOR!* 🎉\n\n"
                            f"📌 *Opportunity / Fırsat:* [{opp['title']}]({opp['url']})\n"
                            f"📅 *Start Date / Başlangıç:* TODAY / BUGÜN! (`{opp['start_date']}`)\n\n"
                            "We wish you great success in this journey! / Gelişim yolculuğunuzda başarılar dileriz! 💻💪"
                        )
                    else:
                        reminder_msg = (
                            "🎉 *PROGRAM STARTING TODAY!* 🎉\n\n"
                            f"📌 *Opportunity:* [{opp['title']}]({opp['url']})\n"
                            f"📅 *Start Date:* TODAY! (`{opp['start_date']}`)\n\n"
                            "We wish you the best of luck on your new learning journey! 💻💪"
                        )
                    TelegramBot.send_message(reminder_msg, bot_token, chat_id)
                    
                    with db_lock:
                        with db.get_connection() as conn:
                            conn.execute("UPDATE opportunities SET notified_start = 1 WHERE id = ?", (opp["id"],))
                            conn.commit()
            
            # Log run date completion in DB
            with db_lock:
                with db.get_connection() as conn:
                    conn.execute("UPDATE users SET last_run_date = ? WHERE chat_id = ?", (today_str, chat_id))
                    conn.commit()

        # Scan active email inbox sweeps if active for this user
        if user["email_active"] == 1:
            EmailScanner.scan_inbox(user, db, provider, model, api_key, bot_token)


# Helper Functions
def normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        normalized = parsed._replace(query="", fragment="")
        return urlunparse(normalized).lower().rstrip('/')
    except Exception:
        return url.lower().rstrip('/')

def compile_data_to_prompt(firecrawl_results: list) -> str:
    compiled_text = ""
    if firecrawl_results:
        compiled_text += "### INTERNET SEARCH & TRACKED SITE PAYLOADS:\n"
        for idx, res in enumerate(firecrawl_results, 1):
            title = res.get("title", "Not Specified")
            url = res.get("url", "")
            desc = res.get("description", "")
            markdown = res.get("markdown", "")
            compiled_text += f"\n[Result {idx}]\nTitle: {title}\nLink: {url}\nDescription: {desc}\nDetails:\n{markdown[:1500]}\n"
    return compiled_text

def generate_search_queries_with_ai(region: str, language: str, provider: str, model: str, api_key: str) -> list:
    system_instruction = (
        "You are an expert search engine optimization engineer and a technology career opportunity hunter.\n"
        "Your job is to output exactly 10 highly optimized search queries to find active, free technology opportunities for developers.\n\n"
        "MANDATORY STRUCTURE — You MUST follow this structure exactly:\n"
        "General Searches (Queries 1-5):\n"
        "1. Hackathon/Ideathon based opportunities.\n"
        "2. Free tech/coding/AI certificate programs.\n"
        "3. Tech/software developer internship listings.\n"
        "4. Software training courses/bootcamps.\n"
        "5. General technology career/opportunity search.\n\n"
        "Niche/Specific Searches (Queries 6-10):\n"
        "6. BTK Akademi focused (use site:btkakademi.gov.tr or 'BTK Akademi').\n"
        "7. Patika.dev focused (use site:patika.dev or 'Patika.dev').\n"
        "8. Coderspace, Kodluyoruz, or Techcareer.net focused (use site:coderspace.co, site:kodluyoruz.org, site:techcareer.net, 'Coderspace', 'Kodluyoruz', or 'Techcareer').\n"
        "9. Niche programs or active opportunities from Google.\n"
        "10. Niche programs or active opportunities from Microsoft.\n\n"
        "RULES:\n"
        "- Output exactly 10 lines, one raw search query per line.\n"
        "- Do NOT include headers, category names, bullets, numbers, quotes, or markdown.\n"
        "- Tailor all queries deeply to the specified region, language, and the year 2026."
    )
    prompt = (
        f"Generate exactly 10 highly optimized search queries for the following settings:\n"
        f"Target Region: {region}\n"
        f"Target Language: {language}\n"
        f"Year: 2026\n"
        f"Remember: Use the 5 general + 5 niche structure exactly."
    )
    
    try:
        response = LLMClient.call_llm(provider, model, api_key, prompt, system_instruction)
        queries = []
        for line in response.split("\n"):
            line = re.sub(r'^\d+[\.\-\)]\s*', '', line)
            line = line.strip().strip('"').strip("'")
            if line:
                queries.append(line)
        if len(queries) < 3:
            raise ValueError("LLM returned too few queries.")
        return queries
    except Exception as e:
        logging.warning(f"Failed to generate queries: {e}. Fallback to static.")
        return get_search_queries(region, language)

def get_search_queries(region: str, language: str) -> list:
    region = region.lower().strip()
    language = language.lower().strip()
    if region == "tr" or (region == "global" and language == "tr") or language == "tr":
        return [
            "ücretsiz yazılım kampı hackathon ideathon yarışmaları 2026",
            "ücretsiz yazılım yapay zeka sertifika programları kursları 2026",
            "yazılım geliştirici staj ilanları stajyer alımı başvuruları 2026",
            "ücretsiz yazılım eğitim kursları online bootcamp dersleri 2026",
            "yazılım kariyer fırsatları ücretsiz teknoloji eğitimleri 2026",
            "site:btkakademi.gov.tr yazılım eğitim kampı bilişim bootcamp 2026",
            "site:patika.dev yazılım eğitim kampları ücretsiz bootcamp 2026",
            "site:coderspace.co OR site:kodluyoruz.org OR site:techcareer.net ücretsiz yazılım etkinlikleri bootcamp kariyer 2026",
            "Google ücretsiz yazılım sertifika programı staj kampı 2026",
            "Microsoft ücretsiz bulut yazılım eğitim programları 2026"
        ]
    return [
        "free coding hackathon ideathon software developer contest 2026",
        "free software engineering AI cloud certificate program 2026",
        "software developer engineering internship active application openings 2026",
        "free software developer training courses intensive bootcamp 2026",
        "software engineering career opportunities global free tech programs 2026",
        "site:btkakademi.gov.tr free software training courses 2026",
        "site:patika.dev free coding bootcamp active registration 2026",
        "site:coderspace.co OR site:kodluyoruz.org OR site:techcareer.net free tech career events bootcamps 2026",
        "Google free coding training developer internship certificate 2026",
        "Microsoft free cloud engineering certificate training 2026"
    ]

def get_agent_prompt(region: str) -> str:
    region = region.lower().strip()
    if region == "tr":
        return "Find currently active bootcamps, hackathons and CTF opportunities in 2026 for developers in Turkey. Retrieve details."
    return "Find currently active free remote coding bootcamps, online developer hackathons, and CTF competitions in 2026 globally."

def filter_and_format_events(raw_data_text: str, provider: str, model: str, api_key: str, language: str, recent_sent_text: str = "", custom_prompt: str = None) -> list:
    """Utilizes the configured AI provider through LiteLLM to filter events, extract structured dates, and return a JSON list of opportunities."""
    if custom_prompt and custom_prompt.strip():
        system_instruction = (
            "You are an autonomous custom site and event filtering agent. Your task is to extract relevant opportunities, news, or updates from the raw data payload according to the user's custom instructions.\n\n"
            f"USER'S CUSTOM FILTER INSTRUCTIONS (Strictly prioritize these):\n"
            f"{custom_prompt}\n\n"
            "RULES:\n"
            "1. ONLY extract information that matches the user's custom instructions above. If an entry does not match, ignore it.\n"
            "2. For each extracted entry, you MUST strictly extract/infer the application deadline and the program/event start date in YYYY-MM-DD format. If not mentioned and cannot be reasonably inferred, set to null.\n"
            "3. Return a valid JSON object matching EXACTLY the following structure (do not wrap in markdown or return extra text, just raw JSON):\n"
            "{\n"
            "  \"opportunities\": [\n"
            "    {\n"
            "      \"title\": \"Opportunity/Update Name\",\n"
            "      \"type\": \"Type of update or event\",\n"
            "      \"organizer\": \"Institution or site name\",\n"
            "      \"url\": \"Strictly valid URL link found in data\",\n"
            "      \"deadline\": \"YYYY-MM-DD or null\",\n"
            "      \"start_date\": \"YYYY-MM-DD or null\",\n"
            "      \"summary\": \"Concise single-sentence description\",\n"
            "      \"skills\": \"2-3 key highlights or technologies gained\",\n"
            "      \"cv_value\": \"Why this matters to a developer/professional (one short sentence)\",\n"
            "      \"first_step\": \"1 concrete action item for today\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )
    else:
        system_instruction = (
            "You are an autonomous career and event hunter agent. Your task is to extract highly relevant opportunities "
            "(free bootcamps, hackathons, certificate programs, CTFs) from the raw search results.\n\n"
            "RULES:\n"
            "1. PRIORITIZE FREE (or fully sponsored/scholarship-based) opportunities. Filter out paid commercial courses.\n"
            "2. For each opportunity, you MUST strictly extract/infer the application deadline and the program/event start date in YYYY-MM-DD format. If not mentioned and cannot be reasonably inferred, set to null.\n"
            "3. Return a valid JSON object matching EXACTLY the following structure (do not wrap in markdown or return extra text, just raw JSON):\n"
            "{\n"
            "  \"opportunities\": [\n"
            "    {\n"
            "      \"title\": \"Opportunity Name\",\n"
            "      \"type\": \"Bootcamp/Hackathon/CTF/Certificate\",\n"
            "      \"organizer\": \"Institution name\",\n"
            "      \"url\": \"Strictly valid URL link found in data\",\n"
            "      \"deadline\": \"YYYY-MM-DD or null\",\n"
            "      \"start_date\": \"YYYY-MM-DD or null\",\n"
            "      \"summary\": \"Concise single-sentence description\",\n"
            "      \"skills\": \"2-3 key technologies to learn\",\n"
            "      \"cv_value\": \"How to present this to tech recruiters (one short sentence)\",\n"
            "      \"first_step\": \"1 concrete preparatory task for today\"\n"
            "    }\n"
            "  ]\n"
            "}"
        )
    recent_sent_instruction = (
        f"\n\n⚠️ IMPORTANT - ALREADY SENT EVENTS:\n"
        f"The following events have already been sent recently. You MUST exclude them entirely from your report:\n"
        f"{recent_sent_text}\n"
    ) if recent_sent_text else ""
            
    prompt = f"Raw Crawled Data Payload:\n{raw_data_text}"
    if recent_sent_instruction:
        prompt = f"{recent_sent_instruction}\n\n{prompt}"
        
    try:
        raw_res = LLMClient.call_llm(provider, model, api_key, prompt, system_instruction, response_format_json=True)
        cleaned_res = LLMClient.clean_json_response(raw_res)
        data = json.loads(cleaned_res)
        return data.get("opportunities", [])
    except Exception as e:
        logging.error(f"LLM filtering JSON extraction failed: {e}")
        return []

def extract_sent_items_from_markdown(markdown_text: str) -> list:
    items = []
    blocks = markdown_text.split("🚀")
    for block in blocks[1:]:
        lines = block.split("\n")
        title_line = lines[0].strip()
        title = re.sub(r'\s*\(.*?\)\s*$', '', title_line).strip().strip('*').strip('[')
        url = ""
        for line in lines:
            if "🔗" in line:
                match = re.search(r'\[.*?\]\((https?://.*?)\)', line)
                if match:
                    url = match.group(1).strip()
        if title:
            items.append({"title": title, "url": url})
    return items

def setup_signal_handlers(bot_token: str, db: DatabaseManager):
    def handle_signal(signum, frame):
        global keep_running
        signame = signal.Signals(signum).name
        logging.info(f"System caught shutdown signal {signame}. Sending offline telemetry alerts...")
        
        with db_lock:
            with db.get_connection() as conn:
                users = conn.execute("SELECT chat_id FROM users").fetchall()
            
        for user in users:
            chat_id = user["chat_id"]
            msg = (
                f"⚠️ *picareeragent Agent Offline!* ⚠️\n\n"
                f"🛑 *Signal:* `{signame}`\n"
                f"🕒 *Shutdown:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                f"📡 *Status:* Offline"
            )
            TelegramBot.send_message(msg, bot_token, chat_id)
            
        keep_running = False
        sys.exit(0)
        
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    logging.info("Container OS signal handlers registered cleanly.")




if __name__ == "__main__":
    load_dotenv()
    
    # Configure logs Stream + optional persistent file logging handler
    log_handlers = [logging.StreamHandler(sys.stdout)]
    log_file = os.getenv("LOG_FILE_PATH", "data/app.log")
    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            log_handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except Exception as e:
            print(f"Failed to initialize persistent file logger: {e}")
            
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=log_handlers
    )
    
    logging.info("Initializing multi-user picareeragent edge service...")
    
    # Initialize SQLite database schema and handle automated json migrations
    db_path = "data/careeragent.db"
    db = DatabaseManager(db_path)
    
    # Load default settings from environment
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower().strip()
    LLM_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash").strip()
    LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
    
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    auth_ids_raw = os.getenv("AUTHORIZED_CHAT_IDS", "")
    AUTHORIZED_CHAT_IDS = [x.strip() for x in auth_ids_raw.split(",") if x.strip()]
    
    setup_signal_handlers(TELEGRAM_BOT_TOKEN, db)
    
    # Register bot commands menu at startup!
    set_bot_commands(TELEGRAM_BOT_TOKEN)
    
    # Start Telegram Polling in a concurrent background thread
    polling_thread = threading.Thread(
        target=telegram_polling_worker, 
        args=(TELEGRAM_BOT_TOKEN, db, AUTHORIZED_CHAT_IDS), 
        daemon=True
    )
    polling_thread.start()
    
    
    # [STARTUP ONLINE NOTIFICATION]
    # Send a beautiful bilingual online telemetry message to all authorized chats on boot
    notify_chats = list(AUTHORIZED_CHAT_IDS)
    primary_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if primary_chat_id and primary_chat_id not in notify_chats:
        notify_chats.append(primary_chat_id)
        
    for cid in notify_chats:
        if TELEGRAM_BOT_TOKEN:
            primary_lang = "en"
            try:
                with db_lock:
                    with db.get_connection() as conn:
                        row = conn.execute("SELECT language FROM users WHERE chat_id = ?", (cid,)).fetchone()
                        if row:
                            primary_lang = row["language"]
            except Exception:
                pass
                
            if primary_lang == "tr":
                startup_msg = (
                    "🚀 *CareerAgent Çevrimiçi!* 🚀\n\n"
                    "📡 *Durum:* Aktif & Taramada\n"
                    f"🕒 *Başlangıç Zamanı:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    "💻 *Platform:* Otonom Daemon Aktif\n\n"
                    "Crawler döngüleri ve e-posta tarayıcıları başarıyla başlatıldı."
                )
            elif primary_lang == "all":
                startup_msg = (
                    "🚀 *CareerAgent Online / Çevrimiçi!* 🚀\n\n"
                    "📡 *Status / Durum:* Online & Active / Aktif & Taramada\n"
                    f"🕒 *Start Time / Başlangıç:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    "Background crawler loops and email scanners initialized successfully. / Crawler döngüleri ve e-posta tarayıcıları başarıyla başlatıldı."
                )
            else:
                startup_msg = (
                    "🚀 *CareerAgent Online!* 🚀\n\n"
                    "📡 *Status:* Online & Active\n"
                    f"🕒 *Start Time:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`\n"
                    "💻 *Platform:* Autonomous Daemon Active\n\n"
                    "Background crawler loops and email scanners initialized successfully."
                )
            sent = TelegramBot.send_message(startup_msg, TELEGRAM_BOT_TOKEN, cid)
            if sent:
                logging.info(f"Startup online telemetry message delivered to chat {cid}")
            else:
                logging.warning(f"Failed to send startup online telemetry message to chat {cid}")
    
    logging.info("Multi-User daemon initialized. Starting main sweep cycles loop...")
    while keep_running:
        try:
            run_user_sweeps(db, FIRECRAWL_API_KEY, LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, TELEGRAM_BOT_TOKEN)
        except Exception as e:
            logging.error(f"Critical execution error in main loop cycle: {e}", exc_info=True)
            
        logging.info("Entering sleeping telemetry sweep state for 30 minutes...")
        for _ in range(180):
            if not keep_running:
                break
            time.sleep(10)

