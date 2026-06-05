# PiCareerAgent

An autonomous career assistant pipeline that crawls job boards, filters postings, and tracks application lifecycles.

## How it Works
The application runs as a persistent background service. It executes automated web crawls of targeted job boards using Firecrawl, monitors a designated IMAP mailbox for recruiter replies, filters and evaluates postings using LiteLLM, updates application statuses in a local SQLite database, and routes notifications and control commands via a Telegram bot interface.

## Tech Stack
- **Languages/Frameworks:** Python, Flask
- **Services/Libraries:** Firecrawl, LiteLLM, SQLite, Telegram Bot API
- **Infrastructure:** Docker, Docker Compose, Linux, Raspberry Pi OS

## Quick Start (Docker)
```bash
docker compose up -d --build
```

## Local Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/ibodeth/PiCareerAgent.git
   cd PiCareerAgent
   ```
2. Configure credentials in a `.env` file (copied from `.env.example`):
   ```text
   LLM_PROVIDER=gemini
   LLM_MODEL=gemini/gemini-1.5-flash
   LLM_API_KEY=your_key
   FIRECRAWL_API_KEY=your_key
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_CHAT_ID=your_chat_id
   ```
3. Set up a virtual environment and run the application:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```

## License
MIT
