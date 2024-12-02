# Telegram Sentiment Analysis Bot

This is a Telegram bot designed to analyze the sentiment of group messages and provide daily mood summaries. It uses a Persian BERT model for sentiment analysis, stores data in a SQLite database, and supports admin feedback for continuous improvement.

---

## Features

- **Sentiment Analysis**: Classifies messages as `POSITIVE`or `NEGATIVE` using a BERT-based model.
- **Daily Summaries**: Sends a daily mood trend summary, including a chart visualization, to the admin group.
- **Admin Feedback**: Allows admins to provide feedback on flagged messages.
- **Scalable Storage**: Uses SQLite for efficient and structured data storage.
- **Logging**: Logs bot activity for debugging and monitoring.

---

## Setup

### Prerequisites
1. Python 3.10+
2. Telegram Bot Token
3. Required Python packages (see `requirements.txt`)

### Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/your-username/telegram-sentiment-bot.git
   cd telegram-sentiment-bot

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install dependencies:
   ```bash
   pip install -r requirements.txt

4. Set up your .env file for sensitive configurations (optional):
   ```bash
   TELEGRAM_API_ID=<your_api_id>
   TELEGRAM_API_HASH=<your_api_hash>
   BOT_TOKEN=<your_bot_token>

