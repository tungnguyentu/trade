import os
from dotenv import load_dotenv


load_dotenv()


API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TESTNET = os.getenv('USE_TESTNET', 'True').lower() in ('true', '1', 't')

SYMBOL = os.getenv('TRADING_SYMBOL', 'BTCUSDT')
LEVERAGE = int(os.getenv('LEVERAGE', '5'))
QUANTITY = float(os.getenv('QUANTITY', '0.001'))

MAX_POSITION_SIZE = float(os.getenv('MAX_POSITION_SIZE', '0.01')) 
STOP_LOSS_PERCENT = float(os.getenv('STOP_LOSS_PERCENT', '2.0'))
TAKE_PROFIT_PERCENT = float(os.getenv('TAKE_PROFIT_PERCENT', '4.0')) 

STRATEGY = os.getenv('STRATEGY', 'simple_ma_crossover')
SHORT_WINDOW = int(os.getenv('SHORT_WINDOW', '9'))
LONG_WINDOW = int(os.getenv('LONG_WINDOW', '21'))
RSI_PERIOD = int(os.getenv('RSI_PERIOD', '14'))
RSI_OVERBOUGHT = int(os.getenv('RSI_OVERBOUGHT', '70'))
RSI_OVERSOLD = int(os.getenv('RSI_OVERSOLD', '30'))

BACKTEST_DAYS = int(os.getenv('BACKTEST_DAYS', '30'))
BACKTEST_INITIAL_BALANCE = float(os.getenv('BACKTEST_INITIAL_BALANCE', '1000.0'))
BACKTEST_COMMISSION = float(os.getenv('BACKTEST_COMMISSION', '0.0004'))