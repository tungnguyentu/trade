import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Binance API configuration
API_KEY = os.environ.get('BINANCE_API_KEY')
API_SECRET = os.environ.get('BINANCE_API_SECRET')

# Telegram settings
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Trading settings
SYMBOL = os.environ.get('SYMBOL', 'BTCUSDT')
TRADE_SIZE = float(os.environ.get('TRADE_SIZE', 0.001))
TEST_MODE = os.environ.get('TEST_MODE', 'True').lower() == 'true'

# Strategy parameters
EMA_FAST = int(os.environ.get('EMA_FAST', 12))
EMA_SLOW = int(os.environ.get('EMA_SLOW', 26))
RSI_PERIOD = int(os.environ.get('RSI_PERIOD', 14))
RSI_OVERSOLD = int(os.environ.get('RSI_OVERSOLD', 30))
RSI_OVERBOUGHT = int(os.environ.get('RSI_OVERBOUGHT', 70))

# Risk management
STOP_LOSS_PERCENT = float(os.environ.get('STOP_LOSS_PERCENT', 2))
TAKE_PROFIT_PERCENT = float(os.environ.get('TAKE_PROFIT_PERCENT', 4))

# Timeframe for analysis
TIMEFRAME = '1h'

# Logging settings
LOG_DIR = 'logs'
DATA_DIR = 'data' 