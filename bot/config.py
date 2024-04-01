import os

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URI = os.getenv("DATABASE_URI", "sqlite:///data.db")
PAYMENT_PROVIDER_TOKEN = os.getenv("PAYMENT_PROVIDER_TOKEN")
DISCOURSE_URL = os.getenv("DISCOURSE_URL", "https://mirea.ninja")
DISCOURSE_API_KEY = os.getenv("DISCOURSE_API_KEY")
DEVELOPER_CHAT_ID = os.getenv("DEVELOPER_CHAT_ID")
