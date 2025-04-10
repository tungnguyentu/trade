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
            # Check for and repair negative margin first
            self.repair_negative_margin(SYMBOL)
            
            # Change margin type to ISOLATED
            try:
                self.client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
            except BinanceAPIException as e:
                if e.code == -4046:  # Already in the desired margin mode
                    pass
                elif e.code == -4051:  # Isolated balance insufficient
                    logger.warning(f"Isolated balance insufficient for {SYMBOL}. Attempting to repair.")
                    self.repair_negative_margin(SYMBOL)
                    # Try again after repair
                    try:
                        self.client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
                    except Exception as inner_e:
                        logger.warning(f"Still unable to set isolated margin: {inner_e}")
                else:
                    logger.error(f"Error setting margin type: {e}")
                
            # Set leverage using our more resilient method
            self.set_leverage(SYMBOL, LEVERAGE)
        except Exception as e:
            logger.error(f"Error in setup_futures: {e}")
            # Continue anyway - we'll try to work with default settings

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

    def place_limit_order(self, symbol, side, quantity, price, reduce_only=False):
        """Place a limit order"""
        try:
            logger.info(f"Placing {side} limit order for {quantity} {symbol} at {price}")
            
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type='LIMIT',
                timeInForce='GTC',  # Good Till Cancelled
                quantity=quantity,
                price=price,
                reduceOnly=reduce_only
            )
            
            logger.info(f"Placed {side} limit order for {quantity} {symbol}: {order['orderId']}")
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

    def get_exchange_info(self, symbol):
        """Get exchange information for a specific symbol"""
        try:
            exchange_info = self.client.futures_exchange_info()
            
            # Find the symbol in the exchange info
            for sym_info in exchange_info['symbols']:
                if sym_info['symbol'] == symbol:
                    return sym_info
                    
            logger.warning(f"Symbol {symbol} not found in exchange info")
            return None
        except Exception as e:
            logger.error(f"Error getting exchange info: {e}")
            return None

    def get_leverage(self, symbol):
        """Get current leverage for a symbol"""
        try:
            leverage_info = self.client.futures_leverage_bracket(symbol=symbol)
            if leverage_info and isinstance(leverage_info, list) and len(leverage_info) > 0:
                # The API returns a list of brackets, we want the current leverage
                current_leverage = leverage_info[0].get('initialLeverage', 10)
                return current_leverage
            
            # If we can't get the leverage from brackets, try to get position info
            positions = self.get_open_positions(symbol)
            if positions:
                for position in positions:
                    if position['symbol'] == symbol:
                        return float(position.get('leverage', 10))
            
            return 10  # Default to 10x if we can't determine
        except Exception as e:
            logger.error(f"Error getting leverage: {e}")
            return None

    def set_leverage(self, symbol, leverage=20):
        """Set leverage for a symbol"""
        try:
            result = self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            logger.info(f"Leverage set to {leverage}x for {symbol}")
            return leverage
        except Exception as e:
            logger.warning(f"Error setting leverage to {leverage}x for {symbol}: {e}")
            logger.info(f"Continuing with default leverage. This may affect position sizing.")
            
            # Try to get current leverage instead
            try:
                current_leverage = self.get_leverage(symbol)
                if current_leverage:
                    logger.info(f"Using existing leverage: {current_leverage}x for {symbol}")
                    return current_leverage
                else:
                    # If we can't get current leverage, assume a conservative value
                    logger.info(f"Using default leverage of 5x for {symbol}")
                    return 5
            except:
                # If all else fails, return a conservative default
                return 5
                
    def repair_negative_margin(self, symbol):
        """Attempt to repair negative isolated margin by transferring funds"""
        try:
            # Get position information to check isolated margin
            positions = self.get_open_positions(symbol)
            negative_margin = 0
            
            for position in positions:
                if position['symbol'] == symbol:
                    isolated_margin = float(position.get('isolatedMargin', 0))
                    isolated_wallet = float(position.get('isolatedWallet', 0))
                    
                    if isolated_margin < 0 or isolated_wallet < 0:
                        # Calculate how much to transfer (negative value plus buffer)
                        negative_margin = abs(min(isolated_margin, isolated_wallet))
                        transfer_amount = negative_margin + 10  # Add $10 buffer
                        
                        logger.info(f"Attempting to repair negative margin of ${negative_margin:.2f} by transferring ${transfer_amount:.2f}")
                        
                        # Transfer from spot to futures
                        try:
                            # First try to transfer from spot to futures wallet
                            self.client.futures_account_transfer(
                                asset='USDT',
                                amount=transfer_amount,
                                type=1  # 1: Spot to USDⓈ-M Futures
                            )
                            logger.info(f"Transferred ${transfer_amount:.2f} from spot to futures wallet")
                        except Exception as e:
                            logger.warning(f"Error transferring from spot to futures: {e}")
                            
                        # Then try to adjust isolated margin
                        try:
                            # Add margin to the position
                            self.client.futures_change_position_margin(
                                symbol=symbol,
                                amount=transfer_amount,
                                type=1  # 1: Add margin
                            )
                            logger.info(f"Added ${transfer_amount:.2f} margin to {symbol} position")
                            return True
                        except Exception as e:
                            logger.error(f"Error adding margin to position: {e}")
                            
                        # If direct margin adjustment fails, try to close and reopen position
                        try:
                            # Cancel all open orders first
                            self.cancel_all_orders(symbol)
                            
                            # Try to switch to cross margin temporarily
                            try:
                                self.client.futures_change_margin_type(symbol=symbol, marginType='CROSSED')
                                logger.info(f"Switched to CROSSED margin for {symbol}")
                                
                                # Switch back to isolated with more margin
                                self.client.futures_change_margin_type(symbol=symbol, marginType='ISOLATED')
                                logger.info(f"Switched back to ISOLATED margin for {symbol}")
                                return True
                            except Exception as e:
                                logger.error(f"Error switching margin type: {e}")
                        except Exception as e:
                            logger.error(f"Error closing position: {e}")
            
            if negative_margin == 0:
                logger.info(f"No negative margin detected for {symbol}")
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error repairing negative margin: {e}")
            return False