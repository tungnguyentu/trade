from binance.client import Client
from binance.exceptions import BinanceAPIException
from app.config.config import BINANCE_API_KEY, BINANCE_API_SECRET, TRADING_MODE
from app.utils.logger import get_logger

logger = get_logger()

class BinanceClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BinanceClient, cls).__new__(cls)
            cls._instance._client = None
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._initialize_client()
            self._initialized = True
    
    def _initialize_client(self):
        try:
            if TRADING_MODE == 'live':
                self._client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
                logger.info("Connected to Binance live trading API")
            else:
                # For paper trading and backtesting, we use the API in test mode
                self._client = Client(BINANCE_API_KEY, BINANCE_API_SECRET, testnet=True)
                logger.info(f"Connected to Binance API in {TRADING_MODE} mode")
                
            # Test connection
            self._client.ping()
            server_time = self._client.get_server_time()
            logger.info(f"Binance server time: {server_time}")
            
        except BinanceAPIException as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            raise
    
    def get_client(self):
        return self._client
    
    def get_klines(self, symbol, interval, start_str=None, end_str=None, limit=500):
        """
        Get historical klines (candlestick data) for a symbol
        
        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT')
            interval (str): Kline interval (e.g., '1m', '5m', '1h')
            start_str (str, optional): Start time in ISO format
            end_str (str, optional): End time in ISO format
            limit (int, optional): Maximum number of klines to fetch
            
        Returns:
            list: List of klines data
        """
        try:
            klines = self._client.get_historical_klines(
                symbol=symbol,
                interval=interval,
                start_str=start_str,
                end_str=end_str,
                limit=limit
            )
            return klines
        except BinanceAPIException as e:
            logger.error(f"Failed to fetch klines for {symbol} {interval}: {e}")
            return []
    
    def get_symbol_info(self, symbol):
        """Get symbol information"""
        try:
            return self._client.get_symbol_info(symbol)
        except BinanceAPIException as e:
            logger.error(f"Failed to get symbol info for {symbol}: {e}")
            return None
    
    def get_account_balance(self, asset='USDT'):
        """Get account balance for a specific asset in Binance Futures"""
        try:
            balances = self._client.futures_account_balance()
            
            for balance in balances:
                if balance['asset'] == asset:
                    return {
                        'free': float(balance['availableBalance']),
                        'locked': float(balance['balance']) - float(balance['availableBalance']),
                        'total': float(balance['balance'])
                    }
            
            logger.warning(f"Asset {asset} not found in account balances")
            return {'free': 0.0, 'locked': 0.0, 'total': 0.0}
        except BinanceAPIException as e:
            logger.error(f"Failed to fetch account balance: {e}")
            return {'free': 0.0, 'locked': 0.0, 'total': 0.0}
        except Exception as e:
            logger.error(f"Unexpected error fetching account balance: {e}")
            return {'free': 0.0, 'locked': 0.0, 'total': 0.0} 