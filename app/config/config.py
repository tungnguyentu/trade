import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Binance API Credentials
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')

# Telegram Bot Settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Trading Parameters
TRADING_MODE = os.getenv('TRADING_MODE', 'backtest').lower()  # backtest, paper, live
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.01'))  # 1% of account per trade
MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', '0.20'))  # 20% max drawdown
BASE_ORDER_SIZE = float(os.getenv('BASE_ORDER_SIZE', '100'))  # Base order size in USDT

# Strategy Parameters
SCALPING_ENABLED = os.getenv('SCALPING_ENABLED', 'True').lower() == 'true'
SWING_TRADING_ENABLED = os.getenv('SWING_TRADING_ENABLED', 'True').lower() == 'true'

# Symbols and Timeframes
TRADING_SYMBOLS = os.getenv('TRADING_SYMBOLS', 'BTCUSDT,ETHUSDT').split(',')
TIMEFRAMES = os.getenv('TIMEFRAMES', '1m,5m,15m,1h,4h').split(',')

# Backtesting Parameters
INITIAL_BALANCE = float(os.getenv('INITIAL_BALANCE', '10000'))
BACKTEST_START_DATE = os.getenv('BACKTEST_START_DATE', '2023-01-01')
BACKTEST_END_DATE = os.getenv('BACKTEST_END_DATE', '')  # Empty means current date

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
SAVE_TRADE_HISTORY = os.getenv('SAVE_TRADE_HISTORY', 'True').lower() == 'true'

# Futures-specific Parameters
DEFAULT_LEVERAGE = int(os.getenv('DEFAULT_LEVERAGE', '5'))
MARGIN_TYPE = os.getenv('MARGIN_TYPE', 'ISOLATED')  # ISOLATED or CROSSED

# Advanced Order Settings
USE_TRAILING_STOP = os.getenv('USE_TRAILING_STOP', 'False').lower() == 'true'
TRAILING_STOP_CALLBACK = float(os.getenv('TRAILING_STOP_CALLBACK', '0.8'))  # 0.8%
TRADING_INTERVAL = int(os.getenv('TRADING_INTERVAL', '5'))  # Minutes

# Technical Indicator Parameters
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
BOLLINGER_PERIOD = int(os.getenv('BOLLINGER_PERIOD', '20'))
BOLLINGER_STD_DEV = float(os.getenv('BOLLINGER_STD_DEV', '2.0'))
EMA_SHORT = int(os.getenv('EMA_SHORT', '9'))
EMA_LONG = int(os.getenv('EMA_LONG', '21'))
MACD_FAST = int(os.getenv('MACD_FAST', '12'))
MACD_SLOW = int(os.getenv('MACD_SLOW', '26'))
MACD_SIGNAL = int(os.getenv('MACD_SIGNAL', '9'))
ATR_PERIOD = int(os.getenv('ATR_PERIOD', '14'))

# Risk Management Parameters
STOP_LOSS_ATR_MULTIPLIER = float(os.getenv('STOP_LOSS_ATR_MULTIPLIER', '2.0'))
TAKE_PROFIT_RISK_REWARD = float(os.getenv('TAKE_PROFIT_RISK_REWARD', '2.0'))

# Strategy-specific Parameters
# Scalping Strategy
SCALPING_PROFIT_TARGET = float(os.getenv('SCALPING_PROFIT_TARGET', '0.005'))  # 0.5%
SCALPING_STOP_LOSS = float(os.getenv('SCALPING_STOP_LOSS', '0.002'))  # 0.2%
SCALPING_RSI_OVERBOUGHT = int(os.getenv('SCALPING_RSI_OVERBOUGHT', '70'))
SCALPING_RSI_OVERSOLD = int(os.getenv('SCALPING_RSI_OVERSOLD', '30'))

# Swing Trading Strategy
SWING_MIN_HOLDING_PERIOD = int(os.getenv('SWING_MIN_HOLDING_PERIOD', '4'))  # Hours
SWING_MAX_HOLDING_PERIOD = int(os.getenv('SWING_MAX_HOLDING_PERIOD', '72'))  # Hours
SWING_PROFIT_TARGET = float(os.getenv('SWING_PROFIT_TARGET', '0.02'))  # 2.0%
SWING_STOP_LOSS = float(os.getenv('SWING_STOP_LOSS', '0.01'))  # 1.0% 