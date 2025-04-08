from binance.client import Client
from binance.exceptions import BinanceAPIException
import logging
import sys
from config.config import API_KEY, API_SECRET, TESTNET, SYMBOL, LEVERAGE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/trading.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("binance_client")

class BinanceFuturesClient:
    def __init__(self, testnet=None):
        try:
            # Use the provided testnet parameter if given, otherwise use config
            use_testnet = TESTNET if testnet is None else testnet
            
            self.client = Client(API_KEY, API_SECRET, testnet=use_testnet)
            logger.info(f"Connected to Binance {'Testnet' if use_testnet else 'Production'}")
            
            # Set up futures
            self.setup_futures()
        except BinanceAPIException as e:
            logger.error(f"Failed to initialize Binance client: {e}")
            raise

    def setup_futures(self):
        """Set up futures trading parameters"""
        try:
            # Change margin type to ISOLATED
            self.client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
        except BinanceAPIException as e:
            if e.code == -4046:  # Already in the desired margin mode
                pass
            else:
                logger.error(f"Error setting margin type: {e}")
                raise
                
        try:
            # Set leverage
            self.client.futures_change_leverage(symbol=SYMBOL, leverage=LEVERAGE)
            logger.info(f"Leverage set to {LEVERAGE}x for {SYMBOL}")
        except BinanceAPIException as e:
            logger.error(f"Error setting leverage: {e}")
            raise

    def get_account_balance(self):
        """Get futures account balance"""
        try:
            futures_account = self.client.futures_account()
            for asset in futures_account['assets']:
                if asset['asset'] == 'USDT':
                    return {
                        'wallet_balance': float(asset['walletBalance']),
                        'unrealized_pnl': float(asset['unrealizedProfit']),
                        'margin_balance': float(asset['marginBalance']),
                        'available_balance': float(asset['availableBalance'])
                    }
            return None
        except BinanceAPIException as e:
            logger.error(f"Error getting account balance: {e}")
            return None

    def get_market_price(self, symbol=SYMBOL):
        """Get current market price for a symbol"""
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logger.error(f"Error getting market price: {e}")
            return None

    def get_historical_klines(self, symbol=SYMBOL, interval='1h', limit=100):
        """Get historical klines/candlestick data"""
        try:
            klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            return klines
        except BinanceAPIException as e:
            logger.error(f"Error getting historical klines: {e}")
            return None

    def place_market_order(self, side, quantity, symbol=SYMBOL, reduce_only=False):
        """Place a market order"""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,  # 'BUY' or 'SELL'
                type='MARKET',
                quantity=quantity,
                reduceOnly=reduce_only
            )
            logger.info(f"Placed {side} market order for {quantity} {symbol}: {order['orderId']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Error placing market order: {e}")
            return None

    def place_limit_order(self, side, quantity, price, reduce_only=False):
        """Place a limit order"""
        try:
            logger.info(f"Placing {side} limit order for {quantity} {self.symbol} at {price}")
            
            order = self.client.futures_create_order(
                symbol=self.symbol,
                side=side,
                type='LIMIT',
                timeInForce='GTC',  # Good Till Cancelled
                quantity=quantity,
                price=price,
                reduceOnly=reduce_only
            )
            
            logger.info(f"Placed {side} limit order for {quantity} {self.symbol}: {order['orderId']}")
            return order
        except Exception as e:
            logger.error(f"Error placing limit order: {e}")
            return None

    def place_stop_loss(self, side, quantity, stop_price, symbol=SYMBOL):
        """Place a stop loss order"""
        try:
            opposite_side = 'BUY' if side == 'SELL' else 'SELL'
            order = self.client.futures_create_order(
                symbol=symbol,
                side=opposite_side,
                type='STOP_MARKET',
                timeInForce='GTC',
                quantity=quantity,
                stopPrice=stop_price,
                reduceOnly=True
            )
            logger.info(f"Placed stop loss at {stop_price} for {quantity} {symbol}: {order['orderId']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Error placing stop loss: {e}")
            return None

    def place_take_profit(self, side, quantity, take_profit_price, symbol=SYMBOL):
        """Place a take profit order"""
        try:
            opposite_side = 'BUY' if side == 'SELL' else 'SELL'
            order = self.client.futures_create_order(
                symbol=symbol,
                side=opposite_side,
                type='TAKE_PROFIT_MARKET',
                timeInForce='GTC',
                quantity=quantity,
                stopPrice=take_profit_price,
                reduceOnly=True
            )
            logger.info(f"Placed take profit at {take_profit_price} for {quantity} {symbol}: {order['orderId']}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Error placing take profit: {e}")
            return None

    def get_open_positions(self, symbol=SYMBOL):
        """Get open positions"""
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            return positions
        except BinanceAPIException as e:
            logger.error(f"Error getting open positions: {e}")
            return None

    def cancel_all_orders(self, symbol=SYMBOL):
        """Cancel all open orders for a symbol"""
        try:
            result = self.client.futures_cancel_all_open_orders(symbol=symbol)
            logger.info(f"Cancelled all orders for {symbol}")
            return result
        except BinanceAPIException as e:
            logger.error(f"Error cancelling orders: {e}")
            return None