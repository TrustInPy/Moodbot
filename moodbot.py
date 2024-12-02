import asyncio
import hashlib
import logging
import os
import re
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from hazm import Normalizer
from matplotlib import pyplot as plt
from telethon import TelegramClient, events, Button
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import emoji

# Logging setup
logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# Telegram API credentials
api_id = "api_id_here"
api_hash = "api_hash_here"
bot_token = "bot_token_here"
admin_group_id = int('admin_group_id_here')  # Admin group for feedback
group_id = int('group_id_here')  # Group where the bot is active
proxy = ("socks5", "127.0.0.1", 1234) #change these if needed

# Path to local model
model_path = "local_model"

# SQLite database path
db_path = "sentiment_data.db"

# Initialize Hazm Normalizer
normalizer = Normalizer()

# Initialize the Telegram bot client
client = TelegramClient("mood_analyzer", api_id, api_hash, proxy=proxy).start(
    bot_token=bot_token
)

# Initialize model
if not os.path.exists(model_path):
    logging.info("Downloading the model...")
    sentiment_pipeline = pipeline(
        "sentiment-analysis",
        model="HooshvareLab/bert-fa-base-uncased-sentiment-snappfood",
    )
    sentiment_pipeline.save_pretrained(model_path)
    logging.info("Model downloaded and saved locally.")

tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForSequenceClassification.from_pretrained(model_path)
sentiment_pipeline = pipeline("sentiment-analysis", model=model, tokenizer=tokenizer)

# Initialize daily message data
messages_data = defaultdict(list)


# Initialize SQLite Database
def initialize_db():
    """
    Create the SQLite database and tables if they do not exist.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sentiment_data (
            id TEXT PRIMARY KEY,
            message_text TEXT,
            sentiment TEXT,
            score REAL,
            label TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    conn.commit()
    conn.close()
    logging.info("Database initialized.")


initialize_db()


def save_message_data(message_text, sentiment, score, label=None):
    """
    Save message data with a unique identifier in the database.
    """
    unique_id = str(uuid.uuid4())
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO sentiment_data (id, message_text, sentiment, score, label)
        VALUES (?, ?, ?, ?, ?)
    """,
        (unique_id, message_text, sentiment, score, label),
    )

    conn.commit()
    conn.close()
    logging.info(f"Message saved: ID={unique_id}, Sentiment={sentiment}, Score={score}")
    return unique_id


def update_feedback_in_dataset(unique_id, label):
    """
    Update the human feedback for a specific entry in the SQLite database.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE sentiment_data
        SET label = ?
        WHERE id = ?
    """,
        (label, unique_id),
    )

    conn.commit()
    conn.close()
    logging.info(f"Feedback updated: ID={unique_id}, Label={label}")


def preprocess_text(text):
    """
    Preprocess and normalize Persian text.
    """
    text = re.sub(r"http\S+|www\.\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"#\w+", "", text)
    text = emoji.replace_emoji(text, replace="")
    text = re.sub(r"[a-zA-Z]", "", text)
    text = re.sub(r"[^\u0600-\u06FF\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = normalizer.normalize(text)
    text = re.sub(r"\d+", "", text)
    return text


def analyze_sentiment(text):
    """
    Analyze the sentiment of the given text.
    """
    try:
        result = sentiment_pipeline(text)
        label = result[0]["label"]
        score = result[0]["score"]
        if label == "HAPPY":
            return "POSITIVE", score
        elif label == "SAD":
            return "NEGATIVE", score
        else:
            return "NEUTRAL", score
    except Exception as e:
        logging.error(f"Sentiment analysis error: {e}")
        return "ERROR", 0.0


def generate_mood_chart(daily_data, save_path):
    """
    Generate a mood summary chart.
    """
    dates = sorted(daily_data.keys())
    positive, neutral, negative = [], [], []

    for date in dates:
        sentiments = daily_data[date]
        total = len(sentiments)
        pos_count = sum(1 for s in sentiments if s == "POSITIVE")
        neg_count = sum(1 for s in sentiments if s == "NEGATIVE")
        neu_count = total - pos_count - neg_count

        positive.append(pos_count / total * 100)
        neutral.append(neu_count / total * 100)
        negative.append(neg_count / total * 100)

    plt.figure(figsize=(10, 6))
    plt.plot(dates, positive, label="Positive", marker="o")
    plt.plot(dates, neutral, label="Neutral", marker="o")
    plt.plot(dates, negative, label="Negative", marker="o")
    plt.xlabel("Date")
    plt.ylabel("Percentage")
    plt.title("Mood Trends Over Time")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()
    logging.info(f"Chart saved to {save_path}")


@client.on(events.NewMessage())
async def mood_analyzer(event):
    """
    Analyze and save sentiment of new messages.
    """
    if event.is_group and event.raw_text:
        message_text = preprocess_text(event.raw_text)
        sentiment, score = analyze_sentiment(message_text)
        unique_id = save_message_data(message_text, sentiment, score)

        today = datetime.now().strftime("%Y-%m-%d")
        messages_data[today].append(sentiment)

        if sentiment == "NEGATIVE" and score > 0.6:
            negativity_percentage = score * 100
            await client.send_message(
                admin_group_id,
                f"⚠️ Negative message detected ({negativity_percentage:.2f}% negative):\n\n"
                f"{message_text}\n\n"
                f"From: {event.chat.title if event.chat else 'Unknown'}",
                buttons=[
                    Button.inline("Negative", data=f"label_negative:{unique_id}"),
                    Button.inline(
                        "Not Negative", data=f"label_not_negative:{unique_id}"
                    ),
                ],
            )


@client.on(events.CallbackQuery)
async def handle_feedback(event):
    """
    Handle admin feedback on detected messages.
    """
    data = event.data.decode("utf-8")
    label = "negative" if "label_negative" in data else "not_negative"
    unique_id = data.split(":", 1)[1]

    update_feedback_in_dataset(unique_id, label)
    await event.answer("Feedback recorded! Thank you.")
    msg = await event.get_message()
    await msg.delete()


async def daily_mood_summary():
    """
    Generate and send a daily mood summary.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    summary_file = "mood_summary.png"

    if yesterday in messages_data and messages_data[yesterday]:
        generate_mood_chart(messages_data, summary_file)

        pos_count = sum(1 for s in messages_data[yesterday] if s == "POSITIVE")
        neg_count = sum(1 for s in messages_data[yesterday] if s == "NEGATIVE")
        neu_count = len(messages_data[yesterday]) - pos_count - neg_count

        await client.send_message(
            admin_group_id,
            f"📊 Mood Summary for {yesterday}:\n"
            f"Positive: {pos_count}\nNeutral: {neu_count}\nNegative: {neg_count}",
            file=summary_file,
        )
    else:
        await client.send_message(admin_group_id, f"No data for {yesterday}.")


async def schedule_daily_summary():
    """
    Schedule daily mood summaries.
    """
    while True:
        now = datetime.now()
        next_run = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await daily_mood_summary()
        await asyncio.sleep((next_run - datetime.now()).total_seconds())


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(schedule_daily_summary())
        client.run_until_disconnected()
