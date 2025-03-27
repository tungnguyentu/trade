from binance.client import Client
from binance.exceptions import BinanceAPIException
import time
import os
from app.utils.logger import get_logger
from app.config.config import BINANCE_API_KEY, BINANCE_API_SECRET, TRADING_MODE

logger = get_logger()

class BinanceClient:
    """
    Singleton class to manage Binance API client
    """
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(BinanceClient, cls).__new__(cls)
            cls._instance._initialize_client()
        return cls._instance
    
    def _initialize_client(self):
        """Initialize the Binance client with API credentials"""
        try:
            # Check if API credentials are available
            if BINANCE_API_KEY and BINANCE_API_SECRET:
                self._client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
                logger.info("Binance client initialized with API credentials")
                
                # Set testnet for paper trading mode
                if TRADING_MODE == "paper":
                    self._client.API_URL = "https://testnet.binance.vision/api"
                    logger.info("Using Binance testnet API for paper trading")
            else:
                # Initialize in read-only mode for backtesting or if no credentials
                self._client = Client()
                logger.warning("Binance client initialized in read-only mode (no API credentials)")
                
        except BinanceAPIException as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initializing Binance client: {e}")
            raise
    
    def get_client(self):
        """Get the Binance client instance"""
        return self._client
    
    def get_historical_klines(self, symbol, interval, start_str, end_str=None):
        """
        Get historical klines (candlestick data) for a symbol
        
        Args:
            symbol (str): Trading pair symbol (e.g., 'BTCUSDT')
            interval (str): Kline interval (e.g., '1h', '15m', '1d')
            start_str (str): Start time in milliseconds or formatted string
            end_str (str, optional): End time in milliseconds or formatted string
            
        Returns:
            list: List of klines data
        """
        try:
            # For futures data, use the futures_klines method
            return self._client.futures_klines(
                symbol=symbol,
                interval=interval,
                startTime=start_str,
                endTime=end_str,
                limit=1000
            )
        except BinanceAPIException as e:
            logger.error(f"Error fetching historical klines: {e}")
            # Fallback to normal klines if futures API not available
            logger.info("Falling back to spot klines")
            return self._client.get_klines(
                symbol=symbol,
                interval=interval,
                startTime=start_str,
                endTime=end_str,
                limit=1000
            )
    
    def get_exchange_info(self):
        """Get Binance Futures exchange information"""
        try:
            return self._client.futures_exchange_info()
        except BinanceAPIException as e:
            logger.error(f"Error fetching exchange info: {e}")
            raise
    
    def get_account_info(self):
        """Get account information including balances and positions"""
        if TRADING_MODE == "backtest":
            # Return dummy account info for backtesting
            return {
                "totalWalletBalance": "10000.00000000",
                "totalUnrealizedProfit": "0.00000000",
                "totalMarginBalance": "10000.00000000",
                "availableBalance": "10000.00000000",
                "positions": []
            }
        
        try:
            return self._client.futures_account()
        except BinanceAPIException as e:
            logger.error(f"Error fetching account info: {e}")
            raise
    
    def get_symbol_info(self, symbol):
        """Get symbol information including trading rules"""
        try:
            exchange_info = self._client.futures_exchange_info()
            for symbol_info in exchange_info['symbols']:
                if symbol_info['symbol'] == symbol:
                    return symbol_info
            return None
        except BinanceAPIException as e:
            logger.error(f"Error fetching symbol info for {symbol}: {e}")
            raise
    
    def get_current_price(self, symbol):
        """Get current price for a symbol"""
        try:
            mark_price = self._client.futures_mark_price(symbol=symbol)
            return float(mark_price['markPrice'])
        except BinanceAPIException as e:
            logger.error(f"Error fetching current price for {symbol}: {e}")
            logger.info(f"Falling back to spot price")
            ticker = self._client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
    
    def set_leverage(self, symbol, leverage):
        """Set leverage for a symbol"""
        if TRADING_MODE == "backtest" or TRADING_MODE == "paper":
            logger.info(f"[{TRADING_MODE.upper()}] Setting leverage {leverage}x for {symbol}")
            return {"leverage": leverage, "symbol": symbol}
        
        try:
            return self._client.futures_change_leverage(
                symbol=symbol,
                leverage=leverage
            )
        except BinanceAPIException as e:
            logger.error(f"Error setting leverage for {symbol}: {e}")
            raise
    
    def get_funding_rate(self, symbol):
        """Get current funding rate for a symbol"""
        try:
            return self._client.futures_funding_rate(symbol=symbol)[0]
        except BinanceAPIException as e:
            logger.error(f"Error fetching funding rate for {symbol}: {e}")
            raise
    
    def get_open_orders(self, symbol=None):
        """Get open orders for a symbol or all symbols"""
        if TRADING_MODE == "backtest":
            return []
            
        try:
            return self._client.futures_get_open_orders(symbol=symbol)
        except BinanceAPIException as e:
            logger.error(f"Error fetching open orders: {e}")
            raise
    
    def cancel_order(self, symbol, order_id):
        """Cancel an order"""
        if TRADING_MODE == "backtest":
            logger.info(f"[BACKTEST] Simulated canceling order {order_id} for {symbol}")
            return {"orderId": order_id, "status": "CANCELED"}
            
        try:
            return self._client.futures_cancel_order(
                symbol=symbol,
                orderId=order_id
            )
        except BinanceAPIException as e:
            logger.error(f"Error canceling order {order_id} for {symbol}: {e}")
            raise 