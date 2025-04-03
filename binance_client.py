import logging
import time
from binance.client import Client
from binance.exceptions import BinanceAPIException, BinanceRequestException
import pandas as pd
import config

logger = logging.getLogger(__name__)

class BinanceClient:
    def __init__(self):
        self.client = Client(config.API_KEY, config.API_SECRET)
        self.test_mode = config.TEST_MODE
        logger.info(f"Binance client initialized. Test mode: {self.test_mode}")
        
    def get_account_balance(self):
        """Get futures account balance for USDT"""
        try:
            account_info = self.client.futures_account_balance()
            for balance in account_info:
                if balance['asset'] == 'USDT':
                    return float(balance['balance'])
            return 0.0
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error getting account balance: {e}")
            return 0.0
            
    def get_current_price(self, symbol=None):
        """Get current price for a symbol"""
        if symbol is None:
            symbol = config.SYMBOL
        try:
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    def get_historical_klines(self, symbol=None, interval=None, start_str=None, limit=500):
        """
        Get historical klines (candlestick data)
        
        :param symbol: Trading symbol
        :param interval: Kline interval (e.g. '1h', '15m', '1d')
        :param start_str: Start time in format "1 day ago UTC", "1 hour ago UTC", etc.
        :param limit: Number of klines to return
        :return: Pandas DataFrame with kline data
        """
        if symbol is None:
            symbol = config.SYMBOL
        if interval is None:
            interval = config.TIMEFRAME
            
        try:
            klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit, startTime=start_str)
            
            df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 
                                              'close_time', 'quote_asset_volume', 'number_of_trades',
                                              'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
            
            # Convert timestamp to datetime and set as index
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Convert string values to float
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_columns] = df[numeric_columns].astype(float)
            
            return df
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error getting historical klines for {symbol}: {e}")
            return pd.DataFrame()
    
    def place_market_order(self, symbol, side, quantity):
        """
        Place a market order
        
        :param symbol: Trading symbol
        :param side: 'BUY' or 'SELL'
        :param quantity: Order quantity
        :return: Order response or None if in test mode
        """
        try:
            if self.test_mode:
                logger.info(f"TEST MODE: Would place {side} market order for {quantity} {symbol}")
                # Simulate order response
                current_price = self.get_current_price(symbol)
                return {
                    'symbol': symbol,
                    'side': side,
                    'type': 'MARKET',
                    'quantity': quantity,
                    'price': current_price,
                    'status': 'FILLED',
                    'time': int(time.time() * 1000)
                }
            else:
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='MARKET',
                    quantity=quantity
                )
                logger.info(f"Placed {side} market order for {quantity} {symbol}: {order}")
                return order
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error placing {side} market order for {symbol}: {e}")
            return None
    
    def place_limit_order(self, symbol, side, quantity, price):
        """
        Place a limit order
        
        :param symbol: Trading symbol
        :param side: 'BUY' or 'SELL'
        :param quantity: Order quantity
        :param price: Limit price
        :return: Order response or None if in test mode
        """
        try:
            if self.test_mode:
                logger.info(f"TEST MODE: Would place {side} limit order for {quantity} {symbol} at {price}")
                # Simulate order response
                return {
                    'symbol': symbol,
                    'side': side,
                    'type': 'LIMIT',
                    'timeInForce': 'GTC',
                    'quantity': quantity,
                    'price': price,
                    'status': 'NEW',
                    'time': int(time.time() * 1000)
                }
            else:
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=quantity,
                    price=price
                )
                logger.info(f"Placed {side} limit order for {quantity} {symbol} at {price}: {order}")
                return order
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error placing {side} limit order for {symbol}: {e}")
            return None
    
    def place_stop_loss_order(self, symbol, side, quantity, stop_price):
        """Place a stop market order for stop loss"""
        opposite_side = 'SELL' if side == 'BUY' else 'BUY'
        try:
            if self.test_mode:
                logger.info(f"TEST MODE: Would place {opposite_side} stop loss at {stop_price}")
                return {
                    'symbol': symbol,
                    'side': opposite_side,
                    'type': 'STOP_MARKET',
                    'quantity': quantity,
                    'stopPrice': stop_price,
                    'status': 'NEW',
                    'time': int(time.time() * 1000)
                }
            else:
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type='STOP_MARKET',
                    quantity=quantity,
                    stopPrice=stop_price
                )
                logger.info(f"Placed stop loss order at {stop_price}: {order}")
                return order
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error placing stop loss order: {e}")
            return None
    
    def place_take_profit_order(self, symbol, side, quantity, stop_price):
        """Place a take profit market order"""
        opposite_side = 'SELL' if side == 'BUY' else 'BUY'
        try:
            if self.test_mode:
                logger.info(f"TEST MODE: Would place {opposite_side} take profit at {stop_price}")
                return {
                    'symbol': symbol,
                    'side': opposite_side,
                    'type': 'TAKE_PROFIT_MARKET',
                    'quantity': quantity,
                    'stopPrice': stop_price,
                    'status': 'NEW',
                    'time': int(time.time() * 1000)
                }
            else:
                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=opposite_side,
                    type='TAKE_PROFIT_MARKET',
                    quantity=quantity,
                    stopPrice=stop_price
                )
                logger.info(f"Placed take profit order at {stop_price}: {order}")
                return order
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error placing take profit order: {e}")
            return None
    
    def get_open_positions(self, symbol=None):
        """Get current open positions"""
        if symbol is None:
            symbol = config.SYMBOL
            
        try:
            positions = self.client.futures_position_information()
            
            if symbol:
                for position in positions:
                    if position['symbol'] == symbol:
                        amount = float(position['positionAmt'])
                        if amount != 0:
                            return {
                                'symbol': position['symbol'],
                                'amount': amount,
                                'entry_price': float(position['entryPrice']),
                                'unrealized_profit': float(position['unRealizedProfit'])
                            }
                return None
            
            # Return all non-zero positions
            active_positions = []
            for position in positions:
                amount = float(position['positionAmt'])
                if amount != 0:
                    active_positions.append({
                        'symbol': position['symbol'],
                        'amount': amount,
                        'entry_price': float(position['entryPrice']),
                        'unrealized_profit': float(position['unRealizedProfit'])
                    })
            
            return active_positions
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error getting open positions: {e}")
            return None
    
    def cancel_all_orders(self, symbol=None):
        """Cancel all open orders for a symbol"""
        if symbol is None:
            symbol = config.SYMBOL
            
        try:
            if self.test_mode:
                logger.info(f"TEST MODE: Would cancel all orders for {symbol}")
                return True
            else:
                result = self.client.futures_cancel_all_open_orders(symbol=symbol)
                logger.info(f"Cancelled all orders for {symbol}: {result}")
                return True
        except (BinanceAPIException, BinanceRequestException) as e:
            logger.error(f"Error cancelling orders for {symbol}: {e}")
            return False 