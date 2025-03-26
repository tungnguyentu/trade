import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# API Configuration
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Trading Parameters
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', 0.01))  # 1% risk per trade by default
MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', 0.20))  # 20% max drawdown by default
BASE_ORDER_SIZE = float(100)  # Base order size in USDT
TRADING_MODE = os.getenv('TRADING_MODE', 'backtest')  # 'backtest', 'paper', 'live'

# Strategy Parameters
SCALPING_ENABLED = os.getenv('SCALPING_ENABLED', 'True').lower() == 'true'
SWING_TRADING_ENABLED = os.getenv('SWING_TRADING_ENABLED', 'True').lower() == 'true'

# Markets and Timeframes
TRADING_SYMBOLS = os.getenv('TRADING_SYMBOLS', 'BTCUSDT,ETHUSDT').split(',')
TIMEFRAMES = os.getenv('TIMEFRAMES', '1m,5m,15m,1h,4h').split(',')

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Backtesting Configuration
BACKTEST_START_DATE = os.getenv('BACKTEST_START_DATE', '2023-01-01')
BACKTEST_END_DATE = os.getenv('BACKTEST_END_DATE', '2023-12-31')

# Indicator Parameters
RSI_PERIOD = int(os.getenv('RSI_PERIOD', 14))
RSI_OVERBOUGHT = int(os.getenv('RSI_OVERBOUGHT', 70))
RSI_OVERSOLD = int(os.getenv('RSI_OVERSOLD', 30))

BOLLINGER_PERIOD = int(os.getenv('BOLLINGER_PERIOD', 20))
BOLLINGER_STD_DEV = float(os.getenv('BOLLINGER_STD_DEV', 2.0))

MACD_FAST = int(os.getenv('MACD_FAST', 12))
MACD_SLOW = int(os.getenv('MACD_SLOW', 26))
MACD_SIGNAL = int(os.getenv('MACD_SIGNAL', 9))

# Scalping Strategy Parameters
SCALPING_PROFIT_TARGET = float(os.getenv('SCALPING_PROFIT_TARGET', 0.005))  # 0.5%
SCALPING_STOP_LOSS = float(os.getenv('SCALPING_STOP_LOSS', 0.002))  # 0.2%

# Swing Trading Strategy Parameters
SWING_PROFIT_TARGET = float(os.getenv('SWING_PROFIT_TARGET', 0.03))  # 3%
SWING_STOP_LOSS = float(os.getenv('SWING_STOP_LOSS', 0.015))  # 1.5% 