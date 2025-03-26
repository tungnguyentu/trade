from binance.client import Client
from binance.enums import (
    ORDER_TYPE_MARKET, 
    ORDER_TYPE_LIMIT, 
    ORDER_TYPE_STOP_MARKET, 
    ORDER_TYPE_TAKE_PROFIT_MARKET,
    TIME_IN_FORCE_GTC
)
from binance.exceptions import BinanceAPIException
from datetime import datetime
import time

from app.models.binance_client import BinanceClient
from app.notification.telegram_notifier import TelegramNotifier
from app.models.risk_manager import RiskManager
from app.utils.logger import get_logger
from app.config.config import TRADING_MODE

logger = get_logger()

class OrderManager:
    def __init__(self):
        self.binance_client = BinanceClient().get_client()
        self.notifier = TelegramNotifier()
        self.risk_manager = RiskManager()
        self.open_positions = {}  # Dict to track open positions {symbol: position_data}
    
    def execute_order(self, symbol, side, order_type, quantity, price=None, stop_price=None, 
                     reduce_only=False, working_type="CONTRACT_PRICE"):
        """
        Execute an order on Binance Futures
        
        Args:
            symbol (str): Trading pair symbol
            side (str): "BUY" or "SELL"
            order_type (str): Order type (MARKET, LIMIT, STOP_MARKET, TAKE_PROFIT_MARKET)
            quantity (float): Order quantity
            price (float, optional): Order price, required for LIMIT orders
            stop_price (float, optional): Stop price, required for stop orders
            reduce_only (bool): Whether this order is to reduce position only
            working_type (str): "CONTRACT_PRICE" or "MARK_PRICE" for trigger price type
            
        Returns:
            dict: Order response from Binance or simulated response
        """
        # Format the quantity to appropriate precision
        quantity = float(quantity)
        
        order_params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity
        }
        
        if price and order_type == ORDER_TYPE_LIMIT:
            order_params["price"] = price
            
        if stop_price and (order_type == ORDER_TYPE_STOP_MARKET or order_type == ORDER_TYPE_TAKE_PROFIT_MARKET):
            order_params["stopPrice"] = stop_price
            order_params["workingType"] = working_type
            
        if reduce_only:
            order_params["reduceOnly"] = "true"
        
        logger.info(f"Executing {order_type} order: {symbol} {side} {quantity}")
        
        # Determine which API to use based on trading mode
        if TRADING_MODE == "live":
            try:
                # Use real Binance Futures API
                if order_type == ORDER_TYPE_MARKET:
                    response = self.binance_client.futures_create_order(**order_params)
                elif order_type == ORDER_TYPE_LIMIT:
                    order_params["timeInForce"] = TIME_IN_FORCE_GTC
                    response = self.binance_client.futures_create_order(**order_params)
                elif order_type == ORDER_TYPE_STOP_MARKET:
                    response = self.binance_client.futures_create_order(**order_params)
                elif order_type == ORDER_TYPE_TAKE_PROFIT_MARKET:
                    response = self.binance_client.futures_create_order(**order_params)
                else:
                    raise ValueError(f"Unsupported order type: {order_type}")
                
                logger.info(f"Order executed: {response}")
                return response
                
            except BinanceAPIException as e:
                error_msg = f"Binance API error: {e.message}"
                logger.error(error_msg)
                self.notifier.send_error(error_msg)
                raise
                
        else:  # Backtest or paper trading mode
            # Simulate order execution
            return self._simulate_order_execution(symbol, side, order_type, quantity, price, stop_price)
    
    def _simulate_order_execution(self, symbol, side, order_type, quantity, price=None, stop_price=None):
        """
        Simulate order execution for backtesting and paper trading
        
        Returns a mock response that mimics Binance's response structure
        """
        # Get the current market price as execution price for market orders
        current_price = self.binance_client.futures_mark_price(symbol=symbol)["markPrice"]
        current_price = float(current_price)
        
        # For limit orders, use the specified price
        if order_type == ORDER_TYPE_LIMIT and price:
            execution_price = float(price)
        else:
            execution_price = current_price
            
        order_id = f"simulated_{int(time.time() * 1000)}"
        
        # Create a simulated order response
        response = {
            "symbol": symbol,
            "orderId": order_id,
            "clientOrderId": f"simulated_client_{int(time.time() * 1000)}",
            "transactTime": int(time.time() * 1000),
            "price": price if price else "0.0",
            "origQty": str(quantity),
            "executedQty": str(quantity),
            "status": "FILLED",
            "timeInForce": TIME_IN_FORCE_GTC,
            "type": order_type,
            "side": side,
            "avgPrice": str(execution_price)
        }
        
        logger.info(f"Simulated order executed: {response}")
        return response
    
    def open_position(self, symbol, signal_data, market_data):
        """
        Open a new trading position
        
        Args:
            symbol (str): Trading pair symbol
            signal_data (dict): Signal data with entry information
            market_data (dict): Current market data
            
        Returns:
            bool: True if position was opened successfully
        """
        # Check if we already have an open position for this symbol
        if symbol in self.open_positions:
            logger.warning(f"Position already open for {symbol}, skipping entry")
            return False
            
        # Calculate position size based on risk management
        entry_price = float(market_data["close"])
        position_size = self.risk_manager.calculate_position_size(
            symbol=symbol,
            entry_price=entry_price,
            stop_loss_price=signal_data.get("stop_loss_price"),
            risk_per_trade=signal_data.get("risk_per_trade")
        )
        
        # Determine if it's a long or short position
        is_long = signal_data.get("direction", "long") == "long"
        side = "BUY" if is_long else "SELL"
        
        # Execute the market order
        try:
            order_response = self.execute_order(
                symbol=symbol,
                side=side,
                order_type=ORDER_TYPE_MARKET,
                quantity=position_size
            )
            
            # If not in backtest mode, set stop loss and take profit orders
            if TRADING_MODE != "backtest":
                if signal_data.get("stop_loss_price"):
                    sl_side = "SELL" if is_long else "BUY"
                    self.execute_order(
                        symbol=symbol,
                        side=sl_side,
                        order_type=ORDER_TYPE_STOP_MARKET,
                        quantity=position_size,
                        stop_price=signal_data["stop_loss_price"],
                        reduce_only=True
                    )
                    
                if signal_data.get("take_profit_price"):
                    tp_side = "SELL" if is_long else "BUY"
                    self.execute_order(
                        symbol=symbol,
                        side=tp_side,
                        order_type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                        quantity=position_size,
                        stop_price=signal_data["take_profit_price"],
                        reduce_only=True
                    )
            
            # Record the open position
            self.open_positions[symbol] = {
                "entry_price": entry_price,
                "quantity": position_size,
                "side": side,
                "entry_time": datetime.now(),
                "strategy": signal_data.get("strategy_name", "Unknown"),
                "stop_loss": signal_data.get("stop_loss_price"),
                "take_profit": signal_data.get("take_profit_price")
            }
            
            # Send notification
            self.notifier.send_trade_entry(
                symbol=symbol,
                entry_price=entry_price,
                quantity=position_size,
                strategy_type=signal_data.get("strategy_name", "Unknown"),
                reasoning=signal_data.get("reasoning", "Signal generated by strategy")
            )
            
            logger.info(f"Position opened for {symbol} at {entry_price}")
            return True
            
        except Exception as e:
            logger.error(f"Error opening position: {e}")
            self.notifier.send_error(f"Failed to open position for {symbol}: {e}")
            return False
    
    def close_position(self, symbol, market_data, reason="Strategy exit signal"):
        """
        Close an existing position
        
        Args:
            symbol (str): Trading pair symbol
            market_data (dict): Current market data
            reason (str): Reason for closing the position
            
        Returns:
            bool: True if position was closed successfully
        """
        if symbol not in self.open_positions:
            logger.warning(f"No open position for {symbol}, cannot close")
            return False
            
        position = self.open_positions[symbol]
        exit_price = float(market_data["close"])
        
        # Determine the side to close position
        close_side = "SELL" if position["side"] == "BUY" else "BUY"
        
        try:
            # Execute market order to exit
            order_response = self.execute_order(
                symbol=symbol,
                side=close_side,
                order_type=ORDER_TYPE_MARKET,
                quantity=position["quantity"],
                reduce_only=True
            )
            
            # Calculate PnL
            entry_price = position["entry_price"]
            quantity = position["quantity"]
            
            if position["side"] == "BUY":  # Long position
                pnl = (exit_price - entry_price) * quantity
            else:  # Short position
                pnl = (entry_price - exit_price) * quantity
                
            pnl_percent = pnl / (entry_price * quantity)
            
            # Calculate duration
            duration = datetime.now() - position["entry_time"]
            duration_str = str(duration).split('.')[0]  # Remove microseconds
            
            # Send notification
            self.notifier.send_trade_exit(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                pnl=pnl,
                pnl_percent=pnl_percent,
                duration=duration_str,
                strategy_type=position["strategy"],
                reasoning=reason
            )
            
            # Update risk manager with trade result
            self.risk_manager.update_trade_history(
                symbol=symbol,
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=quantity,
                pnl=pnl,
                pnl_percent=pnl_percent,
                duration=duration,
                strategy=position["strategy"]
            )
            
            # Remove from open positions
            del self.open_positions[symbol]
            
            logger.info(f"Position closed for {symbol} at {exit_price}, PnL: {pnl:.2f} ({pnl_percent:.2%})")
            return True
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
            self.notifier.send_error(f"Failed to close position for {symbol}: {e}")
            return False
    
    def check_open_positions(self, current_market_data, strategy_signals):
        """
        Check for exit signals and manage open positions
        
        Args:
            current_market_data (dict): Dictionary of current market data by symbol
            strategy_signals (dict): Dictionary of strategy signals by symbol
        """
        for symbol, position in list(self.open_positions.items()):
            if symbol not in current_market_data:
                logger.warning(f"No market data for {symbol}, skipping position check")
                continue
                
            market_data = current_market_data[symbol]
            current_price = float(market_data["close"])
            
            # Check for stop loss hit
            if position["stop_loss"] and ((position["side"] == "BUY" and current_price <= position["stop_loss"]) or 
                                       (position["side"] == "SELL" and current_price >= position["stop_loss"])):
                logger.info(f"Stop loss triggered for {symbol} at {current_price}")
                self.close_position(symbol, market_data, "Stop loss triggered")
                continue
                
            # Check for take profit hit
            if position["take_profit"] and ((position["side"] == "BUY" and current_price >= position["take_profit"]) or 
                                         (position["side"] == "SELL" and current_price <= position["take_profit"])):
                logger.info(f"Take profit triggered for {symbol} at {current_price}")
                self.close_position(symbol, market_data, "Take profit triggered")
                continue
                
            # Check for strategy exit signals
            if symbol in strategy_signals and strategy_signals[symbol].get("action") == "exit":
                logger.info(f"Exit signal received for {symbol} from strategy")
                self.close_position(symbol, market_data, strategy_signals[symbol].get("reasoning", "Strategy exit signal")) 