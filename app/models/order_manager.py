from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from datetime import datetime
import time

from app.utils.binance_client import BinanceClient
from app.utils.logger import get_logger
from app.notification.telegram_notifier import TelegramNotifier
from app.config.config import TRADING_MODE
from app.risk_management.risk_manager import RiskManager

logger = get_logger()

class OrderManager:
    def __init__(self):
        self.binance_client = BinanceClient()
        self.client = self.binance_client.get_client()
        self.notifier = TelegramNotifier()
        self.risk_manager = RiskManager()
        self.open_positions = {}  # Track open positions
    
    def execute_order(self, symbol, side, quantity, order_type=ORDER_TYPE_MARKET, price=None, stop_price=None):
        """
        Execute an order on Binance
        
        Args:
            symbol (str): Symbol to trade
            side (str): 'BUY' or 'SELL'
            quantity (float): Quantity to buy/sell
            order_type (str): Order type (MARKET, LIMIT, STOP_LOSS, etc)
            price (float, optional): Limit price for limit orders
            stop_price (float, optional): Stop price for stop orders
            
        Returns:
            dict: Order response or None if error
        """
        try:
            # In backtest mode, simulate order execution
            if TRADING_MODE == 'backtest':
                return self._simulate_order_execution(symbol, side, quantity, order_type, price, stop_price)
                
            # In paper trading mode, simulate but use real market data
            if TRADING_MODE == 'paper':
                return self._simulate_order_execution(symbol, side, quantity, order_type, price, stop_price)
                
            # In live mode, execute actual order
            if TRADING_MODE == 'live':
                order_params = {
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity
                }
                
                # Add order type specific parameters
                if order_type == ORDER_TYPE_LIMIT:
                    order_params['type'] = ORDER_TYPE_LIMIT
                    order_params['timeInForce'] = TIME_IN_FORCE_GTC
                    order_params['price'] = price
                elif order_type == ORDER_TYPE_MARKET:
                    order_params['type'] = ORDER_TYPE_MARKET
                elif order_type == ORDER_TYPE_STOP_LOSS_LIMIT:
                    order_params['type'] = ORDER_TYPE_STOP_LOSS_LIMIT
                    order_params['timeInForce'] = TIME_IN_FORCE_GTC
                    order_params['price'] = price
                    order_params['stopPrice'] = stop_price
                elif order_type == ORDER_TYPE_TAKE_PROFIT_LIMIT:
                    order_params['type'] = ORDER_TYPE_TAKE_PROFIT_LIMIT
                    order_params['timeInForce'] = TIME_IN_FORCE_GTC
                    order_params['price'] = price
                    order_params['stopPrice'] = stop_price
                
                # Execute order
                response = self.client.create_order(**order_params)
                logger.info(f"Order executed: {response}")
                return response
                
        except BinanceAPIException as e:
            error_msg = f"Error executing {order_type} {side} order for {symbol}: {e}"
            logger.error(error_msg)
            self.notifier.send_error(error_msg)
            return None
        except Exception as e:
            error_msg = f"Unexpected error executing order: {e}"
            logger.error(error_msg)
            self.notifier.send_error(error_msg)
            return None
    
    def _simulate_order_execution(self, symbol, side, quantity, order_type, price=None, stop_price=None):
        """Simulate order execution for backtesting and paper trading"""
        # Get current price if not provided
        if price is None or order_type == ORDER_TYPE_MARKET:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            price = current_price
        
        # Create simulated order response
        order_id = f"sim_{int(time.time() * 1000)}"
        executed_qty = quantity
        cummulative_quote_qty = executed_qty * price
        
        response = {
            'orderId': order_id,
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'price': str(price),
            'origQty': str(quantity),
            'executedQty': str(executed_qty),
            'cummulativeQuoteQty': str(cummulative_quote_qty),
            'status': ORDER_STATUS_FILLED,
            'timeInForce': TIME_IN_FORCE_GTC if order_type != ORDER_TYPE_MARKET else 'NA',
            'time': int(time.time() * 1000),
            'fills': [{
                'price': str(price),
                'qty': str(executed_qty),
                'commission': '0',
                'commissionAsset': 'USDT'
            }]
        }
        
        if stop_price:
            response['stopPrice'] = str(stop_price)
            
        logger.info(f"Simulated {TRADING_MODE} order: {symbol} {side} {quantity} at {price}")
        return response
    
    def open_position(self, symbol, entry_price, quantity, stop_loss, take_profit, strategy_type, signal_data):
        """
        Open a new trading position
        
        Args:
            symbol (str): Trading pair symbol
            entry_price (float): Entry price
            quantity (float): Quantity to trade
            stop_loss (float): Stop loss price
            take_profit (float): Take profit price
            strategy_type (str): Strategy type (Scalping, Swing)
            signal_data (dict): Signal data
            
        Returns:
            dict: Position information or None if error
        """
        try:
            # Determine if this is a long or short position
            is_long = signal_data['type'] == 'long'
            position_side = 'LONG' if is_long else 'SHORT'
            order_side = 'BUY' if is_long else 'SELL'
            
            # Generate reasoning text
            if 'get_signal_reasoning' in dir(signal_data):
                reasoning = signal_data.get_signal_reasoning(signal_data)
            else:
                reasoning = f"Entry based on {strategy_type} strategy"
                
            # Execute market order
            order_response = self.execute_order(
                symbol=symbol,
                side=order_side,
                quantity=quantity,
                order_type=ORDER_TYPE_MARKET
            )
            
            if not order_response:
                logger.error(f"Failed to execute entry order for {symbol}")
                return None
                
            # Record position
            position = {
                'symbol': symbol,
                'type': signal_data['type'],  # 'long' or 'short'
                'entry_time': datetime.now(),
                'entry_price': entry_price,
                'quantity': quantity,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'strategy': strategy_type,
                'order_id': order_response['orderId'],
                'status': 'open',
                'pnl': 0.0,
                'exit_price': None,
                'exit_time': None,
                'exit_reason': None
            }
            
            # Store position in open positions
            self.open_positions[symbol] = position
            
            # Set stop loss and take profit orders if not in backtest mode
            if TRADING_MODE != 'backtest':
                sl_side = 'SELL' if is_long else 'BUY'
                tp_side = 'SELL' if is_long else 'BUY'
                
                # Place stop loss order
                sl_order = self.execute_order(
                    symbol=symbol,
                    side=sl_side,
                    quantity=quantity,
                    order_type=ORDER_TYPE_STOP_LOSS_LIMIT,
                    price=stop_loss * 0.99 if is_long else stop_loss * 1.01,  # Ensure it executes
                    stop_price=stop_loss
                )
                
                # Place take profit order
                tp_order = self.execute_order(
                    symbol=symbol,
                    side=tp_side,
                    quantity=quantity,
                    order_type=ORDER_TYPE_TAKE_PROFIT_LIMIT,
                    price=take_profit * 1.01 if is_long else take_profit * 0.99,  # Ensure it executes
                    stop_price=take_profit
                )
                
                if sl_order:
                    position['stop_loss_order_id'] = sl_order['orderId']
                
                if tp_order:
                    position['take_profit_order_id'] = tp_order['orderId']
            
            # Send notification
            self.notifier.send_trade_entry(
                symbol=symbol,
                entry_price=entry_price,
                quantity=quantity,
                strategy_type=strategy_type,
                reasoning=reasoning
            )
            
            logger.info(f"Opened {position_side} position for {symbol} at {entry_price}")
            return position
            
        except Exception as e:
            error_msg = f"Error opening position for {symbol}: {e}"
            logger.error(error_msg)
            self.notifier.send_error(error_msg)
            return None
    
    def close_position(self, symbol, exit_price, exit_reason):
        """
        Close an existing position
        
        Args:
            symbol (str): Trading pair symbol
            exit_price (float): Exit price
            exit_reason (str): Reason for exiting
            
        Returns:
            dict: Position information or None if error
        """
        try:
            # Check if position exists
            if symbol not in self.open_positions:
                logger.warning(f"No open position found for {symbol}")
                return None
                
            position = self.open_positions[symbol]
            is_long = position['type'] == 'long'
            position_side = 'LONG' if is_long else 'SHORT'
            order_side = 'SELL' if is_long else 'BUY'
            
            # Execute market order to close position
            order_response = self.execute_order(
                symbol=symbol,
                side=order_side,
                quantity=position['quantity'],
                order_type=ORDER_TYPE_MARKET
            )
            
            if not order_response:
                logger.error(f"Failed to execute exit order for {symbol}")
                return None
                
            # Update position data
            position['exit_price'] = exit_price
            position['exit_time'] = datetime.now()
            position['exit_reason'] = exit_reason
            position['status'] = 'closed'
            
            # Calculate P&L
            entry_price = position['entry_price']
            exit_price = float(exit_price)
            quantity = float(position['quantity'])
            
            if is_long:
                pnl_usdt = (exit_price - entry_price) * quantity
                pnl_pct = (exit_price - entry_price) / entry_price
            else:
                pnl_usdt = (entry_price - exit_price) * quantity
                pnl_pct = (entry_price - exit_price) / entry_price
                
            position['pnl'] = pnl_usdt
            position['pnl_percent'] = pnl_pct
            
            # Calculate trade duration
            duration_seconds = (position['exit_time'] - position['entry_time']).total_seconds()
            hours, remainder = divmod(duration_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
            position['duration'] = duration_str
            
            # Cancel any open stop loss or take profit orders
            if TRADING_MODE != 'backtest' and 'stop_loss_order_id' in position:
                try:
                    self.client.cancel_order(symbol=symbol, orderId=position['stop_loss_order_id'])
                except:
                    pass
                    
            if TRADING_MODE != 'backtest' and 'take_profit_order_id' in position:
                try:
                    self.client.cancel_order(symbol=symbol, orderId=position['take_profit_order_id'])
                except:
                    pass
            
            # Send notification
            self.notifier.send_trade_exit(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                pnl=pnl_usdt,
                pnl_percent=pnl_pct,
                duration=duration_str,
                strategy_type=position['strategy'],
                reasoning=exit_reason
            )
            
            # Update risk manager with trade result
            trade_record = {
                'symbol': symbol,
                'entry_time': position['entry_time'],
                'exit_time': position['exit_time'],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'quantity': quantity,
                'type': position['type'],
                'pnl': pnl_usdt,
                'pnl_percent': pnl_pct,
                'strategy': position['strategy'],
                'duration': duration_str,
                'exit_reason': exit_reason,
                'investment': entry_price * quantity
            }
            
            self.risk_manager.update_trade_history(trade_record)
            
            # Remove from open positions
            del self.open_positions[symbol]
            
            logger.info(f"Closed {position_side} position for {symbol} at {exit_price} with P&L: {pnl_usdt:.2f} USDT ({pnl_pct:.2%})")
            return position
            
        except Exception as e:
            error_msg = f"Error closing position for {symbol}: {e}"
            logger.error(error_msg)
            self.notifier.send_error(error_msg)
            return None
    
    def check_open_positions(self, symbol, current_data, strategy):
        """
        Check open positions for exit signals
        
        Args:
            symbol (str): Trading pair symbol
            current_data (dict): Current market data
            strategy (obj): Strategy object to check exit conditions
            
        Returns:
            bool: True if position was closed, False otherwise
        """
        try:
            # Check if position exists
            if symbol not in self.open_positions:
                return False
                
            position = self.open_positions[symbol]
            current_price = current_data['close'].iloc[-1]
            
            # Check for exit signals from strategy
            should_exit, exit_reason = strategy.should_exit_trade(position['entry_price'], position)
            
            if should_exit:
                logger.info(f"Exit signal for {symbol}: {exit_reason}")
                self.close_position(symbol, current_price, exit_reason)
                return True
                
            # Check for stop loss / take profit
            is_long = position['type'] == 'long'
            
            # Check stop loss
            if (is_long and current_price <= position['stop_loss']) or \
               (not is_long and current_price >= position['stop_loss']):
                exit_reason = f"Stop loss triggered at {current_price}"
                logger.info(exit_reason)
                self.close_position(symbol, current_price, exit_reason)
                return True
                
            # Check take profit
            if (is_long and current_price >= position['take_profit']) or \
               (not is_long and current_price <= position['take_profit']):
                exit_reason = f"Take profit reached at {current_price}"
                logger.info(exit_reason)
                self.close_position(symbol, current_price, exit_reason)
                return True
                
            return False
            
        except Exception as e:
            error_msg = f"Error checking open position for {symbol}: {e}"
            logger.error(error_msg)
            return False 