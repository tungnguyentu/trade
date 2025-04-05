import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Configuration
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TESTNET = os.getenv('USE_TESTNET', 'True').lower() in ('true', '1', 't')

# Trading Parameters
SYMBOL = os.getenv('TRADING_SYMBOL', 'BTCUSDT')
LEVERAGE = int(os.getenv('LEVERAGE', '5'))
QUANTITY = float(os.getenv('QUANTITY', '0.001'))  # BTC amount for futures

# Risk Management
MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '0.01'))  # BTC
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '2.0'))  # 2%
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '4.0'))  # 4%

# Strategy Parameters
STRATEGY = os.getenv('STRATEGY', 'simple_ma_crossover')
SHORT_WINDOW = int(os.getenv('SHORT_WINDOW', '9'))
LONG_WINDOW = int(os.getenv('LONG_WINDOW', '21'))
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
RSI_OVERBOUGHT = int(os.getenv('RSI_OVERBOUGHT', '70'))
RSI_OVERSOLD = int(os.getenv('RSI_OVERSOLD', '30'))

# Backtesting Parameters
BACKTEST_DAYS = int(os.getenv('BACKTEST_DAYS', '30'))
BACKTEST_INITIAL_BALANCE = float(os.getenv('BACKTEST_INITIAL_BALANCE', '1000.0'))
BACKTEST_COMMISSION = float(os.getenv('BACKTEST_COMMISSION', '0.0004'))  # 0.04%

# Telegram Notifications
TELEGRAM_ENABLED = os.getenv('TELEGRAM_ENABLED', 'False').lower() in ('true', '1', 't')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')