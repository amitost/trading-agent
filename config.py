import os

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

PORTFOLIO = ["AAPL", "MSFT", "NVDA", "GOOGL", "SPY", "QQQ"]
MAX_POSITION_SIZE = 0.10